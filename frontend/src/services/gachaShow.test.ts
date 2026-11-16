import { describe, expect, it } from 'vitest'

import { TURN_MS, turnDelay } from './gachaShow'

describe('turnDelay', () => {
  it('keeps the handle turning for the full time even when the answer is instant', () => {
    expect(turnDelay(1000, 1000, false)).toBe(TURN_MS)
  })

  it('only waits for what is left when the answer was slow', () => {
    expect(turnDelay(1000, 1000 + TURN_MS - 500, false)).toBe(500)
    expect(turnDelay(1000, 1000 + TURN_MS + 3000, false)).toBe(0)
  })

  it('does not wait for people who ask for reduced motion', () => {
    expect(turnDelay(1000, 1000, true)).toBe(0)
  })
})
