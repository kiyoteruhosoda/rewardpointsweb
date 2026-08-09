/**
 * 招待コードを載せた URL の組み立て。
 *
 * コードだけを渡すと、受け取った人は「どの画面を開き、どこへ打ち込むか」を別に
 * 教わらなければならず、打ち間違いも起きる。参加の入口（`/join`）へコードを載せた
 * URL を渡せば、開いた時点でコードが入った状態から始まる
 * （`RedeemInvitationPage` が `?code=` を読む）。すでにアカウントを持つ人が
 * ログインへ回った場合も、コードはその先の家族の画面まで運ばれる。
 *
 * 差し出す URL の宛先は、発行した親がいま見ているのと同じ入口（`origin`）にする。
 * 設定の `APP_BASE_URL` はメール本文の生成元で、既定は空。空のまま使うと開けない
 * URL を渡すことになるので、ここでは参照しない。
 */

/** アカウントを作って家族へ加わる画面（未認証で開ける）。 */
export const JOIN_PATH = '/join'

/** 参加の入口までのパス。コードは URL に載せるため必ずエスケープする。 */
export function invitationJoinPath(code: string): string {
  return `${JOIN_PATH}?code=${encodeURIComponent(code)}`
}

/**
 * 受け取った人へそのまま渡せる URL。
 *
 * @param origin 発行した画面の出所（`window.location.origin`）。末尾の `/` は落とす。
 */
export function invitationUrl(code: string, origin: string): string {
  return `${origin.replace(/\/+$/, '')}${invitationJoinPath(code)}`
}
