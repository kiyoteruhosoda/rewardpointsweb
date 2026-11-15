/**
 * The celebration when a pet reaches a new stage (ADR-0061): the pet bounces in big with
 * sparkles and the new stage's name. Shown once per screen for each stage up. The motion is
 * CSS only and stops for people who ask for reduced motion.
 */
import { useEffect, useRef } from 'react'

import { useI18n } from '../i18n'
import type { PetSpecies } from '../services/pet'
import { SparklesArt } from './GachaArt'
import { PetArt } from './PetArt'

interface Props {
  species: PetSpecies
  stage: number
  onClose: () => void
}

export function PetCelebration({ species, stage, onClose }: Props) {
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

  return (
    <div className="gacha-reveal-backdrop">
      <div
        className="gacha-reveal pet-celebration"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pet-celebration-title"
      >
        <div className="gacha-reveal-stage">
          <SparklesArt />
          <PetArt species={species} stage={stage} className="pet-celebration-art" />
        </div>
        <h2 id="pet-celebration-title" className="gacha-reveal-title">
          {t('pet.celebrateTitle')}
        </h2>
        <p className="pet-celebration-stage">
          {t('pet.celebrateStage', { stage: t(`pet.stage.${stage}`) })}
        </p>
        <button ref={closeRef} type="button" className="gacha-reveal-close" onClick={onClose}>
          {t('pet.celebrateClose')}
        </button>
      </div>
    </div>
  )
}
