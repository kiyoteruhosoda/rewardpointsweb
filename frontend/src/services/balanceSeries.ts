/**
 * 台帳の履歴から残高の推移を組み立てる（ポイントの推移グラフ）。
 *
 * 残高は履歴の合計として導出する（ADR-0010）ので、推移も同じく履歴を古い順に
 * 足していけば出る。打ち消し・訂正の行も 1 行として足す（台帳の残高と同じ数に
 * なる）。サーバーには何も足していない。
 *
 * 打ち消しの行と、打ち消された記録は、組にして推移から外す（ADR-0050）。
 * 打ち消しは「その記録は無かった」という意味なので、合計は 0 で、残高の推移にも
 * 現れないのが実態に合う。同じ時点に「元の記録・打ち消し・訂正後の行」を順に
 * 並べると、点を結ぶ線が一瞬だけ元の値まで跳ねる（+100 を 10 に直すと 185 まで
 * 上がって 95 へ戻る）。履歴の表は打ち消した日時のまま出す（いつ直したかは表で分かる）。
 * 打ち消した相手が手元に無いとき（届いていない等）だけ、打ち消しを自分の日時に置く。
 */
import { parseUtc, type Transaction } from './families'

export interface BalancePoint {
  /** 発生日時（ミリ秒）。 */
  at: number
  /** この行を足した後の残高。 */
  balance: number
  change: number
  reason: string
}

export type TrendRange = 'month' | 'quarter' | 'all'

export const TREND_RANGES: TrendRange[] = ['month', 'quarter', 'all']

const DAY = 24 * 60 * 60 * 1000
const RANGE_DAYS: Record<Exclude<TrendRange, 'all'>, number> = { month: 30, quarter: 90 }

/** 古い順に並べ、行ごとの残高を出す。打ち消し合う組は描かない。 */
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
  /** 期間の始まりの時点での残高（期間より前の行の合計）。 */
  startBalance: number
  points: BalancePoint[]
}

/** 期間で切り出す。期間より前の行は、始まりの残高として持ち越す。 */
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

/** 軸の目盛り。1・2・5 の 10 のべき乗倍で、*count* 本前後に収める。 */
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

/** 予測の見積もりに使う過去の長さ（日）。 */
export const FORECAST_BASIS_DAYS = 30
/** これより記録が短いと、増え方を見積もらない（数日の記録だと 1 回の加算で大きく振れる）。 */
export const FORECAST_MIN_HISTORY_DAYS = 7
/** 予測を出す先（日後）。グラフは最後の先まで点線で伸ばす。 */
export const FORECAST_HORIZONS = [7, 30] as const

export interface BalanceForecast {
  /** 見積もった 1 日あたりの増減（小数のまま）。 */
  perDay: number
  /** 見積もりに使った過去の日数。 */
  basisDays: number
  /** 各先での残高の見込み（四捨五入）。*FORECAST_HORIZONS* と同じ順。 */
  points: { days: number; at: number; balance: number }[]
}

/**
 * これからの残高を見積もる（ADR-0053）。
 *
 * 直近 *FORECAST_BASIS_DAYS* 日の増え方（毎日のボーナスも、手で付けた・使った分も
 * 込み）がそのまま続いたとして伸ばす。毎日のボーナスだけで伸ばさないのは、使う分を
 * 見ないと見込みが実際より大きく外れるため。記録が *FORECAST_MIN_HISTORY_DAYS* 日に
 * 満たないうちは null（見積もらない）。
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
