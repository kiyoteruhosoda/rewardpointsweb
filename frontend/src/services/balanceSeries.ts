/**
 * 台帳の履歴から残高の推移を組み立てる（ポイントの推移グラフ）。
 *
 * 残高は履歴の合計として導出する（ADR-0010）ので、推移も同じく履歴を古い順に
 * 足していけば出る。打ち消し・訂正の行も 1 行として足す（台帳の残高と同じ数に
 * なる）。サーバーには何も足していない。
 *
 * 打ち消しの行は、打ち消した記録の発生日時に置く（ADR-0049）。打ち消しは
 * 「その記録は無かった」という意味なので、打ち消した日に残高が跳ねると、
 * 過去の記録を直しただけで今日に増減があったように見える。訂正後の行は元の
 * 発生日時を引き継いでいるので、打ち消しと同じ時点に並ぶ。履歴の表は
 * 打ち消した日時のまま出す（いつ直したかは表で分かる）。
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

/** 古い順に並べ、行ごとの残高を出す。 */
export function balanceSeries(transactions: readonly Transaction[]): BalancePoint[] {
  const occurredAt = new Map(transactions.map((row) => [row.id, row.occurred_at]))
  const ordered = transactions
    .map((transaction) => {
      // 打ち消した相手が手元に無いとき（届いていない等）は打ち消しの日時に置く
      const original =
        transaction.reversal_of_id === null ? undefined : occurredAt.get(transaction.reversal_of_id)
      return { transaction, at: parseUtc(original ?? transaction.occurred_at).getTime() }
    })
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
