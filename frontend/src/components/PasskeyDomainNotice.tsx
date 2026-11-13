/**
 * Box showing whether the passkey settings match the URL currently open.
 *
 * Even if the RP ID and origin are consistent with each other (the server checks on save), if they
 * differ from the URL actually opened, what fails is not the settings screen but the user's
 * "add passkey". Only the browser knows the open URL, so compare them and show the result
 * while someone who can fix the settings has that screen open.
 */
import { useI18n } from '../i18n'
import {
  matchesLocation,
  relyingPartyForLocation,
  supportsPasskeys,
  type BrowsingLocation,
  type RelyingPartySettings,
} from '../services/relyingParty'

interface Props {
  /** Values currently in the form (including unsaved edits). */
  settings: RelyingPartySettings
  /** What to compare against. The screen passes `window.location`. */
  location: BrowsingLocation
  /** When "match" is pressed. Only fills the inputs; does not save. */
  onApply: (settings: RelyingPartySettings) => void
}

/** Shows an empty value as recognisably "not set" rather than blank. */
function orPlaceholder(value: string): string {
  return value.trim() || '—'
}

export function PasskeyDomainNotice({ settings, location, onApply }: Props) {
  const { t } = useI18n()
  // Even when values match, passkeys may **not work at all** on that URL
  // (http domain names, IP addresses). Looking only at the match, nothing would be shown
  // in that case and only "add passkey" would fail. Check whether the URL itself works first.
  if (supportsPasskeys(location) && matchesLocation(settings, location)) return null

  const expected = relyingPartyForLocation(location)
  return (
    <div className="notice">
      <p>
        {t('config.passkeyDomainMismatch', {
          currentOrigin: expected.origin,
          rpId: orPlaceholder(settings.rpId),
          origin: orPlaceholder(settings.origin),
        })}
      </p>
      <PasskeyDomainRemedy location={location} expected={expected} onApply={onApply} />
    </div>
  )
}

/** How to fix it. Depends on whether we can match this URL and where to fix it. */
function PasskeyDomainRemedy({
  location,
  expected,
  onApply,
}: {
  location: BrowsingLocation
  expected: RelyingPartySettings
  onApply: (settings: RelyingPartySettings) => void
}) {
  const { t } = useI18n()
  // Cannot match a URL opened by IP address or over http (saving is rejected).
  // Don't show a button that looks like it would fix things; tell them where to reopen instead.
  if (!supportsPasskeys(location)) return <p>{t('config.passkeyDomainUnusableUrl')}</p>
  // ⚠ **The branch for values fixed by environment variables is gone** (ADR: the screen value wins).
  //   Even if compose has a value, matching and saving here wins over it.
  return (
    <button
      type="button"
      onClick={() => {
        onApply(expected)
      }}
    >
      {t('config.passkeyDomainApply')}
    </button>
  )
}
