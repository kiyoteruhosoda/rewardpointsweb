import { describe, expect, it } from 'vitest'

import { balanceSeries, niceTicks, trendWindow } from './balanceSeries'
import type { Transaction } from './families'

function row(id: number, amount: number, occurredAt: string): Transaction {
  return {
    id,
    amount,
    reason: `r${id}`,
    occurred_at: occurredAt,
    created_at: occurredAt,
    reversal_of_id: null,
    corrects_id: null,
    is_reversed: false,
    granted_by: null,
  }
}

describe('balanceSeries', () => {
  it('古い順に足して、行ごとの残高を出す（届く順は新しい順）', () => {
    const series = balanceSeries([
      row(3, -5, '2026-10-03T00:00:00'),
      row(2, 20, '2026-10-02T00:00:00'),
      row(1, 10, '2026-10-01T00:00:00'),
    ])

    expect(series.map((point) => point.balance)).toEqual([10, 30, 25])
  })

  it('同じ時刻の行は記録した順に並べる', () => {
    const series = balanceSeries([
      row(2, -10, '2026-10-01T00:00:00'),
      row(1, 10, '2026-10-01T00:00:00'),
    ])

    expect(series.map((point) => point.change)).toEqual([10, -10])
  })

  it('打ち消しは打ち消した記録の時点に置く（過去を直しても今日は跳ねない）', () => {
    const series = balanceSeries([
      { ...row(4, 30, '2026-09-01T00:00:00'), corrects_id: 2 },
      { ...row(3, -50, '2026-10-09T00:00:00'), reversal_of_id: 2 },
      { ...row(2, 50, '2026-09-01T00:00:00'), is_reversed: true },
      row(1, 100, '2026-08-01T00:00:00'),
    ])

    expect(series.map((point) => [point.at, point.balance])).toEqual([
      [Date.parse('2026-08-01T00:00:00Z'), 100],
      [Date.parse('2026-09-01T00:00:00Z'), 150],
      [Date.parse('2026-09-01T00:00:00Z'), 100],
      [Date.parse('2026-09-01T00:00:00Z'), 130],
    ])
  })

  it('打ち消した相手が無ければ打ち消しの日時に置く', () => {
    const series = balanceSeries([{ ...row(3, -50, '2026-10-09T00:00:00'), reversal_of_id: 2 }])

    expect(series[0]?.at).toBe(Date.parse('2026-10-09T00:00:00Z'))
  })
})

describe('trendWindow', () => {
  const now = Date.parse('2026-10-03T00:00:00Z')

  it('期間より前の行は始まりの残高として持ち越す', () => {
    const series = balanceSeries([
      row(1, 100, '2026-01-01T00:00:00'),
      row(2, 10, '2026-09-30T00:00:00'),
    ])

    const window = trendWindow(series, 'month', now)

    expect(window.startBalance).toBe(100)
    expect(window.points.map((point) => point.balance)).toEqual([110])
  })

  it('すべてを選ぶと最初の行から始まる', () => {
    const series = balanceSeries([row(1, 100, '2026-01-01T00:00:00')])

    const window = trendWindow(series, 'all', now)

    expect(window.start).toBe(Date.parse('2026-01-01T00:00:00Z'))
    expect(window.startBalance).toBe(0)
  })
})

describe('niceTicks', () => {
  it('きりのよい目盛りで範囲を覆う', () => {
    expect(niceTicks(0, 95)).toEqual([0, 50, 100])
  })

  it('負の残高があれば 0 をまたぐ', () => {
    const ticks = niceTicks(-30, 70)
    expect(ticks).toContain(0)
    expect(ticks[0]).toBeLessThanOrEqual(-30)
    expect(ticks.at(-1)).toBeGreaterThanOrEqual(70)
  })
})
