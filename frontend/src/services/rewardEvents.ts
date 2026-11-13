/**
 * API client for events (effort cards, ADR-0042).
 *
 * Created with a goal, points awarded on completion and a completion count; each completion adds
 * one sticker. When all cells are filled, the server adds one completion points row to the ledger.
 *
 * Stickers are added **by number**. The client sends "the next number to add", and sending the same number twice
 * still yields one sticker (a double tap or network retry does not make two).
 */
import { api } from './api'

export interface Sticker {
  /** Sequence number starting at 1. */
  number: number
  stuck_at: string
}

export interface RewardEvent {
  id: number
  ledger_id: number
  /** Goal. Also used as the ledger reason on completion. */
  title: string
  reward_points: number
  /** Completion count (= number of cells). */
  goal_count: number
  /** Ascending by number. */
  stickers: Sticker[]
  /** When the cells were filled. null if not yet. */
  completed_at: string | null
  created_at: string
  /** Completed if filled by the end of this day (YYYY-MM-DD). null if not set. ADR-0043 */
  deadline: string | null
  /** Past the deadline and not filled. Decided by the server (the family's day boundary). */
  is_expired: boolean
}

export interface RewardEventBoard {
  ledger_id: number
  display_name: string
  /** Whether to show the create, add, remove and delete entry points. */
  can_modify: boolean
  /** In creation order. */
  events: RewardEvent[]
}

export interface NewRewardEvent {
  title: string
  reward_points: number
  goal_count: number
  /** YYYY-MM-DD. null for no deadline. */
  deadline: string | null
}

/** Maximum completion count (same as the server's MAX_GOAL_COUNT). */
export const MAX_GOAL_COUNT = 50

/** Maximum goal length (same as the server's TITLE_MAX_LENGTH). */
export const TITLE_MAX_LENGTH = 100

const eventsPath = (familyId: number, ledgerId: number) =>
  `/api/families/${familyId}/ledgers/${ledgerId}/events`

const stickerPath = (familyId: number, ledgerId: number, eventId: number, number: number) =>
  `${eventsPath(familyId, ledgerId)}/${eventId}/stickers/${number}`

export const rewardEvents = {
  board: (familyId: number, ledgerId: number) =>
    api.get<RewardEventBoard>(eventsPath(familyId, ledgerId)),

  create: (familyId: number, ledgerId: number, event: NewRewardEvent) =>
    api.post<RewardEvent>(eventsPath(familyId, ledgerId), event),

  /** Add sticker number *number*. If it is the last cell, the points go into the ledger. */
  stick: (familyId: number, ledgerId: number, eventId: number, number: number) =>
    api.put<RewardEvent>(stickerPath(familyId, ledgerId, eventId, number)),

  /** Reset the deadline (null for none). An expired card can be added to again once extended. */
  changeDeadline: (familyId: number, ledgerId: number, eventId: number, deadline: string | null) =>
    api.put<RewardEvent>(`${eventsPath(familyId, ledgerId)}/${eventId}/deadline`, { deadline }),

  /** Remove the last sticker (undo a mis-tap). Not possible after completion. */
  peel: (familyId: number, ledgerId: number, eventId: number, number: number) =>
    api.delete<RewardEvent>(stickerPath(familyId, ledgerId, eventId, number)),

  /** Delete. Points added on completion stay in the ledger. */
  remove: (familyId: number, ledgerId: number, eventId: number) =>
    api.delete<undefined>(`${eventsPath(familyId, ledgerId)}/${eventId}`),
}
