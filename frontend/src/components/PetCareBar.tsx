/**
 * How a hatched pet feels, and the care buttons (task #1128).
 *
 * Care is free and never touches growth: the buttons lift the mood, and a pet left alone only
 * looks lonely. The result of a care is also said in text (a live region), so it reads the same
 * with reduced motion. Display devices get no buttons (`can_care` is false there).
 */
import { useI18n } from '../i18n'
import { PET_CARE_KINDS, type Pet, type PetCareKind } from '../services/pet'

const OUTLINE = '#2b2540'

/** A small picture on each button, so a child who cannot read yet can still pick one. */
function CareIcon({ kind }: { kind: PetCareKind }) {
  const stroke = { stroke: OUTLINE, strokeWidth: 3, strokeLinejoin: 'round' as const }
  return (
    <svg className="pet-care-icon" viewBox="-20 -20 40 40" aria-hidden="true" focusable="false">
      {kind === 'feed' && (
        <g>
          <path d="M -15 -2 Q -14 -14 0 -14 Q 14 -14 15 -2 Z" fill="#ffffff" {...stroke} />
          <path d="M -17 -2 L 17 -2 Q 14 15 0 15 Q -14 15 -17 -2 Z" fill="#5ab8ff" {...stroke} />
        </g>
      )}
      {kind === 'pat' && (
        <path
          d="M 0 14 C -16 2 -18 -10 -9 -13 C -4 -15 0 -10 0 -7 C 0 -10 4 -15 9 -13 C 18 -10 16 2 0 14 Z"
          fill="#ff5fa2"
          {...stroke}
        />
      )}
      {kind === 'play' && (
        <g>
          <circle r="14" fill="#ffd23f" {...stroke} />
          <path d="M -14 0 Q 0 -7 14 0" fill="none" stroke="#9b6bff" strokeWidth={4} />
        </g>
      )}
      {kind === 'bath' && (
        <g fill="#d9f1ff" stroke="#5ab8ff" strokeWidth={3}>
          <circle cx="-6" cy="4" r="9" />
          <circle cx="9" cy="-6" r="7" />
          <circle cx="8" cy="11" r="5" />
        </g>
      )}
    </svg>
  )
}

interface Props {
  pet: Pet
  /** Text for the care just given (the live region). Empty when none. */
  status: string
  busy: boolean
  onCare: (kind: PetCareKind) => void
}

export function PetCareBar({ pet, status, busy, onCare }: Props) {
  const { t } = useI18n()
  const care = pet.care
  if (care === null) {
    // An egg is not cared for. Once a kind is chosen, say when caring starts
    return pet.species !== null ? <p className="pet-panel-hint">{t('pet.careAfterHatch')}</p> : null
  }
  return (
    <div className="pet-care">
      <div className="pet-care-feelings">
        <p className={`pet-care-mood is-${care.mood_level}`}>
          {t('pet.moodLine', { mood: t(`pet.mood.${care.mood_level}`) })}
        </p>
        <div
          className="pet-mood-meter"
          role="progressbar"
          aria-label={t('pet.moodLabel')}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={care.mood}
        >
          <span style={{ width: `${care.mood}%` }} />
        </div>
        <p className="pet-care-friendship">{t('pet.friendship', { days: care.days_cared })}</p>
      </div>
      {care.mood_level === 'lonely' && <p className="pet-panel-hint">{t('pet.lonelyHint')}</p>}
      {pet.can_care && (
        <>
          <div className="pet-care-actions" role="group" aria-label={t('pet.careHeading')}>
            {PET_CARE_KINDS.map((kind) => (
              <button
                key={kind}
                type="button"
                className="pet-care-button"
                disabled={busy}
                onClick={() => {
                  onCare(kind)
                }}
              >
                <CareIcon kind={kind} />
                <span>{t(`pet.care.${kind}`)}</span>
              </button>
            ))}
          </div>
          <p className="pet-panel-hint">{t('pet.careFree')}</p>
        </>
      )}
      <p className="pet-care-status" role="status">
        {status}
      </p>
    </div>
  )
}
