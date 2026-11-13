import { describe, expect, it } from 'vitest'

import { daysUntil, localDate } from './eventDeadline'

describe('daysUntil', () => {
  it('is 0 on the deadline day and 1 the day before', () => {
    expect(daysUntil('2026-10-03', '2026-10-03')).toBe(0)
    expect(daysUntil('2026-10-03', '2026-10-02')).toBe(1)
  })

  it('counts across months and years', () => {
    expect(daysUntil('2027-01-02', '2026-12-30')).toBe(3)
  })

  it('is negative once past', () => {
    expect(daysUntil('2026-10-01', '2026-10-03')).toBe(-2)
  })
})

describe('localDate', () => {
  it('returns the device calendar date as YYYY-MM-DD', () => {
    expect(localDate(new Date(2026, 0, 5, 23, 59))).toBe('2026-01-05')
  })
})
