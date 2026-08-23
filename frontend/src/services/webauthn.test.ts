/** ブラウザ由来のパスキー失敗を、原因の分かる翻訳キーへ変換できること。 */
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

describe('パスキーを作る・使う前の噛み合わせ', () => {
  // jsdom が開いている URL は localhost。RP ID がそれと合わない設定を渡す。
  const credentials = { create: vi.fn(), get: vi.fn() }

  afterEach(() => {
    vi.unstubAllGlobals()
    credentials.create.mockReset()
    credentials.get.mockReset()
  })

  function stubCredentials(): void {
    vi.stubGlobal('navigator', { credentials })
  }

  it('使えない RP ID なら、認証器を呼ばずに原因の分かる失敗にする', async () => {
    stubCredentials()
    await expect(createPasskey({ rp: { id: 'example.com' } })).rejects.toBeInstanceOf(
      PasskeyRelyingPartyMismatchError,
    )
    expect(credentials.create).not.toHaveBeenCalled()
  })

  it('ログイン（認証）の側でも同じように見る', async () => {
    stubCredentials()
    await expect(assertPasskey({ rpId: 'example.com' })).rejects.toBeInstanceOf(
      PasskeyRelyingPartyMismatchError,
    )
    expect(credentials.get).not.toHaveBeenCalled()
  })

  it('食い違いは設定の誤りとして訳される（取り消しにはしない）', () => {
    const error = new PasskeyRelyingPartyMismatchError('example.com', 'localhost')
    expect(passkeyErrorKey(error)).toBe('error.passkey_domain_mismatch')
    expect(isPasskeyCancellation(error)).toBe(false)
  })
})

describe('passkeyErrorKey', () => {
  it('RP ID がドメインと合わない場合（SecurityError）を見分ける', () => {
    // 設定の誤りを利用者の画面で「エラーが発生しました」にしない
    expect(passkeyErrorKey(new DOMException('bad rp id', 'SecurityError'))).toBe(
      'error.passkey_domain_mismatch',
    )
  })

  it('同じ端末に登録済みの場合（InvalidStateError）を見分ける', () => {
    expect(passkeyErrorKey(new DOMException('exists', 'InvalidStateError'))).toBe(
      'error.passkey_already_on_device',
    )
  })

  it('認証器が対応していない場合（NotSupportedError）を見分ける', () => {
    expect(passkeyErrorKey(new DOMException('nope', 'NotSupportedError'))).toBe(
      'error.passkey_unsupported_authenticator',
    )
  })

  it('取り消しは取り消しとして返す', () => {
    expect(passkeyErrorKey(new DOMException('cancel', 'NotAllowedError'))).toBe(
      'error.passkey_cancelled',
    )
    expect(passkeyErrorKey(new Error(PASSKEY_CANCELLED))).toBe('error.passkey_cancelled')
  })

  it('サーバー由来の失敗は null を返し、呼び出し側の変換に委ねる', () => {
    expect(passkeyErrorKey(new ApiError(500, 'passkey_misconfigured'))).toBeNull()
    expect(passkeyErrorKey(new DOMException('other', 'AbortError'))).toBeNull()
    expect(passkeyErrorKey(undefined)).toBeNull()
  })

  it('返すキーは両言語に訳がある', () => {
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
  it('取り消し以外の DOMException は取り消しではない', () => {
    expect(isPasskeyCancellation(new DOMException('bad rp id', 'SecurityError'))).toBe(false)
  })
})
