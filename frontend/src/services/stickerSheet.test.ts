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
  ])('%i マスは %i 列に並ぶ', (count, columns) => {
    expect(gridColumns(count)).toBe(columns)
  })

  it('上限より多くは横に並べない', () => {
    for (let count = 1; count <= 50; count++) {
      expect(gridColumns(count)).toBeLessThanOrEqual(10)
    }
  })
})

describe('stickerLook', () => {
  it('同じカードの同じ番号はいつも同じ見た目になる', () => {
    expect(stickerLook(7, 3)).toEqual(stickerLook(7, 3))
  })

  it('隣り合う番号は違う形になる', () => {
    expect(stickerLook(7, 3).shape).not.toBe(stickerLook(7, 4).shape)
  })

  it('傾きは手で貼った程度に収まる', () => {
    for (let number = 1; number <= 50; number++) {
      expect(Math.abs(stickerLook(3, number).tilt)).toBeLessThanOrEqual(12)
    }
  })
})
