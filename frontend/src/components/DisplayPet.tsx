/**
 * The pet on a display device (ADR-0061, ADR-0047).
 *
 * Nobody taps the display, so a stage up is celebrated in place: the pet bounces with a
 * banner for a while and then settles (an egg cracks open when it hatches). Like every other
 * screen, the display remembers the last stage it showed per ledger and celebrates each stage
 * up once.
 *
 * The display only looks at care (task #1128): it shows the pet's mood, and when someone has
 * cared for it since the last read, the pet plays that care's move with a banner.
 */
import { useEffect, useState } from 'react'

import { useI18n } from '../i18n'
import { takeNewCare, takeStageUp, type Pet, type PetCareKind } from '../services/pet'
import { PetArt } from './PetArt'

/** How long the in-place celebration lasts. */
export const DISPLAY_CELEBRATION_MS = 30 * 1000
/** How long the reaction to a care stays (the move plays once; the banner stays). */
export const DISPLAY_CARE_REACTION_MS = 20 * 1000

interface Props {
  ledgerId: number
  name: string
  pet: Pet
}

export function DisplayPet({ ledgerId, name, pet }: Props) {
  const { t } = useI18n()
  // null: no celebration. Otherwise whether it hatched this time
  const [celebration, setCelebration] = useState<{ hatching: boolean } | null>(null)
  const [reaction, setReaction] = useState<PetCareKind | null>(null)
  const chosen = pet.species !== null
  const lastCaredAt = pet.care?.last_cared_at ?? null
  const lastKind = pet.care?.last_kind ?? null

  useEffect(() => {
    // Without a species the pet is drawn as an egg: remember stage 0 so choosing shows it hatch
    const from = takeStageUp(ledgerId, chosen ? pet.stage : 0)
    if (from === null || !chosen) return
    setCelebration({ hatching: from === 0 })
    const timer = window.setTimeout(() => {
      setCelebration(null)
    }, DISPLAY_CELEBRATION_MS)
    return () => {
      window.clearTimeout(timer)
    }
  }, [chosen, ledgerId, pet.stage])

  useEffect(() => {
    if (lastKind === null || !takeNewCare(ledgerId, lastCaredAt)) return
    setReaction(lastKind)
    const timer = window.setTimeout(() => {
      setReaction(null)
    }, DISPLAY_CARE_REACTION_MS)
    return () => {
      window.clearTimeout(timer)
    }
  }, [ledgerId, lastCaredAt, lastKind])

  const toNext = pet.next_threshold === null ? null : pet.next_threshold - pet.earned
  const classes = ['display-pet']
  if (celebration !== null) classes.push('is-celebrating')
  if (reaction !== null) classes.push('is-reacting')
  return (
    <div className={classes.join(' ')}>
      <PetArt
        species={pet.species}
        stage={pet.stage}
        mood={celebration !== null ? 'happy' : (pet.care?.mood_level ?? 'calm')}
        action={celebration === null ? reaction : null}
        idle={celebration === null && reaction === null}
        hatching={celebration?.hatching ?? false}
        className="display-pet-art"
      />
      <div className="display-pet-info">
        {celebration !== null && (
          <p className="display-pet-banner" role="status">
            {celebration.hatching
              ? t('display.petHatched', { name })
              : t('display.petGrew', { name })}
          </p>
        )}
        {celebration === null && reaction !== null && (
          <p className="display-pet-banner" role="status">
            {t('display.petCared', { name, care: t(`pet.care.${reaction}`) })}
          </p>
        )}
        <p className="display-pet-stage">{t(`pet.stage.${chosen ? pet.stage : 0}`)}</p>
        {pet.care !== null && (
          <p className="display-note">
            {t('pet.moodLine', { mood: t(`pet.mood.${pet.care.mood_level}`) })}
          </p>
        )}
        <p className="display-note">
          {toNext === null ? t('pet.final') : t('pet.toNext', { points: toNext })}
        </p>
      </div>
    </div>
  )
}
