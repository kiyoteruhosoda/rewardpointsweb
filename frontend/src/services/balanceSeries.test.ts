import { describe, expect, it } from 'vitest'

import { balanceForecast, balanceSeries, niceTicks, trendWindow } from './balanceSeries'
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

  it('打ち消しと打ち消された記録は組にして描かない（訂正しても元の値まで跳ねない）', () => {
    // 85 の上に +100 を記録し、あとで 10 に訂正した: 打ち消し −100 と訂正後の +10 が足される
    const series = balanceSeries([
      { ...row(4, 10, '2026-09-01T00:00:00'), corrects_id: 2 },
      { ...row(3, -100, '2026-10-09T00:00:00'), reversal_of_id: 2 },
      { ...row(2, 100, '2026-09-01T00:00:00'), is_reversed: true },
      row(1, 85, '2026-08-01T00:00:00'),
    ])

    expect(series.map((point) => [point.at, point.balance])).toEqual([
      [Date.parse('2026-08-01T00:00:00Z'), 85],
      [Date.parse('2026-09-01T00:00:00Z'), 95],
    ])
    expect(Math.max(...series.map((point) => point.balance))).toBe(95)
  })

  it('取り消した記録は推移に現れない', () => {
    const series = balanceSeries([
      { ...row(3, -50, '2026-10-09T00:00:00'), reversal_of_id: 2 },
      { ...row(2, 50, '2026-09-01T00:00:00'), is_reversed: true },
      row(1, 100, '2026-08-01T00:00:00'),
    ])

    expect(series.map((point) => point.balance)).toEqual([100])
  })

  it('同じ時刻に並ぶ訂正後の行と別の記録は、残高を足した順に並べる', () => {
    const series = balanceSeries([
      { ...row(4, 10, '2026-09-01T00:00:00'), corrects_id: 2 },
      { ...row(3, -100, '2026-10-09T00:00:00'), reversal_of_id: 2 },
      row(2, 100, '2026-09-01T00:00:00'),
      row(1, -5, '2026-09-01T00:00:00'),
    ])

    expect(series.map((point) => [point.change, point.balance])).toEqual([
      [-5, -5],
      [10, 5],
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

describe('balanceForecast', () => {
  const now = Date.parse('2026-10-31T00:00:00Z')

  it('直近 30 日の増え方が続いたとして、1 週間後と 1 か月後を出す', () => {
    // 30 日前より前に 100、その後の 30 日で +60（毎日のボーナス +90 と使った −30）
    const forecast = balanceForecast(
      balanceSeries([
        row(3, -30, '2026-10-20T00:00:00'),
        row(2, 90, '2026-10-10T00:00:00'),
        row(1, 100, '2026-09-01T00:00:00'),
      ]),
      now,
    )

    expect(forecast?.perDay).toBe(2)
    expect(forecast?.basisDays).toBe(30)
    expect(forecast?.points.map((point) => [point.days, point.balance])).toEqual([
      [7, 174],
      [30, 220],
    ])
  })

  it('記録が 30 日に満たないときは、最初の記録からの日数で割る', () => {
    const forecast = balanceForecast(
      balanceSeries([row(2, 50, '2026-10-25T00:00:00'), row(1, 50, '2026-10-21T00:00:00')]),
      now,
    )

    expect(forecast?.basisDays).toBe(10)
    expect(forecast?.perDay).toBe(10)
  })

  it('使う方が多ければ、見込みは減っていく', () => {
    const forecast = balanceForecast(
      balanceSeries([row(2, -150, '2026-10-15T00:00:00'), row(1, 300, '2026-09-01T00:00:00')]),
      now,
    )

    expect(forecast?.points.at(-1)?.balance).toBe(0)
  })

  it('記録が 1 週間に満たないうちは見積もらない', () => {
    expect(balanceForecast(balanceSeries([row(1, 100, '2026-10-26T00:00:00')]), now)).toBeNull()
    expect(balanceForecast([], now)).toBeNull()
  })

  it('取り消した記録は増え方に数えない', () => {
    const forecast = balanceForecast(
      balanceSeries([
        { ...row(3, -100, '2026-10-20T00:00:00'), reversal_of_id: 2 },
        { ...row(2, 100, '2026-10-10T00:00:00'), is_reversed: true },
        row(1, 100, '2026-09-01T00:00:00'),
      ]),
      now,
    )

    expect(forecast?.perDay).toBe(0)
  })
})
