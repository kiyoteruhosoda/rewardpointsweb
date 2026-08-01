/**
 * API クライアント（fetch ラッパー）。
 *
 * - JWT を localStorage に保持し、Authorization ヘッダーで送る。
 * - 401 のとき refresh トークンで1回だけ再試行する。
 * - バックエンドはエラーコード（{"error": "..."}）を返す。表示文言への変換は
 *   i18n（フロントエンド側）で行う。
 */

const ACCESS_KEY = 'access_token'
const REFRESH_KEY = 'refresh_token'

export class ApiError extends Error {
  status: number
  code: string
  /** 入力検証で落ちた項目名（`validation_error` のときだけ入る）。 */
  fields: string[]

  constructor(status: number, code: string, fields: string[] = []) {
    super(code)
    this.status = status
    this.code = code
    this.fields = fields
  }
}

/** 入力検証の失敗に付くコード（`presentation/fastapi/error_handling.py` と対）。 */
const VALIDATION_ERROR_CODE = 'validation_error'

/**
 * 項目ごとの文言を用意してある項目名。
 *
 * 入力検証の失敗は「どこが悪いか」を言えないと直しようがないので、項目名から
 * `error.invalid_<項目名>` を引く。ここに挙げた名前だけを使うのは、辞書に無い
 * キーが画面へそのまま出るのを防ぐため（未知の項目は `validation_error` の
 * 一般的な文言に落ちる）。名前は API の項目名と同じ綴りにする。
 *
 * **文言は「どの欄か」までにし、原因を断定しない。** 同じ項目名を複数のスキーマが
 * 使っており、決まりもそれぞれ違う。`code` は招待コード（`InvitationRedeemRequest`）
 * と認証アプリのコード（`TotpCodeRequest`、6〜10 文字）の両方で使われるので、
 * 「招待コードを入力してください」と書くと二要素認証の画面で嘘になる。`amount` も
 * 0 と上限の二通りで落ちる。断定できるのは、全てのスキーマで決まりが一致している
 * 項目（`email` の形式、`password` の 8 文字）だけ。
 */
const NAMED_VALIDATION_FIELDS = new Set([
  'amount',
  'code',
  'display_name',
  'email',
  'name',
  'password',
  'reason',
  'username',
])

/**
 * 例外を i18n の翻訳キーへ変換する。
 *
 * バックエンドはエラーコードだけを返すので、画面側の扱いは常に
 * 「`error.<code>` を引く」に落ちる。各ページで同じ分岐を書かないための入口。
 * 入力検証の失敗だけは、落ちた項目の文言（`error.invalid_password` 等）を優先する。
 */
export function errorMessageKey(error: unknown): string {
  if (!(error instanceof ApiError)) return 'error.unknown_error'
  if (error.code === VALIDATION_ERROR_CODE) {
    const field = error.fields.find((name) => NAMED_VALIDATION_FIELDS.has(name))
    if (field !== undefined) return `error.invalid_${field}`
  }
  return `error.${error.code}`
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access)
  localStorage.setItem(REFRESH_KEY, refresh)
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

export function hasTokens(): boolean {
  return localStorage.getItem(ACCESS_KEY) !== null
}

function detailOf(body: unknown): unknown {
  return body && typeof body === 'object' ? (body as Record<string, unknown>).detail : undefined
}

function extractErrorCode(body: unknown): string {
  const detail = detailOf(body)
  if (detail && typeof detail === 'object') {
    const code = (detail as Record<string, unknown>).error
    if (typeof code === 'string') return code
  }
  if (typeof detail === 'string') return detail
  return 'unknown_error'
}

/** 入力検証で落ちた項目名。バックエンドは名前だけを返す（値は載らない）。 */
function extractErrorFields(body: unknown): string[] {
  const detail = detailOf(body)
  if (!detail || typeof detail !== 'object') return []
  const fields = (detail as Record<string, unknown>).fields
  return Array.isArray(fields)
    ? fields.filter((name): name is string => typeof name === 'string')
    : []
}

/** ``/api/auth/refresh`` の応答。 */
interface TokenPair {
  access_token: string
  refresh_token: string
}

async function tryRefresh(): Promise<boolean> {
  const refresh = localStorage.getItem(REFRESH_KEY)
  if (!refresh) return false
  const response = await fetch('/api/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refresh }),
  })
  if (!response.ok) {
    clearTokens()
    return false
  }
  const pair = (await response.json()) as TokenPair
  setTokens(pair.access_token, pair.refresh_token)
  return true
}

async function request<T>(method: string, path: string, body?: unknown, retry = true): Promise<T> {
  const headers: Record<string, string> = {}
  const access = localStorage.getItem(ACCESS_KEY)
  if (access) headers['Authorization'] = `Bearer ${access}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const init: RequestInit = { method, headers }
  if (body !== undefined) init.body = JSON.stringify(body)

  const response = await fetch(path, init)

  if (response.status === 401 && retry && (await tryRefresh())) {
    return request<T>(method, path, body, false)
  }
  if (!response.ok) {
    let payload: unknown = null
    try {
      payload = await response.json()
    } catch {
      /* 非 JSON 応答 */
    }
    throw new ApiError(response.status, extractErrorCode(payload), extractErrorFields(payload))
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}
