/**
 * The pet on a child's ledger screen (ADR-0061).
 *
 * Shows the pet, its stage, the points earned so far and how many more the next stage needs.
 * The child (on their own ledger) and parents choose the species; until then it stays an egg.
 * When the stage has gone up since this screen last showed it, a celebration opens once (an
 * egg cracks open when it hatches). Once hatched, they can care for it (task #1128): the pet
 * plays the care's move and its mood goes up; growth stays as it is.
 */
import { useCallback, useEffect, useState } from 'react'

import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import {
  PET_SPECIES,
  petApi,
  stageProgress,
  takeStageUp,
  type Pet,
  type PetCareKind,
  type PetSpecies,
} from '../services/pet'
import { PetArt } from './PetArt'
import { PetCareBar } from './PetCareBar'
import { PetCelebration } from './PetCelebration'
import { useToast } from './ToastNotification'

interface Props {
  familyId: number
  ledgerId: number
  pet: Pet
  onChanged: (pet: Pet) => void
}

/** How long a care's move plays before the pet goes back to idling. */
export const CARE_MOVE_MS = 1800

interface CareMove {
  kind: PetCareKind
  /** Bumped on every press, so pressing the same care again replays it. */
  round: number
}

export function PetPanel({ familyId, ledgerId, pet, onChanged }: Props) {
  const { t } = useI18n()
  const { notify } = useToast()
  // null: no celebration. Otherwise whether it hatched (came out of the egg) this time
  const [celebration, setCelebration] = useState<{ hatching: boolean } | null>(null)
  const [move, setMove] = useState<CareMove | null>(null)
  const [careStatus, setCareStatus] = useState('')
  const chosen = pet.species !== null
  const closeCelebration = useCallback(() => {
    setCelebration(null)
  }, [])

  // A pet without a species is drawn as an egg, so that is what this screen remembers having
  // shown (stage 0) — choosing then shows it hatch at its real stage
  useEffect(() => {
    const from = takeStageUp(ledgerId, chosen ? pet.stage : 0)
    if (from !== null && chosen) setCelebration({ hatching: from === 0 })
  }, [chosen, ledgerId, pet.stage])

  // A care's move plays for a while, then the pet goes back to idling
  useEffect(() => {
    if (move === null) return
    const timer = window.setTimeout(() => {
      setMove(null)
    }, CARE_MOVE_MS)
    return () => {
      window.clearTimeout(timer)
    }
  }, [move])

  const [care, caring] = usePendingAction(async (kind: PetCareKind) => {
    // The move starts at once; the answer only brings the new mood
    setMove((previous) => ({ kind, round: (previous?.round ?? 0) + 1 }))
    try {
      const next = await petApi.care(familyId, ledgerId, kind)
      onChanged(next)
      const mood =
        next.care === null
          ? ''
          : ` ${t('pet.moodLine', { mood: t(`pet.mood.${next.care.mood_level}`) })}`
      setCareStatus(`${t(`pet.cared.${kind}`)}${mood}`)
    } catch (error) {
      setMove(null)
      notify('error', t(errorMessageKey(error)))
    }
  })

  const [choose, choosing] = usePendingAction(async (species: PetSpecies) => {
    // The kind cannot be changed while the pet grows, so a mis-tap is asked about first
    if (!window.confirm(t('pet.confirmChoose', { species: t(`pet.species.${species}`) }))) return
    try {
      onChanged(await petApi.choose(familyId, ledgerId, species))
      notify('success', t('pet.chosen', { species: t(`pet.species.${species}`) }))
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  })

  const toNext = pet.next_threshold === null ? null : pet.next_threshold - pet.earned
  const picker = (
    <div className="pet-picker" role="group" aria-label={t('pet.choose')}>
      {PET_SPECIES.map((species) => (
        <button
          key={species}
          type="button"
          className={
            pet.species === species ? 'pet-picker-option is-selected' : 'pet-picker-option'
          }
          aria-pressed={pet.species === species}
          disabled={choosing}
          onClick={() => {
            choose(species)
          }}
        >
          <PetArt species={species} stage={2} />
          <span>{t(`pet.species.${species}`)}</span>
        </button>
      ))}
    </div>
  )

  return (
    <section className="card pet-panel" aria-label={t('pet.heading')}>
      <div className="pet-panel-main">
        <PetArt
          key={move === null ? 'idle' : `${move.kind}-${move.round}`}
          species={pet.species}
          stage={pet.stage}
          mood={pet.care?.mood_level ?? 'calm'}
          action={move?.kind ?? null}
          idle={move === null}
          className="pet-panel-art"
        />
        <div className="pet-panel-info">
          <p className="pet-panel-stage">
            {/* Until a species is chosen it is drawn as an egg, so it is named one too */}
            {t(`pet.stage.${chosen ? pet.stage : 0}`)}
            {chosen && <span className="pet-panel-species">{t(`pet.species.${pet.species}`)}</span>}
          </p>
          <p className="pet-panel-earned">{t('pet.earned', { points: pet.earned })}</p>
          <div
            className="pet-progress"
            role="progressbar"
            aria-label={t('pet.progressLabel')}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(stageProgress(pet) * 100)}
          >
            <span style={{ width: `${stageProgress(pet) * 100}%` }} />
          </div>
          <p className="pet-panel-next">
            {toNext === null ? t('pet.final') : t('pet.toNext', { points: toNext })}
          </p>
          <p className="pet-panel-hint">{t('pet.chooseHint')}</p>
        </div>
      </div>

      <PetCareBar
        pet={pet}
        status={careStatus}
        busy={caring}
        onCare={(kind) => {
          care(kind)
        }}
      />

      {pet.can_choose && (
        <div className="pet-panel-choose">
          {/* The first egg, or the next one once the current pet is fully grown */}
          <p className="pet-panel-choose-title">{chosen ? t('pet.nextTitle') : t('pet.choose')}</p>
          <p className="pet-panel-hint">{chosen ? t('pet.nextHint') : t('pet.chooseStarts')}</p>
          {picker}
        </div>
      )}
      {!chosen && !pet.can_choose && <p className="pet-panel-hint">{t('pet.notChosen')}</p>}

      {pet.raised.length > 0 && (
        <div className="pet-panel-raised">
          <p className="pet-panel-raised-title">
            {t('pet.raisedTitle', { count: pet.raised.length })}
          </p>
          <ul>
            {pet.raised.map((species, index) => (
              <li key={`${index}-${species}`} title={t(`pet.species.${species}`)}>
                <PetArt species={species} stage={pet.stage_count - 1} />
                <span className="visually-hidden">{t(`pet.species.${species}`)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {celebration !== null && pet.species !== null && (
        <PetCelebration
          species={pet.species}
          stage={pet.stage}
          hatching={celebration.hatching}
          onClose={closeCelebration}
        />
      )}
    </section>
  )
}
