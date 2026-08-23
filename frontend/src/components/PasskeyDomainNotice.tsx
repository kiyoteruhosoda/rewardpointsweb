/**
 * パスキーの設定が、いま開いている URL と噛み合っているかを見せる枠。
 *
 * RP ID とオリジンは互いに整合していても（保存の時点でサーバーが確かめる）、
 * 実際に開く URL と食い違っていれば、失敗するのは設定画面ではなく利用者の
 * 「パスキーを追加」になる。開いている URL はブラウザにしか分からないため、
 * 設定を直せる人がその画面を開いているあいだに照らし合わせて出す。
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
  /** いま画面に入っている値（保存前の編集も含む）。 */
  settings: RelyingPartySettings
  /** 環境変数で固定されていて、画面からは直せない。 */
  envLocked: boolean
  /** 照らし合わせる相手。画面からは `window.location` を渡す。 */
  location: BrowsingLocation
  /** 「合わせる」を押されたとき。入力欄へ差し込むだけで、保存はしない。 */
  onApply: (settings: RelyingPartySettings) => void
}

/** 値が空のときに、空白ではなく「未設定」と分かる形で出す。 */
function orPlaceholder(value: string): string {
  return value.trim() || '—'
}

export function PasskeyDomainNotice({ settings, envLocked, location, onApply }: Props) {
  const { t } = useI18n()
  if (matchesLocation(settings, location)) return null

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
      <PasskeyDomainRemedy
        envLocked={envLocked}
        location={location}
        expected={expected}
        onApply={onApply}
      />
    </div>
  )
}

/** 直し方。この URL に合わせられるか・どこで直すかで変わる。 */
function PasskeyDomainRemedy({
  envLocked,
  location,
  expected,
  onApply,
}: {
  envLocked: boolean
  location: BrowsingLocation
  expected: RelyingPartySettings
  onApply: (settings: RelyingPartySettings) => void
}) {
  const { t } = useI18n()
  // IP アドレスや http で開いている URL には合わせられない（保存が弾かれる）。
  // 押せば直るように見えるボタンは出さず、開き直す先を伝える。
  if (!supportsPasskeys(location)) return <p>{t('config.passkeyDomainUnusableUrl')}</p>
  if (envLocked) return <p>{t('config.passkeyDomainEnvLocked')}</p>
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
