/** RFC 9457 Problem Details returned by the Django API. */
export interface ProblemDetails {
  type?: string
  title?: string
  status: number
  detail?: string
  code?: string
  request_id?: string
  errors?: { field: string; message: string }[]
  [key: string]: unknown
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly detail: string
  readonly fieldErrors: Record<string, string>
  readonly requestId?: string
  readonly problem: ProblemDetails

  constructor(problem: ProblemDetails) {
    super(problem.detail || problem.title || `Request failed (${problem.status})`)
    this.name = "ApiError"
    this.problem = problem
    this.status = problem.status
    this.code = problem.code ?? "ERROR"
    this.detail = problem.detail ?? problem.title ?? ""
    this.requestId = problem.request_id
    this.fieldErrors = Object.fromEntries((problem.errors ?? []).map((e) => [e.field, e.message]))
  }

  get isAuth(): boolean {
    return this.status === 401
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

export async function problemFromResponse(response: Response): Promise<ProblemDetails> {
  try {
    const body = await response.clone().json()
    if (body && typeof body === "object") return { status: response.status, ...body }
  } catch {
    /* not JSON */
  }
  return { status: response.status, title: response.statusText || "Request failed" }
}
