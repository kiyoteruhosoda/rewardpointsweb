/**
 * The result of one draw, shown over the screen (ADR-0060).
 *
 * A capsule drops in, pops open, and the prize comes out big with sparkles. A miss gets a softer
 * "better luck next time". The motion is CSS only and stops for people who ask for reduced motion
 * (the prize is shown straight away).
 *
 * The capsule colour matches the prize's colour in the machine's list, so a child learns which
 * colour means which prize.
 */
import { useEffect, useRef } from 'react'

import { useI18n } from '../i18n'
import type { GachaDraw } from '../services/gacha'
import { CapsuleArt, SparklesArt } from './GachaArt'

interface Props {
  draw: GachaDraw
  /** Colour of the capsule (the prize's colour in the list). */
  color: string
  balance: number
  onClose: () => void
}

export function GachaReveal({ draw, color, balance, onClose }: Props) {
  const { t } = useI18n()
  const closeRef = useRef<HTMLButtonElement>(null)

  // Move focus into the dialog, and let Escape close it
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

  return (
    <div className="gacha-reveal-backdrop">
      <div
        className={draw.is_miss ? 'gacha-reveal is-miss' : 'gacha-reveal'}
        role="dialog"
        aria-modal="true"
        aria-labelledby="gacha-reveal-title"
      >
        <div className="gacha-reveal-stage">
          {!draw.is_miss && <SparklesArt />}
          <div className="gacha-reveal-capsule">
            <CapsuleArt color={color} opening />
          </div>
          <p className="gacha-reveal-prize">{draw.prize_name}</p>
        </div>
        <h2 id="gacha-reveal-title" className="gacha-reveal-title">
          {draw.is_miss ? t('gacha.resultMiss') : t('gacha.resultTitle')}
        </h2>
        <p className="gacha-reveal-meta">
          {t('gacha.resultFrom', { name: draw.gacha_name })}
          {' · '}
          {t('gacha.resultBalance', { points: balance })}
        </p>
        <button ref={closeRef} type="button" className="gacha-reveal-close" onClick={onClose}>
          {draw.is_miss ? t('gacha.resultCloseMiss') : t('gacha.resultClose')}
        </button>
      </div>
    </div>
  )
}
