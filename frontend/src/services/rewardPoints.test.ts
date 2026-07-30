/** サーバーの時刻（tz なしの UTC）の解釈。 */
import { describe, expect, it } from 'vitest'

import { parseUtc } from './rewardPoints'

describe('parseUtc', () => {
  it('タイムゾーンの無い時刻を UTC として読む', () => {
    // そのまま new Date() に渡すと実行環境のローカル時刻として解釈され、時差の分ずれる
    expect(parseUtc('2026-07-30T09:00:00').toISOString()).toBe('2026-07-30T09:00:00.000Z')
  })

  it('Z 付きはそのまま読む', () => {
    expect(parseUtc('2026-07-30T09:00:00Z').toISOString()).toBe('2026-07-30T09:00:00.000Z')
  })

  it('オフセット付きはその指定に従う', () => {
    expect(parseUtc('2026-07-30T18:00:00+09:00').toISOString()).toBe('2026-07-30T09:00:00.000Z')
  })

  it('マイクロ秒付きでも UTC として読む', () => {
    expect(parseUtc('2026-07-30T09:00:00.123456').toISOString()).toBe('2026-07-30T09:00:00.123Z')
  })
})
