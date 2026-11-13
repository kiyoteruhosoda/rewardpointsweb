/**
 * Building and reading invitation URLs.
 *
 * What is checked: "it points to the join entry", "the code does not break as a URL", and
 * **the code never appears in the query** (ADR-0025). Back in the query, the reverse proxy's
 * access log would keep the code in plain text, letting anyone who can read logs join the family.
 */
import { beforeEach, describe, expect, it } from 'vitest'

import {
  invitationAcceptPath,
  invitationJoinPath,
  invitationSignInPath,
  invitationUrl,
  readInvitationCode,
  rememberInvitationCode,
  takeRememberedInvitationCode,
} from './invitationLink'

describe('invitationLink', () => {
  it('puts the code as a fragment on the join entry', () => {
    expect(invitationJoinPath('ABC123')).toBe('/join#code=ABC123')
    expect(invitationUrl('ABC123', 'child', 'https://points.example.com')).toBe(
      'https://points.example.com/join#code=ABC123',
    )
  })

  it('points parent invitations to the login screen (no new account; ADR-0048)', () => {
    for (const role of ['parent', 'owner'] as const) {
      expect(invitationUrl('ABC123', role, 'https://points.example.com')).toBe(
        'https://points.example.com/login#code=ABC123',
      )
    }
  })

  it('all 3 receiving screens carry it in the fragment', () => {
    // If any one goes back to `?`, everything from there lands in logs in plain text.
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

  it('escapes characters meaningful in URLs', () => {
    // Leaving `+` or `&` as is makes the opened page read it as a different code.
    expect(invitationJoinPath('a+b&c=d')).toBe('/join#code=a%2Bb%26c%3Dd')
    expect(readInvitationCode(invitationJoinPath('a+b&c=d').slice('/join'.length))).toBe('a+b&c=d')
  })

  it('adds no fragment without a code', () => {
    expect(invitationJoinPath('')).toBe('/join')
    expect(invitationSignInPath('   ')).toBe('/login')
  })

  it('does not produce `//join` from a trailing slash on the origin', () => {
    expect(invitationUrl('ABC123', 'child', 'https://points.example.com/')).toBe(
      'https://points.example.com/join#code=ABC123',
    )
  })

  it('extracts the code from the fragment, or empty if none', () => {
    expect(readInvitationCode('#code=ABC123')).toBe('ABC123')
    expect(readInvitationCode('#code=%20ABC123%20')).toBe('ABC123')
    expect(readInvitationCode('')).toBe('')
    expect(readInvitationCode('#other=1')).toBe('')
  })

  describe('holding the code during the IdP round trip', () => {
    beforeEach(() => {
      sessionStorage.clear()
    })

    it('a held code can be taken out only once', () => {
      rememberInvitationCode(' ABC123 ')

      expect(takeRememberedInvitationCode()).toBe('ABC123')
      expect(takeRememberedInvitationCode()).toBe('')
    })

    it('holding an empty value clears the previous one too', () => {
      rememberInvitationCode('ABC123')
      rememberInvitationCode('')

      expect(takeRememberedInvitationCode()).toBe('')
    })

    it('is empty when nothing is held (does not block a login without a code)', () => {
      expect(takeRememberedInvitationCode()).toBe('')
    })
  })
})
