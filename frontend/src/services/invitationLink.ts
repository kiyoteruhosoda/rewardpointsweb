/**
 * 招待コードを載せた URL の組み立てと読み取り。
 *
 * コードだけを渡すと、受け取った人は「どの画面を開き、どこへ打ち込むか」を別に
 * 教わらなければならず、打ち間違いも起きる。参加の入口へコードを載せた URL を渡せば、
 * 開いた時点でコードが入った状態から始まる。
 *
 * **コードは断片（`#code=...`）で運ぶ。クエリ（`?code=`）に置かない**（ADR-0025）。
 * 断片はブラウザがサーバーへ送らないので、リバースプロキシのアクセスログにも
 * リクエストログにも残らない。コードは有効な間そのまま使える capability で、
 * DB にハッシュしか置いていない意味が、経路の途中で平文が残ると失われる。
 *
 * 受け取り側の 3 画面（`/join`・`/login`・`/families`）はどれもここを通してコードを
 * 読み書きする。片方だけクエリへ戻ると、そこから先が平文でログに載る。
 *
 * 差し出す URL の宛先は、発行した親がいま見ているのと同じ入口（`origin`）にする。
 * 設定の `APP_BASE_URL` はメール本文の生成元で、既定は空。空のまま使うと開けない
 * URL を渡すことになるので、ここでは参照しない。
 *
 * SSO は IdP の画面を挟むので断片が失われる。**そのぶんをクエリで補わない**——
 * `redirect_to` に載せた時点でコードはサーバーへ届き、アクセスログにも
 * `sso_login_sessions` にも平文で残る。往復のあいだは同じタブの
 * `sessionStorage` に預ける（`rememberInvitationCode` / `takeRememberedInvitationCode`）。
 */

/** アカウントを作って家族へ加わる画面（未認証で開ける）。 */
const JOIN_PATH = '/join'
/** すでにアカウントを持つ人が先に通る画面。 */
const SIGN_IN_PATH = '/login'
/** ログイン後にコードを使う画面（家族への参加）。 */
const ACCEPT_PATH = '/families'

const CODE_KEY = 'code'

/** IdP への往復のあいだコードを預ける場所（同じタブ限り）。 */
const PENDING_KEY = 'pendingInvitationCode'

/** 断片へコードを載せる。空なら付けない（付けても行き先で拾うものが無い）。 */
function withCode(path: string, code: string): string {
  const trimmed = code.trim()
  if (!trimmed) return path
  return `${path}#${CODE_KEY}=${encodeURIComponent(trimmed)}`
}

/** 招待を受け取った人が最初に開く画面（アカウントを作る）。 */
export function invitationJoinPath(code: string): string {
  return withCode(JOIN_PATH, code)
}

/** すでにアカウントを持つ人がコードを持ったままログインへ回るときの行き先。 */
export function invitationSignInPath(code: string): string {
  return withCode(SIGN_IN_PATH, code)
}

/** ログインを終えた人がコードを使う画面。 */
export function invitationAcceptPath(code: string): string {
  return withCode(ACCEPT_PATH, code)
}

/**
 * 受け取った人へそのまま渡せる URL。
 *
 * @param origin 発行した画面の出所（`window.location.origin`）。末尾の `/` は落とす。
 */
export function invitationUrl(code: string, origin: string): string {
  return `${origin.replace(/\/+$/, '')}${invitationJoinPath(code)}`
}

/**
 * URL の断片からコードを取り出す。
 *
 * @param hash `useLocation().hash`（`#code=...` または空）。
 */
export function readInvitationCode(hash: string): string {
  return new URLSearchParams(hash.replace(/^#/, '')).get(CODE_KEY)?.trim() ?? ''
}

/**
 * IdP への往復のあいだコードを預ける（同じタブの中だけ）。
 *
 * 断片はブラウザが IdP へ送らないので、戻ってきたときには消えている。`localStorage`
 * ではなく `sessionStorage` を使うのは、タブを閉じれば消えてほしいから（コードは
 * capability そのもの）。書けない設定のブラウザでは黙って諦める——コードを失うと
 * 参加の画面で打ち直しになるだけで、ログインそのものは進む。
 */
export function rememberInvitationCode(code: string): void {
  const trimmed = code.trim()
  try {
    if (trimmed) sessionStorage.setItem(PENDING_KEY, trimmed)
    else sessionStorage.removeItem(PENDING_KEY)
  } catch {
    // 保存できない設定のブラウザ（プライベートモード等）。諦める
  }
}

/** 預けたコードを取り出す（1 回限り。取り出したら消す）。 */
export function takeRememberedInvitationCode(): string {
  try {
    const stored = sessionStorage.getItem(PENDING_KEY)
    sessionStorage.removeItem(PENDING_KEY)
    return stored?.trim() ?? ''
  } catch {
    return ''
  }
}
