/**
 * The pet on a child's ledger (ADR-0061).
 *
 * It comes with the ledger response (`Ledger.pet`) and starts as an egg. Choosing its species
 * hands the egg over; from then on it grows with the points added. Spending never shrinks it.
 * The parents or the child choose its species.
 *
 * Each screen remembers the last stage it showed per ledger. When the stage has gone up since,
 * that screen celebrates once — the child's phone and a display device each get their own
 * celebration. The memory is a per-device convenience: if storage is unavailable the screen
 * simply does not celebrate.
 */
import { api } from './api'

export const PET_SPECIES = ['cat', 'rabbit', 'bird', 'dragon'] as const
export type PetSpecies = (typeof PET_SPECIES)[number]

export interface Pet {
  /** null until someone chooses (still an egg). */
  species: PetSpecies | null
  /** 0 is the egg. */
  stage: number
  stage_count: number
  /** Points added since the egg was handed over (spending does not lower it). 0 before. */
  earned: number
  current_threshold: number
  /** null at the final stage. */
  next_threshold: number | null
  /** Whether the viewer may choose the species (parents, and the child for their own). */
  can_choose: boolean
}

/** Progress within the current stage, 0..1 (1 at the final stage). */
export function stageProgress(pet: Pet): number {
  if (pet.next_threshold === null) return 1
  const span = pet.next_threshold - pet.current_threshold
  return span <= 0 ? 1 : Math.min(1, Math.max(0, (pet.earned - pet.current_threshold) / span))
}

export const petApi = {
  choose: (familyId: number, ledgerId: number, species: PetSpecies) =>
    api.put<Pet>(`/api/families/${familyId}/ledgers/${ledgerId}/pet`, { species }),
}

const SEEN_KEY_PREFIX = 'pet-seen-stage:'

/**
 * Whether this screen should celebrate *stage* for *ledgerId*, and remember it as seen.
 *
 * The first time a screen sees a pet it only remembers (nothing to compare with). A lower
 * stage (an addition was reversed) is remembered quietly too.
 */
export function takeStageUp(ledgerId: number, stage: number): boolean {
  const key = `${SEEN_KEY_PREFIX}${ledgerId}`
  try {
    const seen = localStorage.getItem(key)
    localStorage.setItem(key, String(stage))
    return seen !== null && stage > Number(seen)
  } catch {
    return false
  }
}
