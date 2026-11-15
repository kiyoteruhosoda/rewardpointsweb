/**
 * The pet on a display device (ADR-0061, ADR-0047).
 *
 * Nobody taps the display, so a stage up is celebrated in place: the pet bounces with a
 * banner for a while and then settles. Like every other screen, the display remembers the
 * last stage it showed per ledger and celebrates each stage up once.
 */
import { useEffect, useState } from 'react'

import { useI18n } from '../i18n'
import { takeStageUp, type Pet } from '../services/pet'
import { PetArt } from './PetArt'

/** How long the in-place celebration lasts. */
export const DISPLAY_CELEBRATION_MS = 30 * 1000

interface Props {
  ledgerId: number
  name: string
  pet: Pet
}

export function DisplayPet({ ledgerId, name, pet }: Props) {
  const { t } = useI18n()
  const [celebrating, setCelebrating] = useState(false)
  const chosen = pet.species !== null

  useEffect(() => {
    // Without a species the pet is drawn as an egg: remember stage 0 so choosing shows it hatch
    if (!takeStageUp(ledgerId, chosen ? pet.stage : 0) || !chosen) return
    setCelebrating(true)
    const timer = window.setTimeout(() => {
      setCelebrating(false)
    }, DISPLAY_CELEBRATION_MS)
    return () => {
      window.clearTimeout(timer)
    }
  }, [chosen, ledgerId, pet.stage])

  const toNext = pet.next_threshold === null ? null : pet.next_threshold - pet.earned
  return (
    <div className={celebrating ? 'display-pet is-celebrating' : 'display-pet'}>
      <PetArt species={pet.species} stage={pet.stage} className="display-pet-art" />
      <div className="display-pet-info">
        {celebrating && (
          <p className="display-pet-banner" role="status">
            {t('display.petGrew', { name })}
          </p>
        )}
        <p className="display-pet-stage">{t(`pet.stage.${chosen ? pet.stage : 0}`)}</p>
        <p className="display-note">
          {toNext === null ? t('pet.final') : t('pet.toNext', { points: toNext })}
        </p>
      </div>
    </div>
  )
}
