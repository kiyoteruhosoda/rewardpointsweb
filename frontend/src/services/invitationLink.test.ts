/**
 * 招待 URL の組み立て。
 *
 * 見るのは「参加の入口へ向くこと」「コードが URL として壊れないこと」の 2 点。
 * どちらかが崩れると、受け取った人は開いた先でコードを打ち直す羽目になる。
 */
import { describe, expect, it } from 'vitest'

import { invitationJoinPath, invitationUrl } from './invitationLink'

describe('invitationLink', () => {
  it('参加の入口へコードを載せる', () => {
    expect(invitationJoinPath('ABC123')).toBe('/join?code=ABC123')
    expect(invitationUrl('ABC123', 'https://points.example.com')).toBe(
      'https://points.example.com/join?code=ABC123',
    )
  })

  it('URL で意味を持つ文字はエスケープする', () => {
    // `+` や `&` をそのまま置くと、開いた先で別のコードとして読まれる。
    expect(invitationJoinPath('a+b&c=d')).toBe('/join?code=a%2Bb%26c%3Dd')
  })

  it('出所の末尾のスラッシュで `//join` にしない', () => {
    expect(invitationUrl('ABC123', 'https://points.example.com/')).toBe(
      'https://points.example.com/join?code=ABC123',
    )
  })
})
