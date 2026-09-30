/**
 * django-allauth headless (browser client) — session cookies, CSRF, MFA, passkeys.
 * Spec: GET /api/_allauth/openapi.json
 */
import { ensureCsrf, readCsrfToken } from "@/lib/api/csrf"

const BASE = "/api/_allauth/browser/v1"

export interface AuthFlow {
  id: string
  is_pending?: boolean
  types?: string[]
}

export interface AuthUser {
  id: string
  email: string
  display: string
  has_usable_password: boolean
}

export interface AuthResponse<T = unknown> {
  status: number
  data?: T & { flows?: AuthFlow[]; user?: AuthUser; methods?: { method: string; at: number }[] }
  meta?: { is_authenticated?: boolean; session_token?: string; recovery_codes_generated?: boolean } & Record<
    string,
    unknown
  >
  errors?: { message: string; code: string; param?: string }[]
}

export class AuthError extends Error {
  constructor(
    readonly response: AuthResponse,
    message?: string,
  ) {
    super(message ?? response.errors?.[0]?.message ?? `Authentication request failed (${response.status})`)
    this.name = "AuthError"
  }

  fieldError(param: string): string | undefined {
    return this.response.errors?.find((e) => e.param === param)?.message
  }
}

async function call<T = unknown>(
  method: "GET" | "POST" | "PUT" | "DELETE",
  path: string,
  body?: unknown,
  headers: Record<string, string> = {},
): Promise<AuthResponse<T>> {
  if (method !== "GET") await ensureCsrf()
  const res = await fetch(`${BASE}${path}`, {
    method,
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(method !== "GET" ? { "X-CSRFToken": readCsrfToken() } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const json = (await res.json().catch(() => ({ status: res.status }))) as AuthResponse<T>
  json.status = json.status ?? res.status
  // 401 is a normal "not (yet) authenticated" answer that carries the pending flows.
  if (res.status >= 400 && res.status !== 401) throw new AuthError(json)
  return json
}

export function pendingFlow(res: AuthResponse): AuthFlow | undefined {
  return res.data?.flows?.find((f) => f.is_pending)
}

export const allauth = {
  config: () => call("GET", "/config"),
  session: () => call("GET", "/auth/session"),
  logout: () => call("DELETE", "/auth/session"),
  login: (email: string, password: string, remember = false) =>
    call("POST", "/auth/login", { email, password, remember }),
  signup: (payload: Record<string, unknown>) => call("POST", "/auth/signup", payload),
  verifyEmail: (key: string) => call("POST", "/auth/email/verify", { key }),
  resendVerification: () => call("POST", "/auth/email/verify/resend"),
  requestPasswordReset: (email: string) => call("POST", "/auth/password/request", { email }),
  checkResetKey: (key: string) => call("GET", "/auth/password/reset", undefined, { "X-Password-Reset-Key": key }),
  resetPassword: (key: string, password: string) => call("POST", "/auth/password/reset", { key, password }),
  mfaAuthenticate: (code: string) => call("POST", "/auth/2fa/authenticate", { code }),
  reauthenticate: (password: string) => call("POST", "/auth/reauthenticate", { password }),
  mfaReauthenticate: (code: string) => call("POST", "/auth/2fa/reauthenticate", { code }),
  changePassword: (current_password: string, new_password: string) =>
    call("POST", "/account/password/change", { current_password, new_password }),

  // passkeys
  passkeyLoginOptions: () => call<{ request_options: { publicKey: Record<string, unknown> } }>("GET", "/auth/webauthn/login"),
  passkeyLogin: (credential: unknown) => call("POST", "/auth/webauthn/login", { credential }),
  passkey2faOptions: () =>
    call<{ request_options: { publicKey: Record<string, unknown> } }>("GET", "/auth/webauthn/authenticate"),
  passkey2fa: (credential: unknown) => call("POST", "/auth/webauthn/authenticate", { credential }),
  passkeyCreateOptions: (passwordless = true) =>
    call<{ creation_options: { publicKey: Record<string, unknown> } }>(
      "GET",
      `/account/authenticators/webauthn?passwordless=${passwordless}`,
    ),
  addPasskey: (name: string, credential: unknown) =>
    call("POST", "/account/authenticators/webauthn", { name, credential }),
  renamePasskey: (id: number, name: string) => call("PUT", "/account/authenticators/webauthn", { id, name }),
  deletePasskeys: (ids: number[]) => call("DELETE", "/account/authenticators/webauthn", { authenticators: ids }),

  // TOTP & recovery codes
  authenticators: () =>
    call<unknown>("GET", "/account/authenticators") as Promise<AuthResponse<Authenticator[]>>,
  totp: () => call<{ secret?: string; totp_url?: string }>("GET", "/account/authenticators/totp"),
  activateTotp: (code: string) => call("POST", "/account/authenticators/totp", { code }),
  deactivateTotp: () => call("DELETE", "/account/authenticators/totp"),
  recoveryCodes: () =>
    call<{ unused_codes?: string[]; total_code_count: number; unused_code_count: number }>(
      "GET",
      "/account/authenticators/recovery-codes",
    ),
  regenerateRecoveryCodes: () => call("POST", "/account/authenticators/recovery-codes"),

  // sessions
  sessions: () => call<SessionInfo[]>("GET", "/auth/sessions"),
  endSessions: (ids: number[]) => call("DELETE", "/auth/sessions", { sessions: ids }),
}

export interface Authenticator {
  id?: number
  type: "totp" | "recovery_codes" | "webauthn"
  name?: string
  created_at: number
  last_used_at: number | null
  is_passwordless?: boolean
  total_code_count?: number
  unused_code_count?: number
}

export interface SessionInfo {
  id: number
  user_agent: string
  ip: string
  created_at: number
  is_current: boolean
  last_seen_at?: number
}
