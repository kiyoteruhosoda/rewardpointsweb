/**
 * The pet on a child's ledger screen (ADR-0061).
 *
 * Shows the pet, its stage, the points earned so far and how many more the next stage needs.
 * The child (on their own ledger) and parents choose the species; until then it stays an egg.
 * When the stage has gone up since this screen last showed it, a celebration opens once.
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
  type PetSpecies,
} from '../services/pet'
import { PetArt } from './PetArt'
import { PetCelebration } from './PetCelebration'
import { useToast } from './ToastNotification'

interface Props {
  familyId: number
  ledgerId: number
  pet: Pet
  onChanged: (pet: Pet) => void
}

export function PetPanel({ familyId, ledgerId, pet, onChanged }: Props) {
  const { t } = useI18n()
  const { notify } = useToast()
  const [celebrating, setCelebrating] = useState(false)
  const chosen = pet.species !== null
  const closeCelebration = useCallback(() => {
    setCelebrating(false)
  }, [])

  // A pet without a species is drawn as an egg, so that is what this screen remembers having
  // shown (stage 0) — choosing then shows it hatch at its real stage
  useEffect(() => {
    if (takeStageUp(ledgerId, chosen ? pet.stage : 0) && chosen) setCelebrating(true)
  }, [chosen, ledgerId, pet.stage])

  const [choose, choosing] = usePendingAction(async (species: PetSpecies) => {
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
        <PetArt species={pet.species} stage={pet.stage} className="pet-panel-art" />
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

      {!chosen && pet.can_choose && (
        <div className="pet-panel-choose">
          <p className="pet-panel-choose-title">
            {pet.stage > 0 ? t('pet.eggWaiting') : t('pet.choose')}
          </p>
          {picker}
        </div>
      )}
      {!chosen && !pet.can_choose && <p className="pet-panel-hint">{t('pet.notChosen')}</p>}
      {chosen && pet.can_choose && (
        <details className="pet-panel-change">
          <summary>{t('pet.change')}</summary>
          {picker}
        </details>
      )}

      {celebrating && pet.species !== null && (
        <PetCelebration species={pet.species} stage={pet.stage} onClose={closeCelebration} />
      )}
    </section>
  )
}
