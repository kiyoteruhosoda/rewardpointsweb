/**
 * 招待 URL の組み立てと読み取り。
 *
 * 見るのは「参加の入口へ向くこと」「コードが URL として壊れないこと」、そして
 * **コードがクエリに出ないこと**（ADR-0025）。クエリへ戻ると、リバースプロキシの
 * アクセスログに平文のコードが残り、ログを読める人が誰でも家族へ入れてしまう。
 */
import { describe, expect, it } from 'vitest'

import {
  invitationAcceptPath,
  invitationJoinPath,
  invitationSignInPath,
  invitationUrl,
  readInvitationCode,
} from './invitationLink'

describe('invitationLink', () => {
  it('参加の入口へ、断片としてコードを載せる', () => {
    expect(invitationJoinPath('ABC123')).toBe('/join#code=ABC123')
    expect(invitationUrl('ABC123', 'https://points.example.com')).toBe(
      'https://points.example.com/join#code=ABC123',
    )
  })

  it('受け取り側の 3 画面がどれも断片で運ぶ', () => {
    // どれか 1 つでも `?` に戻ると、そこから先は平文でログに載る。
    for (const path of [
      invitationJoinPath('ABC123'),
      invitationSignInPath('ABC123'),
      invitationAcceptPath('ABC123'),
    ]) {
      expect(path).not.toContain('?')
      expect(path).toContain('#code=ABC123')
    }
    expect(invitationSignInPath('ABC123')).toBe('/login#code=ABC123')
    expect(invitationAcceptPath('ABC123')).toBe('/families#code=ABC123')
  })

  it('URL で意味を持つ文字はエスケープする', () => {
    // `+` や `&` をそのまま置くと、開いた先で別のコードとして読まれる。
    expect(invitationJoinPath('a+b&c=d')).toBe('/join#code=a%2Bb%26c%3Dd')
    expect(readInvitationCode(invitationJoinPath('a+b&c=d').slice('/join'.length))).toBe('a+b&c=d')
  })

  it('コードが無ければ断片を付けない', () => {
    expect(invitationJoinPath('')).toBe('/join')
    expect(invitationSignInPath('   ')).toBe('/login')
  })

  it('出所の末尾のスラッシュで `//join` にしない', () => {
    expect(invitationUrl('ABC123', 'https://points.example.com/')).toBe(
      'https://points.example.com/join#code=ABC123',
    )
  })

  it('断片からコードを取り出す。無ければ空', () => {
    expect(readInvitationCode('#code=ABC123')).toBe('ABC123')
    expect(readInvitationCode('#code=%20ABC123%20')).toBe('ABC123')
    expect(readInvitationCode('')).toBe('')
    expect(readInvitationCode('#other=1')).toBe('')
  })
})
