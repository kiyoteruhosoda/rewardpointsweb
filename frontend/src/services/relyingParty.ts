/**
 * RP ID（`WEBAUTHN_RP_ID`）と、いま開いている URL の噛み合わせ。
 *
 * ブラウザは `navigator.credentials` を呼んだ時点で「`rp.id` が呼び出し元の実効
 * ドメインと一致するか、その上位ドメインであること」を確かめ、外れていれば失敗
 * させる。同じ規則をこちら側にも置き、2 つに使う。
 *
 * 1. パスキーを作る・使う前に噛み合わせを見る（原因の分かる失敗にする。ブラウザ
 *    が投げる例外の名前は実装によって違い、取り消しと見分けが付かないことがある）
 * 2. 設定画面で「その値では、いま開いている URL からは使えない」と出す
 *
 * 保存する値どうしの整合（RP ID とオリジン）はサーバーが見る
 * （`bounded_contexts/account_security/domain/services/relying_party_configuration.py`）。
 * **開いている URL は画面側にしか分からない**ので、その照合だけをここで行う。
 */

/** 照合の相手。`window.location` をそのまま渡せる形にしておく。 */
export interface BrowsingLocation {
  hostname: string
  origin: string
  protocol: string
}

/** パスキーの設定のうち、開いている URL と突き合わせる 2 つ。 */
export interface RelyingPartySettings {
  rpId: string
  origin: string
}

// ラベルは英数字とハイフン。国際化ドメインは punycode（`xn--`）へ変換済みの形で持つ。
const LABEL = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/

// ブラウザが安全な文脈として例外的に扱うホスト（http でもパスキーが動く）。
const HTTP_ALLOWED_HOSTS = ['localhost']

// ブラウザの送るオリジンには既定ポートが付かない（`https://example.com:443` ではなく
// `https://example.com`）。サーバー側の正規化と同じ落とし方をしないと、実際には
// 動いている設定を「食い違っている」と誤って出してしまう。
const DEFAULT_PORTS: Record<string, number> = { http: 80, https: 443 }

// `scheme://host[:port]` の切り出し。ホストは IPv6 の `[...]` 表記も受ける。
const ORIGIN = /^(https?):\/\/(\[[^\]]+\]|[^/:]+)(?::(\d+))?$/

/** 比較のために揃える（前後の空白・大文字・末尾のドットを落とす）。 */
export function normalizeDomain(value: string): string {
  return value.trim().replace(/\.+$/, '').toLowerCase()
}

/**
 * 比較のために揃える（前後の空白・大文字・末尾のスラッシュを落とす）。
 *
 * 既定ポートとホスト末尾のドットも落とす。サーバーは保存された値をそのまま持ち、
 * RP を組み立てるときに正規化する（`relying_party_configuration.py`）。ここで
 * 揃えないと `https://example.com:443` のような**動く設定**を食い違いとして出す。
 */
export function normalizeOrigin(value: string): string {
  const trimmed = value.trim().replace(/\/+$/, '').toLowerCase()
  const parts = ORIGIN.exec(trimmed)
  if (!parts) return trimmed
  const [, scheme = '', host = '', port] = parts
  const explicitPort =
    port !== undefined && Number(port) !== DEFAULT_PORTS[scheme] ? `:${port}` : ''
  return `${scheme}://${host.replace(/\.+$/, '')}${explicitPort}`
}

/**
 * `hostname` から見て `rpId` が使えるか。
 *
 * 使えるのは「同じドメイン」か「その上位ドメイン」だけ。ただし上位ドメインが
 * `com` のような 1 ラベルだけの公開サフィックスなら、ブラウザが拒む。
 */
export function isRelyingPartyIdUsable(rpId: string, hostname: string): boolean {
  const identifier = normalizeDomain(rpId)
  const host = normalizeDomain(hostname)
  if (!identifier || !host) return false
  if (host === identifier) return true
  if (!identifier.includes('.')) return false
  return host.endsWith(`.${identifier}`)
}

/**
 * RP ID にできる形か（ドメイン名か）。
 *
 * IP アドレスやポート付きの値は RP ID にできない。ラベルの綴りも見るので、
 * `192.168.1.5` のような数字だけのホストはここで落ちる。
 */
export function isDomainName(value: string): boolean {
  const identifier = normalizeDomain(value)
  if (!identifier) return false
  const labels = identifier.split('.')
  // 数字とドットだけなら IPv4。IPv6 はコロンを含む（ラベルの綴りで落ちる）。
  if (labels.every((label) => /^[0-9]+$/.test(label))) return false
  return labels.every((label) => LABEL.test(label))
}

/**
 * その URL では、設定を直したところでパスキーを使えるか。
 *
 * パスキーは安全な文脈（https、例外として localhost）でしか動かず、RP ID には
 * ドメイン名しか指定できない。IP アドレスで開いている場合は、その URL に合わせた
 * 設定を作っても保存できない（サーバーが弾く）ので、直し方の案内を変える。
 */
export function supportsPasskeys(location: BrowsingLocation): boolean {
  const host = normalizeDomain(location.hostname)
  if (!isDomainName(host)) return false
  const scheme = location.protocol.replace(':', '').toLowerCase()
  return scheme === 'https' || HTTP_ALLOWED_HOSTS.includes(host)
}

/** その URL を開いたまま使える設定（設定画面の「合わせる」の中身）。 */
export function relyingPartyForLocation(location: BrowsingLocation): RelyingPartySettings {
  return { rpId: normalizeDomain(location.hostname), origin: normalizeOrigin(location.origin) }
}

/** その設定のまま、その URL からパスキーを使えるか。 */
export function matchesLocation(
  settings: RelyingPartySettings,
  location: BrowsingLocation,
): boolean {
  const expected = relyingPartyForLocation(location)
  return (
    isRelyingPartyIdUsable(settings.rpId, location.hostname) &&
    normalizeOrigin(settings.origin) === expected.origin
  )
}

/**
 * サーバーが返したオプションから RP ID を取り出す。
 *
 * 登録（create）は `rp.id`、認証（get）は `rpId` に入る。省略されている場合は
 * ブラウザが開いているドメインを使うため、噛み合わせは常に成る（空文字を返し、
 * 呼び出し側が「確かめる必要なし」として扱う）。
 */
export function relyingPartyIdOf(publicKey: Record<string, unknown>): string {
  const rp = publicKey.rp
  if (rp !== null && typeof rp === 'object') {
    const id = (rp as { id?: unknown }).id
    if (typeof id === 'string') return id
  }
  return typeof publicKey.rpId === 'string' ? publicKey.rpId : ''
}
