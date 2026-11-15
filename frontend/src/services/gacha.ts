/**
 * API client for gacha machines on a child's ledger (ADR-0060).
 *
 * A parent sets up a machine (name, price of one draw, prizes with weights). One draw spends the
 * price from the ledger and wins one prize, picked on the server. Each press sends one
 * idempotency key, carried over until the press succeeds, so a double tap or a retry never draws twice.
 */
import { api } from './api'

export interface GachaPrize {
  name: string
  /** Relative to the other prizes' weights (2 comes out twice as often as 1). */
  weight: number
  is_miss: boolean
}

export interface Gacha {
  id: number
  ledger_id: number
  name: string
  price: number
  /** In display order. */
  prizes: GachaPrize[]
  created_at: string
}

export interface GachaDraw {
  id: number
  /** null once the machine is deleted. */
  gacha_id: number | null
  /** Names and price as they were when drawn. */
  gacha_name: string
  prize_name: string
  is_miss: boolean
  price: number
  drawn_at: string
  /** When a parent handed the prize over. null if not yet (always null for a miss). */
  handed_over_at: string | null
}

export interface GachaDrawResult {
  draw: GachaDraw
  /** Ledger balance right after the draw. */
  balance: number
}

export interface GachaBoard {
  ledger_id: number
  display_name: string
  balance: number
  /** Whether to show create, edit, delete and "handed over". */
  can_modify: boolean
  /** Whether to show the draw button (parents, and the child on their own ledger). */
  can_draw: boolean
  /** In creation order. */
  gachas: Gacha[]
  /** Newest first. */
  draws: GachaDraw[]
}

export interface GachaDesign {
  name: string
  price: number
  prizes: GachaPrize[]
}

/** Same limits as the server (domain/entities/gacha.py). */
export const NAME_MAX_LENGTH = 50
export const MAX_PRIZES = 20
export const MAX_WEIGHT = 1000

/** Share of one prize in percent, rounded to one decimal place. */
export function chanceOf(prize: GachaPrize, prizes: readonly GachaPrize[]): number {
  const total = prizes.reduce((sum, p) => sum + p.weight, 0)
  return total === 0 ? 0 : Math.round((prize.weight / total) * 1000) / 10
}

const gachasPath = (familyId: number, ledgerId: number) =>
  `/api/families/${familyId}/ledgers/${ledgerId}/gachas`

const handedOverPath = (familyId: number, ledgerId: number, drawId: number) =>
  `/api/families/${familyId}/ledgers/${ledgerId}/gacha-draws/${drawId}/handed-over`

export const gacha = {
  board: (familyId: number, ledgerId: number) =>
    api.get<GachaBoard>(gachasPath(familyId, ledgerId)),

  create: (familyId: number, ledgerId: number, design: GachaDesign) =>
    api.post<Gacha>(gachasPath(familyId, ledgerId), design),

  /** Replace the name, price and all prizes. Past draws keep what they won. */
  update: (familyId: number, ledgerId: number, gachaId: number, design: GachaDesign) =>
    api.put<Gacha>(`${gachasPath(familyId, ledgerId)}/${gachaId}`, design),

  /** Delete. Past draws and the points spent on them stay. */
  remove: (familyId: number, ledgerId: number, gachaId: number) =>
    api.delete<undefined>(`${gachasPath(familyId, ledgerId)}/${gachaId}`),

  /** Draw once. Resending the same key returns the draw already made. */
  draw: (familyId: number, ledgerId: number, gachaId: number, idempotencyKey: string) =>
    api.post<GachaDrawResult>(`${gachasPath(familyId, ledgerId)}/${gachaId}/draws`, {
      idempotency_key: idempotencyKey,
    }),

  handOver: (familyId: number, ledgerId: number, drawId: number) =>
    api.put<GachaDraw>(handedOverPath(familyId, ledgerId, drawId)),

  takeBackHandOver: (familyId: number, ledgerId: number, drawId: number) =>
    api.delete<GachaDraw>(handedOverPath(familyId, ledgerId, drawId)),
}
