import { describe, expect, it } from 'vitest'

import { gridColumns, stickerLook } from './stickerSheet'

describe('gridColumns', () => {
  it.each([
    [1, 1],
    [5, 5],
    [6, 3],
    [10, 5],
    [12, 4],
    [20, 5],
    [30, 6],
    [50, 10],
  ])('%i cells are laid out in %i columns', (count, columns) => {
    expect(gridColumns(count)).toBe(columns)
  })

  it('does not lay out more than the maximum across', () => {
    for (let count = 1; count <= 50; count++) {
      expect(gridColumns(count)).toBeLessThanOrEqual(10)
    }
  })
})

describe('stickerLook', () => {
  it('the same number on the same card always looks the same', () => {
    expect(stickerLook(7, 3)).toEqual(stickerLook(7, 3))
  })

  it('adjacent numbers get different shapes', () => {
    expect(stickerLook(7, 3).shape).not.toBe(stickerLook(7, 4).shape)
  })

  it('the tilt stays within what hand-placing would give', () => {
    for (let number = 1; number <= 50; number++) {
      expect(Math.abs(stickerLook(3, number).tilt)).toBeLessThanOrEqual(12)
    }
  })
})
