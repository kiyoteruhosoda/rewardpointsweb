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
  it('sums oldest first and gives the balance per row (rows arrive newest first)', () => {
    const series = balanceSeries([
      row(3, -5, '2026-10-03T00:00:00'),
      row(2, 20, '2026-10-02T00:00:00'),
      row(1, 10, '2026-10-01T00:00:00'),
    ])

    expect(series.map((point) => point.balance)).toEqual([10, 30, 25])
  })

  it('orders rows with the same time in recorded order', () => {
    const series = balanceSeries([
      row(2, -10, '2026-10-01T00:00:00'),
      row(1, 10, '2026-10-01T00:00:00'),
    ])

    expect(series.map((point) => point.change)).toEqual([10, -10])
  })

  it('skips reversal pairs (a correction does not spike back to the old value)', () => {
    // Recorded +100 on top of 85, later corrected to 10: a reversal −100 and the corrected +10 are added
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

  it('reversed records do not appear in the trend', () => {
    const series = balanceSeries([
      { ...row(3, -50, '2026-10-09T00:00:00'), reversal_of_id: 2 },
      { ...row(2, 50, '2026-09-01T00:00:00'), is_reversed: true },
      row(1, 100, '2026-08-01T00:00:00'),
    ])

    expect(series.map((point) => point.balance)).toEqual([100])
  })

  it('orders a corrected row and another record at the same time by the order balances were summed', () => {
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

  it('places a reversal at its own time when its target is missing', () => {
    const series = balanceSeries([{ ...row(3, -50, '2026-10-09T00:00:00'), reversal_of_id: 2 }])

    expect(series[0]?.at).toBe(Date.parse('2026-10-09T00:00:00Z'))
  })
})

describe('trendWindow', () => {
  const now = Date.parse('2026-10-03T00:00:00Z')

  it('carries rows before the period over as the starting balance', () => {
    const series = balanceSeries([
      row(1, 100, '2026-01-01T00:00:00'),
      row(2, 10, '2026-09-30T00:00:00'),
    ])

    const window = trendWindow(series, 'month', now)

    expect(window.startBalance).toBe(100)
    expect(window.points.map((point) => point.balance)).toEqual([110])
  })

  it('choosing "all" starts from the first row', () => {
    const series = balanceSeries([row(1, 100, '2026-01-01T00:00:00')])

    const window = trendWindow(series, 'all', now)

    expect(window.start).toBe(Date.parse('2026-01-01T00:00:00Z'))
    expect(window.startBalance).toBe(0)
  })
})

describe('niceTicks', () => {
  it('covers the range with round ticks', () => {
    expect(niceTicks(0, 95)).toEqual([0, 50, 100])
  })

  it('crosses 0 when there is a negative balance', () => {
    const ticks = niceTicks(-30, 70)
    expect(ticks).toContain(0)
    expect(ticks[0]).toBeLessThanOrEqual(-30)
    expect(ticks.at(-1)).toBeGreaterThanOrEqual(70)
  })
})

describe('balanceForecast', () => {
  const now = Date.parse('2026-10-31T00:00:00Z')

  it('projects 1 week and 1 month ahead, assuming the last 30 days of growth continue', () => {
    // 100 before 30 days ago, then +60 over the 30 days (daily bonus +90 and −30 spent)
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

  it('divides by the days since the first record when records span under 30 days', () => {
    const forecast = balanceForecast(
      balanceSeries([row(2, 50, '2026-10-25T00:00:00'), row(1, 50, '2026-10-21T00:00:00')]),
      now,
    )

    expect(forecast?.basisDays).toBe(10)
    expect(forecast?.perDay).toBe(10)
  })

  it('the projection declines when spending exceeds earning', () => {
    const forecast = balanceForecast(
      balanceSeries([row(2, -150, '2026-10-15T00:00:00'), row(1, 300, '2026-09-01T00:00:00')]),
      now,
    )

    expect(forecast?.points.at(-1)?.balance).toBe(0)
  })

  it('does not project while records span less than a week', () => {
    expect(balanceForecast(balanceSeries([row(1, 100, '2026-10-26T00:00:00')]), now)).toBeNull()
    expect(balanceForecast([], now)).toBeNull()
  })

  it('does not count reversed records in the growth', () => {
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
