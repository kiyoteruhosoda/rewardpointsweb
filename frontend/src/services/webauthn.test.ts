/** Browser-originated passkey failures map to translation keys that explain the cause. */
import { afterEach, describe, expect, it, vi } from 'vitest'

import en from '../i18n/en.json'
import ja from '../i18n/ja.json'
import { ApiError, errorMessageKey } from './api'
import {
  PASSKEY_CANCELLED,
  PasskeyRelyingPartyMismatchError,
  assertPasskey,
  createPasskey,
  isPasskeyCancellation,
  passkeyErrorKey,
} from './webauthn'

describe('checks before creating or using a passkey', () => {
  // jsdom opens localhost. Pass a config whose RP ID does not match it.
  const credentials = { create: vi.fn(), get: vi.fn() }

  afterEach(() => {
    vi.unstubAllGlobals()
    credentials.create.mockReset()
    credentials.get.mockReset()
  })

  function stubCredentials(): void {
    vi.stubGlobal('navigator', { credentials })
  }

  it('fails with a clear cause, without calling the authenticator, for an unusable RP ID', async () => {
    stubCredentials()
    await expect(createPasskey({ rp: { id: 'example.com' } })).rejects.toBeInstanceOf(
      PasskeyRelyingPartyMismatchError,
    )
    expect(credentials.create).not.toHaveBeenCalled()
  })

  it('checks the same on the login (authentication) side', async () => {
    stubCredentials()
    await expect(assertPasskey({ rpId: 'example.com' })).rejects.toBeInstanceOf(
      PasskeyRelyingPartyMismatchError,
    )
    expect(credentials.get).not.toHaveBeenCalled()
  })

  it('translates a mismatch as a misconfiguration (not a cancellation)', () => {
    const error = new PasskeyRelyingPartyMismatchError('example.com', 'localhost')
    expect(passkeyErrorKey(error)).toBe('error.passkey_domain_mismatch')
    expect(isPasskeyCancellation(error)).toBe(false)
  })
})

describe('passkeyErrorKey', () => {
  it('recognises an RP ID not matching the domain (SecurityError)', () => {
    // Do not turn a misconfiguration into "an error occurred" on the user's screen
    expect(passkeyErrorKey(new DOMException('bad rp id', 'SecurityError'))).toBe(
      'error.passkey_domain_mismatch',
    )
  })

  it('recognises an already registered device (InvalidStateError)', () => {
    expect(passkeyErrorKey(new DOMException('exists', 'InvalidStateError'))).toBe(
      'error.passkey_already_on_device',
    )
  })

  it('recognises an unsupported authenticator (NotSupportedError)', () => {
    expect(passkeyErrorKey(new DOMException('nope', 'NotSupportedError'))).toBe(
      'error.passkey_unsupported_authenticator',
    )
  })

  it('returns a cancellation as a cancellation', () => {
    expect(passkeyErrorKey(new DOMException('cancel', 'NotAllowedError'))).toBe(
      'error.passkey_cancelled',
    )
    expect(passkeyErrorKey(new Error(PASSKEY_CANCELLED))).toBe('error.passkey_cancelled')
  })

  it('returns null for server-originated failures, leaving conversion to the caller', () => {
    expect(passkeyErrorKey(new ApiError(500, 'passkey_misconfigured'))).toBeNull()
    expect(passkeyErrorKey(new DOMException('other', 'AbortError'))).toBeNull()
    expect(passkeyErrorKey(undefined)).toBeNull()
  })

  it('every returned key has translations in both languages', () => {
    const errors = [
      new DOMException('bad rp id', 'SecurityError'),
      new DOMException('exists', 'InvalidStateError'),
      new DOMException('nope', 'NotSupportedError'),
      new DOMException('cancel', 'NotAllowedError'),
    ]
    const keys = [
      ...errors.map((error) => passkeyErrorKey(error) ?? ''),
      errorMessageKey(new ApiError(500, 'passkey_misconfigured')),
      errorMessageKey(new ApiError(400, 'invalid_webauthn_rp_id')),
      errorMessageKey(new ApiError(400, 'invalid_webauthn_origin')),
    ]
    for (const key of keys) {
      expect(Object.keys(ja)).toContain(key)
      expect(Object.keys(en)).toContain(key)
    }
  })
})

describe('isPasskeyCancellation', () => {
  it('a DOMException other than cancellation is not a cancellation', () => {
    expect(isPasskeyCancellation(new DOMException('bad rp id', 'SecurityError'))).toBe(false)
  })
})
