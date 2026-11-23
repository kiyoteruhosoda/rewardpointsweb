/**
 * The pet on a child's ledger (ADR-0061).
 *
 * It comes with the ledger response (`Ledger.pet`) and starts as an egg. Choosing its species
 * hands the egg over — once; it cannot change while the pet grows. From then on it grows with
 * the points added; spending never shrinks it. Once fully grown, the next pet can be chosen and
 * starts again from an egg. The parents or the child choose.
 *
 * Once hatched, the child (their own) and parents can care for it (task #1128): feed, pat, play,
 * bath. Care is free and never touches the growth; it lifts the mood, and a pet left alone only
 * looks lonely. Display devices only look, and react when someone has cared for it.
 *
 * Each screen remembers the last stage it showed per ledger. When the stage has gone up since,
 * that screen celebrates once — the child's phone and a display device each get their own
 * celebration. The memory is a per-device convenience: if storage is unavailable the screen
 * simply does not celebrate.
 */
import { api } from './api'

export const PET_SPECIES = ['cat', 'rabbit', 'bird', 'dragon'] as const
export type PetSpecies = (typeof PET_SPECIES)[number]

export const PET_CARE_KINDS = ['feed', 'pat', 'play', 'bath'] as const
export type PetCareKind = (typeof PET_CARE_KINDS)[number]
export type PetMoodLevel = 'lonely' | 'calm' | 'happy'

/** How a hatched pet feels. Care never touches growth. */
export interface PetCare {
  /** 0..100, made of the recent cares. */
  mood: number
  /** lonely is only a face: the pet never weakens, shrinks or leaves. */
  mood_level: PetMoodLevel
  /** On how many days it was cared for (friendship). */
  days_cared: number
  last_kind: PetCareKind | null
  /** ISO 8601 with Z. */
  last_cared_at: string | null
}

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
  /**
   * Whether the viewer may choose a pet now: allowed (parents, and the child for their own) and
   * there is an egg to receive — none chosen yet, or the current pet is fully grown.
   */
  can_choose: boolean
  /** Species of the pets already raised, oldest first. */
  raised: PetSpecies[]
  /** null until it hatches (an egg is not cared for). */
  care: PetCare | null
  /** Whether the viewer may care for it now (allowed, and hatched). Never on a display. */
  can_care: boolean
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
  care: (familyId: number, ledgerId: number, kind: PetCareKind) =>
    api.post<Pet>(`/api/families/${familyId}/ledgers/${ledgerId}/pet/cares`, { kind }),
}

const SEEN_KEY_PREFIX = 'pet-seen-stage:'

/**
 * Whether this screen should celebrate *stage* for *ledgerId*, and remember it as seen.
 *
 * Returns the stage it last showed when the pet has gone up since (0 means it hatched), or
 * null when there is nothing to celebrate. The first time a screen sees a pet it only
 * remembers (nothing to compare with). A lower stage (an addition was reversed) is remembered
 * quietly too.
 */
export function takeStageUp(ledgerId: number, stage: number): number | null {
  const key = `${SEEN_KEY_PREFIX}${ledgerId}`
  try {
    const seen = localStorage.getItem(key)
    localStorage.setItem(key, String(stage))
    return seen !== null && stage > Number(seen) ? Number(seen) : null
  } catch {
    return null
  }
}

const CARE_SEEN_KEY_PREFIX = 'pet-seen-care:'

/**
 * Whether *caredAt* is a care this screen has not reacted to yet, and remember it.
 *
 * For screens that did not give the care themselves (a display device). The first look only
 * remembers, so opening the screen does not replay an old care.
 */
export function takeNewCare(ledgerId: number, caredAt: string | null): boolean {
  if (caredAt === null) return false
  const key = `${CARE_SEEN_KEY_PREFIX}${ledgerId}`
  try {
    const seen = localStorage.getItem(key)
    localStorage.setItem(key, caredAt)
    return seen !== null && Date.parse(caredAt) > Date.parse(seen)
  } catch {
    return false
  }
}
