/** API クライアントのトークン保持とエラーコード変換。 */
import { beforeEach, describe, expect, it } from 'vitest'

import en from '../i18n/en.json'
import ja from '../i18n/ja.json'
import { ApiError, clearTokens, errorMessageKey, hasTokens, setTokens } from './api'

describe('errorMessageKey', () => {
  it('ApiError のコードを i18n キーへ変換する', () => {
    expect(errorMessageKey(new ApiError(401, 'invalid_token'))).toBe('error.invalid_token')
  })

  it('API 以外の例外は unknown_error に丸める', () => {
    expect(errorMessageKey(new Error('boom'))).toBe('error.unknown_error')
  })

  it('例外でない値でも落ちない', () => {
    expect(errorMessageKey(undefined)).toBe('error.unknown_error')
    expect(errorMessageKey('invalid_token')).toBe('error.unknown_error')
  })

  it('入力検証の失敗は、落ちた項目の文言を指す', () => {
    expect(errorMessageKey(new ApiError(422, 'validation_error', ['password']))).toBe(
      'error.invalid_password',
    )
  })

  it('文言を用意していない項目は一般的な文言に落ちる（キーがそのまま出ない）', () => {
    expect(errorMessageKey(new ApiError(422, 'validation_error', ['idempotency_key']))).toBe(
      'error.validation_error',
    )
  })

  it('項目名が無い入力検証の失敗でも一般的な文言になる', () => {
    expect(errorMessageKey(new ApiError(422, 'validation_error'))).toBe('error.validation_error')
  })
})

describe('入力検証の文言', () => {
  /**
   * `errorMessageKey` が返し得るキーは辞書に必ずある。無いと `t` がキーをそのまま
   * 返し、画面に `error.invalid_email` という文字列が出る。
   */
  const KEYS = [
    'amount',
    'code',
    'display_name',
    'email',
    'name',
    'password',
    'reason',
    'username',
  ].map((field) => `error.invalid_${field}`)

  // キーに `.` を含むため配列で渡す（文字列だと入れ子のパスとして解釈される）。
  it.each([...KEYS, 'error.validation_error'])('%s が en/ja の双方にある', (key) => {
    expect(en).toHaveProperty([key])
    expect(ja).toHaveProperty([key])
  })
})

describe('トークンの保持', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('保存前は未保持', () => {
    expect(hasTokens()).toBe(false)
  })

  it('保存すると保持と判定される', () => {
    setTokens('access', 'refresh')
    expect(hasTokens()).toBe(true)
  })

  it('消すと未保持に戻る', () => {
    setTokens('access', 'refresh')
    clearTokens()
    expect(hasTokens()).toBe(false)
  })
})
