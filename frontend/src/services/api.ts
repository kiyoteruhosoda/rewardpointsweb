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
/**
 * 表示端末（サイネージ）の資格情報（ADR-0047）。ペアリングで 1 度だけ受け取る。
 *
 * ⚠ **ログアウトやセッションの失効では消さない**（`clearTokens` の外）。消すのは
 * サーバーが「外された・失効した」と答えたときだけ。届かないだけで消すと、
 * リリースのたびに端末がペアリングからやり直しになる（ADR-0046 と同じ考え）。
 */
const DISPLAY_CREDENTIAL_KEY = 'display_credential'

/**
 * オフライン閲覧用に Service Worker が閲覧系 GET を保存するキャッシュ名
 * （ADR-0015）。`frontend/vite.config.ts` の `runtimeCaching.cacheName` と対。
 * 応答には個人のポイント記録が入るため、トークンを消すときに一緒に消す。
 */
const OFFLINE_VIEW_CACHE = 'offline-views'

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

export function displayCredential(): string | null {
  return localStorage.getItem(DISPLAY_CREDENTIAL_KEY)
}

export function rememberDisplayCredential(credential: string): void {
  localStorage.setItem(DISPLAY_CREDENTIAL_KEY, credential)
}

export function forgetDisplayCredential(): void {
  localStorage.removeItem(DISPLAY_CREDENTIAL_KEY)
}

/** 表示端末のセッションを開いた結果。 */
export type DisplaySessionOutcome = 'opened' | 'removed' | 'unreachable'

/**
 * 端末の資格情報を 5 分のアクセストークンに換える（ADR-0047）。
 *
 * 401 は「外された・失効した」なので資格情報を消す（ペアリングからやり直し）。
 * それ以外の失敗は届かないだけとみなし、資格情報を残す。
 */
export async function openDisplaySession(): Promise<DisplaySessionOutcome> {
  const credential = displayCredential()
  if (!credential) return 'removed'
  let response: Response
  try {
    response = await fetch('/api/display/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_credential: credential }),
    })
  } catch {
    return 'unreachable'
  }
  if (response.status === 401) {
    forgetDisplayCredential()
    clearTokens()
    return 'removed'
  }
  if (!response.ok) return 'unreachable'
  const session = (await response.json()) as { access_token: string }
  // リフレッシュトークンは無い。切れたら資格情報で取り直す
  localStorage.setItem(ACCESS_KEY, session.access_token)
  localStorage.removeItem(REFRESH_KEY)
  return 'opened'
}

/**
 * オフライン閲覧キャッシュを消す（ADR-0015）。
 *
 * キャッシュは URL だけで引かれ、Authorization ヘッダーを見ない。誰の応答かを
 * 区別できないので、ユーザーが替わり得る節目（ログアウト・セッション失効・
 * ログイン成功）で丸ごと消す。
 */
export async function clearOfflineViewCache(): Promise<void> {
  if (typeof caches !== 'undefined') await caches.delete(OFFLINE_VIEW_CACHE)
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
  // ログアウト・セッション失効の後、同じブラウザの別ユーザーに前のユーザーの
  // 残高・履歴が見えないようにする（ADR-0015）。
  void clearOfflineViewCache()
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
  // 表示端末はリフレッシュトークンを持たない。資格情報で取り直す（ADR-0047）
  if (displayCredential()) return (await openDisplaySession()) === 'opened'
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

async function requestResponse(
  method: string,
  path: string,
  body?: unknown,
  retry = true,
): Promise<Response> {
  const headers: Record<string, string> = {}
  const access = localStorage.getItem(ACCESS_KEY)
  if (access) headers['Authorization'] = `Bearer ${access}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const init: RequestInit = { method, headers }
  if (body !== undefined) init.body = JSON.stringify(body)

  const response = await fetch(path, init)

  if (response.status === 401 && retry && (await tryRefresh())) {
    return requestResponse(method, path, body, false)
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
  return response
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await requestResponse(method, path, body)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** 応答本体と、その応答が作られた時刻。 */
export interface Fetched<T> {
  data: T
  /**
   * 応答の ``Date`` ヘッダー。オフラインでは Service Worker が保存時のヘッダー
   * ごと応答を返すため、この時刻だけが「いつの情報か」を示せる（ADR-0015）。
   * ヘッダーが無い・読めない応答では null。
   */
  fetchedAt: Date | null
}

function fetchedAtOf(response: Response): Date | null {
  const value = response.headers.get('date')
  if (!value) return null
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

async function requestFetched<T>(path: string): Promise<Fetched<T>> {
  const response = await requestResponse('GET', path)
  return { data: (await response.json()) as T, fetchedAt: fetchedAtOf(response) }
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  /** オフライン閲覧に対応する画面向け。取得時刻（Date ヘッダー）を添えて返す。 */
  getFetched: <T>(path: string) => requestFetched<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
}
