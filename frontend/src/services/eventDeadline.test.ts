import { describe, expect, it } from 'vitest'

import { daysUntil, localDate } from './eventDeadline'

describe('daysUntil', () => {
  it('期限の日は 0、前日は 1', () => {
    expect(daysUntil('2026-10-03', '2026-10-03')).toBe(0)
    expect(daysUntil('2026-10-03', '2026-10-02')).toBe(1)
  })

  it('月や年をまたいでも数えられる', () => {
    expect(daysUntil('2027-01-02', '2026-12-30')).toBe(3)
  })

  it('過ぎていれば負になる', () => {
    expect(daysUntil('2026-10-01', '2026-10-03')).toBe(-2)
  })
})

describe('localDate', () => {
  it('端末の暦の日付を YYYY-MM-DD で返す', () => {
    expect(localDate(new Date(2026, 0, 5, 23, 59))).toBe('2026-01-05')
  })
})
