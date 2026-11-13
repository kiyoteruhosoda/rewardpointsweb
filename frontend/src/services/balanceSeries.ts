/**
 * Builds the balance history from the ledger entries (the points trend chart).
 *
 * The balance is derived as the sum of entries (ADR-0010), so the trend likewise comes from adding
 * entries oldest first. Reversal and correction rows are added as rows too (giving the same number as the
 * ledger balance). Nothing extra is added on the server.
 *
 * A reversal row and the record it reverses are paired and left out of the trend (ADR-0050).
 * A reversal means "that record never happened", so the sum is 0 and it matching reality means
 * it does not appear in the trend either. Placing "original record, reversal, corrected row" in order at the same instant
 * makes the connecting line spike briefly to the original value (fixing +100 to 10 goes up to 185
 * and back to 95). The history table keeps the reversal's own time (the table shows when it was fixed).
 * Only when the reversed record is not at hand (not delivered etc.) is the reversal placed at its own time.
 */
import { parseUtc, type Transaction } from './families'

export interface BalancePoint {
  /** When it happened (milliseconds). */
  at: number
  /** Balance after adding this row. */
  balance: number
  change: number
  reason: string
}

export type TrendRange = 'month' | 'quarter' | 'all'

export const TREND_RANGES: TrendRange[] = ['month', 'quarter', 'all']

const DAY = 24 * 60 * 60 * 1000
const RANGE_DAYS: Record<Exclude<TrendRange, 'all'>, number> = { month: 30, quarter: 90 }

/** Sort oldest first and compute the balance per row. Pairs that cancel out are not drawn. */
export function balanceSeries(transactions: readonly Transaction[]): BalancePoint[] {
  const ids = new Set(transactions.map((row) => row.id))
  const cancelled = new Set(
    transactions.flatMap((row) =>
      row.reversal_of_id !== null && ids.has(row.reversal_of_id)
        ? [row.id, row.reversal_of_id]
        : [],
    ),
  )
  const ordered = transactions
    .filter((transaction) => !cancelled.has(transaction.id))
    .map((transaction) => ({ transaction, at: parseUtc(transaction.occurred_at).getTime() }))
    .sort((a, b) => a.at - b.at || a.transaction.id - b.transaction.id)
  let balance = 0
  return ordered.map(({ transaction, at }) => {
    balance += transaction.amount
    return { at, balance, change: transaction.amount, reason: transaction.reason }
  })
}

export interface TrendWindow {
  start: number
  end: number
  /** Balance at the start of the period (sum of rows before the period). */
  startBalance: number
  points: BalancePoint[]
}

/** Cut out a period. Rows before the period carry over as the starting balance. */
export function trendWindow(
  series: readonly BalancePoint[],
  range: TrendRange,
  now: number,
): TrendWindow {
  const first = series[0]
  const start =
    range === 'all' ? Math.min(first?.at ?? now - DAY, now - DAY) : now - RANGE_DAYS[range] * DAY
  const before = series.filter((point) => point.at < start)
  return {
    start,
    end: now,
    startBalance: before.at(-1)?.balance ?? 0,
    points: series.filter((point) => point.at >= start && point.at <= now),
  }
}

/** Axis ticks. Powers of 10 times 1, 2 or 5, about *count* of them. */
export function niceTicks(min: number, max: number, count = 4): number[] {
  const span = max - min || 1
  const raw = span / count
  const power = 10 ** Math.floor(Math.log10(raw))
  const step =
    ([1, 2, 5, 10].map((m) => m * power).find((candidate) => candidate >= raw) ?? raw) || 1
  const first = Math.floor(min / step) * step
  const steps = Math.max(1, Math.ceil((max - first) / step))
  return Array.from({ length: steps + 1 }, (_, index) => Math.round(first + index * step))
}

/** How far back (days) to look when estimating the forecast. */
export const FORECAST_BASIS_DAYS = 30
/** With a shorter history than this, do not estimate the growth (a few days of records swing widely on one addition). */
export const FORECAST_MIN_HISTORY_DAYS = 7
/** How far ahead (days) to forecast. The chart extends a dotted line to the furthest one. */
export const FORECAST_HORIZONS = [7, 30] as const

export interface BalanceForecast {
  /** Estimated change per day (kept as a fraction). */
  perDay: number
  /** Number of past days used for the estimate. */
  basisDays: number
  /** Expected balance at each horizon (rounded). Same order as *FORECAST_HORIZONS*. */
  points: { days: number; at: number; balance: number }[]
}

/**
 * Estimate the future balance (ADR-0053).
 *
 * Extends the growth over the last *FORECAST_BASIS_DAYS* days (daily bonuses, manual additions and spending
 * included) as if it continued. It does not extend daily bonuses alone because ignoring spending
 * makes the forecast far larger than reality. null (no estimate) while the records cover fewer than
 * *FORECAST_MIN_HISTORY_DAYS* days.
 */
export function balanceForecast(
  series: readonly BalancePoint[],
  now: number,
): BalanceForecast | null {
  const first = series[0]
  if (first === undefined) return null
  const historyDays = (now - first.at) / DAY
  if (historyDays < FORECAST_MIN_HISTORY_DAYS) return null
  const basisDays = Math.min(FORECAST_BASIS_DAYS, historyDays)
  const since = now - basisDays * DAY
  const before = series.filter((point) => point.at < since).at(-1)?.balance ?? 0
  const current = series.filter((point) => point.at <= now).at(-1)?.balance ?? 0
  const perDay = (current - before) / basisDays
  return {
    perDay,
    basisDays: Math.round(basisDays),
    points: FORECAST_HORIZONS.map((days) => ({
      days,
      at: now + days * DAY,
      balance: Math.round(current + perDay * days),
    })),
  }
}
