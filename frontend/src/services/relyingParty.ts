/**
 * Whether the RP ID (`WEBAUTHN_RP_ID`) fits the URL currently open.
 *
 * When `navigator.credentials` is called, the browser checks that "`rp.id` equals the caller's effective
 * domain or is a parent domain of it", and fails if not. The same rule is
 * kept on this side and used for two things.
 *
 * 1. Check the fit before creating or using a passkey (so the failure explains its cause; the name of the
 *    exception the browser throws varies by implementation and can be indistinguishable from a cancel)
 * 2. Show in the settings screen that "with that value it cannot be used from the URL currently open"
 *
 * Consistency between the stored values (RP ID and origins) is checked by the server
 * (`bounded_contexts/account_security/domain/services/relying_party_configuration.py`).
 * **Only the client knows the URL being opened**, so only that comparison is done here.
 */

/** What to compare against. Shaped so `window.location` can be passed as-is. */
export interface BrowsingLocation {
  hostname: string
  origin: string
  protocol: string
}

/** The two passkey settings compared against the open URL. */
export interface RelyingPartySettings {
  rpId: string
  origin: string
}

// Labels are alphanumerics and hyphens. Internationalized domains are held in punycode (`xn--`) form.
const LABEL = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/

// Hosts browsers treat as a secure context by exception (passkeys work even over http).
const HTTP_ALLOWED_HOSTS = ['localhost']

// Origins sent by the browser carry no default port (`https://example.com`, not
// `https://example.com:443`). Unless we strip it the same way as the server normalization,
// a setting that actually works would be wrongly reported as "mismatched".
const DEFAULT_PORTS: Record<string, number> = { http: 80, https: 443 }

// Extracts `scheme://host[:port]`. The host also accepts IPv6 `[...]` notation.
const ORIGIN = /^(https?):\/\/(\[[^\]]+\]|[^/:]+)(?::(\d+))?$/

/** Normalize for comparison (drop surrounding whitespace, uppercase and a trailing dot). */
export function normalizeDomain(value: string): string {
  return value.trim().replace(/\.+$/, '').toLowerCase()
}

/**
 * Normalize for comparison (drop surrounding whitespace, uppercase and a trailing slash).
 *
 * Also drop the default port and a trailing dot on the host. The server keeps the stored value as-is and
 * normalizes it when building the RP (`relying_party_configuration.py`). Without normalizing
 * here, a **working setting** like `https://example.com:443` would be reported as a mismatch.
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
 * Whether `rpId` can be used from `hostname`.
 *
 * Only "the same domain" or "a parent domain of it" works. But if the parent domain is
 * a single-label public suffix like `com`, the browser rejects it.
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
 * Whether it can be an RP ID (whether it is a domain name).
 *
 * IP addresses and values with a port cannot be an RP ID. Label spelling is checked too, so
 * a digits-only host like `192.168.1.5` fails here.
 */
export function isDomainName(value: string): boolean {
  const identifier = normalizeDomain(value)
  if (!identifier) return false
  const labels = identifier.split('.')
  // Only digits and dots means IPv4. IPv6 contains colons (fails on label spelling).
  if (labels.every((label) => /^[0-9]+$/.test(label))) return false
  return labels.every((label) => LABEL.test(label))
}

/**
 * Whether passkeys can be used from that URL once the settings are fixed.
 *
 * Passkeys only work in a secure context (https, with localhost as an exception), and an RP ID
 * can only be a domain name. When opened by IP address, a setting matched to that URL
 * cannot be saved (the server rejects it), so the guidance on how to fix it changes.
 */
export function supportsPasskeys(location: BrowsingLocation): boolean {
  const host = normalizeDomain(location.hostname)
  if (!isDomainName(host)) return false
  const scheme = location.protocol.replace(':', '').toLowerCase()
  return scheme === 'https' || HTTP_ALLOWED_HOSTS.includes(host)
}

/** Settings that work with that URL open (what "match" does in the settings screen). */
export function relyingPartyForLocation(location: BrowsingLocation): RelyingPartySettings {
  return { rpId: normalizeDomain(location.hostname), origin: normalizeOrigin(location.origin) }
}

/** Whether passkeys can be used from that URL with those settings as they are. */
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
 * Extract the RP ID from the options returned by the server.
 *
 * Registration (create) puts it in `rp.id`, authentication (get) in `rpId`. When omitted
 * the browser uses the open domain, so it always fits (return an empty string, which
 * the caller treats as "no need to check").
 */
export function relyingPartyIdOf(publicKey: Record<string, unknown>): string {
  const rp = publicKey.rp
  if (rp !== null && typeof rp === 'object') {
    const id = (rp as { id?: unknown }).id
    if (typeof id === 'string') return id
  }
  return typeof publicKey.rpId === 'string' ? publicKey.rpId : ''
}
