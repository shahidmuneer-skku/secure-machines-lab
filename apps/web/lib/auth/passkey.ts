"use client"

import { startAuthentication, startRegistration, browserSupportsWebAuthn } from "@simplewebauthn/browser"

import { allauth, AuthError } from "./allauth"

export const passkeysSupported = () => typeof window !== "undefined" && browserSupportsWebAuthn()

/** Passwordless sign-in with a passkey. */
export async function signInWithPasskey() {
  const options = await allauth.passkeyLoginOptions()
  const optionsJSON = options.data?.request_options?.publicKey
  if (!optionsJSON) throw new AuthError(options, "Passkey sign-in is not available.")
  const credential = await startAuthentication({ optionsJSON: optionsJSON as never })
  return allauth.passkeyLogin(credential)
}

/** Passkey as the second factor after a password. */
export async function passkeySecondFactor() {
  const options = await allauth.passkey2faOptions()
  const optionsJSON = options.data?.request_options?.publicKey
  if (!optionsJSON) throw new AuthError(options, "Passkey verification is not available.")
  const credential = await startAuthentication({ optionsJSON: optionsJSON as never })
  return allauth.passkey2fa(credential)
}

export async function registerPasskey(name: string) {
  const options = await allauth.passkeyCreateOptions(true)
  const optionsJSON = options.data?.creation_options?.publicKey
  if (!optionsJSON) throw new AuthError(options, "Please confirm your password first.")
  const credential = await startRegistration({ optionsJSON: optionsJSON as never })
  return allauth.addPasskey(name, credential)
}
