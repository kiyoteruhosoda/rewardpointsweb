/**
 * Browser-side handling of passkeys (WebAuthn).
 *
 * The server returns options as JSON with base64url strings and accepts
 * responses in the same format (py_webauthn compatible). This only does that conversion and
 * calls `navigator.credentials`. No external library is used.
 */

import { isRelyingPartyIdUsable, relyingPartyIdOf } from './relyingParty'

export interface PasskeyChallenge {
  challenge_id: string
  public_key: Record<string, unknown>
}

/** Thrown when the user cancels the operation, so the error message can differ. */
export const PASSKEY_CANCELLED = 'passkey_cancelled'

/**
 * Thrown when the RP ID cannot be used on the domain currently open.
 *
 * Left to the browser, how the failure surfaces differs by implementation (some throw `SecurityError`,
 * others turn it into the same `NotAllowedError` as a cancel), and a misconfiguration
 * shows up as "cancelled". Check before calling so the cause is kept.
 */
export class PasskeyRelyingPartyMismatchError extends Error {
  constructor(
    readonly relyingPartyId: string,
    readonly domain: string,
  ) {
    super(`relying party id "${relyingPartyId}" cannot be used on "${domain}"`)
    this.name = 'PasskeyRelyingPartyMismatchError'
  }
}

/** Check that the RP ID returned by the server can be used on the domain currently open. */
function assertRelyingParty(publicKey: Record<string, unknown>): void {
  const relyingPartyId = relyingPartyIdOf(publicKey)
  // If omitted, the browser uses the open domain, so there can be no mismatch.
  if (!relyingPartyId) return
  const { hostname } = window.location
  if (isRelyingPartyIdUsable(relyingPartyId, hostname)) return
  throw new PasskeyRelyingPartyMismatchError(relyingPartyId, hostname)
}

export function isPasskeySupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.PublicKeyCredential !== 'undefined' &&
    !!navigator.credentials
  )
}

function base64urlToBuffer(value: string): ArrayBuffer {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=')
  const binary = atob(padded)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
  return bytes.buffer
}

function bufferToBase64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** Convert a base64url credential list into WebAuthn descriptors. */
function toDescriptors(source: unknown): PublicKeyCredentialDescriptor[] {
  if (!Array.isArray(source)) return []
  return source.map((item) => {
    const descriptor = item as { id: string; type: 'public-key'; transports?: string[] }
    return {
      ...descriptor,
      id: base64urlToBuffer(descriptor.id),
    } as PublicKeyCredentialDescriptor
  })
}

/** Convert only the fields of the server's JSON that need an ArrayBuffer. */
function toCreationOptions(source: Record<string, unknown>): PublicKeyCredentialCreationOptions {
  const user = source.user as { id: string; name: string; displayName: string }
  return {
    ...source,
    challenge: base64urlToBuffer(source.challenge as string),
    user: { ...user, id: base64urlToBuffer(user.id) },
    excludeCredentials: toDescriptors(source.excludeCredentials),
  } as PublicKeyCredentialCreationOptions
}

function toRequestOptions(source: Record<string, unknown>): PublicKeyCredentialRequestOptions {
  return {
    ...source,
    challenge: base64urlToBuffer(source.challenge as string),
    allowCredentials: toDescriptors(source.allowCredentials),
  }
}

function assertCredential(credential: Credential | null): PublicKeyCredential {
  if (!credential) throw new Error(PASSKEY_CANCELLED)
  return credential as PublicKeyCredential
}

/** Have the authenticator create a new passkey and shape it for sending to the server. */
export async function createPasskey(
  publicKey: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  assertRelyingParty(publicKey)
  const credential = assertCredential(
    await navigator.credentials.create({ publicKey: toCreationOptions(publicKey) }),
  )
  const response = credential.response as AuthenticatorAttestationResponse
  return {
    id: credential.id,
    rawId: bufferToBase64url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment ?? undefined,
    clientExtensionResults: credential.getClientExtensionResults(),
    response: {
      clientDataJSON: bufferToBase64url(response.clientDataJSON),
      attestationObject: bufferToBase64url(response.attestationObject),
      transports: typeof response.getTransports === 'function' ? response.getTransports() : [],
    },
  }
}

/** Have a registered passkey sign and shape it for sending to the server. */
export async function assertPasskey(
  publicKey: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  assertRelyingParty(publicKey)
  const credential = assertCredential(
    await navigator.credentials.get({ publicKey: toRequestOptions(publicKey) }),
  )
  const response = credential.response as AuthenticatorAssertionResponse
  return {
    id: credential.id,
    rawId: bufferToBase64url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment ?? undefined,
    clientExtensionResults: credential.getClientExtensionResults(),
    response: {
      clientDataJSON: bufferToBase64url(response.clientDataJSON),
      authenticatorData: bufferToBase64url(response.authenticatorData),
      signature: bufferToBase64url(response.signature),
      userHandle: response.userHandle ? bufferToBase64url(response.userHandle) : null,
    },
  }
}

/** Detect a cancel (NotAllowedError) thrown by the browser. */
export function isPasskeyCancellation(error: unknown): boolean {
  if (error instanceof Error && error.message === PASSKEY_CANCELLED) return true
  return error instanceof DOMException && error.name === 'NotAllowedError'
}

/** Name of a DOMException thrown by `navigator.credentials` -> translation key. */
const BROWSER_ERROR_KEYS: Record<string, string> = {
  // The RP ID does not match the domain of the open URL (misconfiguration).
  SecurityError: 'error.passkey_domain_mismatch',
  // The authenticator already has a passkey for the same account (excludeCredentials).
  InvalidStateError: 'error.passkey_already_on_device',
  // The authenticator does not support the requested method.
  NotSupportedError: 'error.passkey_unsupported_authenticator',
}

/**
 * Convert a browser-originated failure into a translation key. `null` if it came from the server.
 *
 * Failures from `navigator.credentials` are not `ApiError`, so passing them straight to
 * `errorMessageKey()` yields "An error occurred" whatever the cause.
 * Callers write `passkeyErrorKey(err) ?? errorMessageKey(err)`.
 */
export function passkeyErrorKey(error: unknown): string | null {
  if (error instanceof PasskeyRelyingPartyMismatchError) return 'error.passkey_domain_mismatch'
  if (isPasskeyCancellation(error)) return 'error.passkey_cancelled'
  if (!(error instanceof DOMException)) return null
  return BROWSER_ERROR_KEYS[error.name] ?? null
}
