/**
 * All eleven prizes of a bundle at the end (task #1047), in the order they came out.
 * The free one is marked as the bonus.
 */
import { useEffect, useRef } from 'react'

import { useI18n } from '../i18n'
import type { GachaDraw } from '../services/gacha'

interface Props {
  draws: GachaDraw[]
  /** Colour of each draw's capsule, in the same order. */
  colors: string[]
  balance: number
  onClose: () => void
}

export function GachaBundleSummary({ draws, colors, balance, onClose }: Props) {
  const { t } = useI18n()
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  const won = draws.filter((draw) => !draw.is_miss).length
  return (
    <div className="gacha-reveal-backdrop">
      <div
        className="gacha-reveal gacha-bundle-summary"
        role="dialog"
        aria-modal="true"
        aria-labelledby="gacha-bundle-summary-title"
      >
        <h2 id="gacha-bundle-summary-title" className="gacha-reveal-title">
          {t('gacha.bundleSummaryTitle', { count: won })}
        </h2>
        <ol className="gacha-bundle-list">
          {draws.map((draw, index) => (
            <li key={draw.id} className={draw.is_miss ? 'is-miss' : undefined}>
              <span
                className="gacha-prize-dot"
                style={{ background: colors[index] ?? 'var(--slot-line)' }}
                aria-hidden="true"
              />
              <span className="gacha-bundle-prize">{draw.prize_name}</span>
              {draw.is_bonus && <span className="gacha-bundle-bonus">{t('gacha.bonus')}</span>}
            </li>
          ))}
        </ol>
        <p className="gacha-reveal-meta">{t('gacha.resultBalance', { points: balance })}</p>
        <button ref={closeRef} type="button" className="gacha-reveal-close" onClick={onClose}>
          {t('gacha.resultClose')}
        </button>
      </div>
    </div>
  )
}
