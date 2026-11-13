/**
 * Do not lose the destination across the sign-in round trip (ADR-0051).
 */
import { describe, expect, it } from 'vitest'

import { sanitizeRedirectTo, signInPathFor } from './returnTo'

describe('sanitizeRedirectTo', () => {
  it('passes in-site absolute paths through with the query', () => {
    expect(sanitizeRedirectTo('/admin/logs?q=a%2Fb')).toBe('/admin/logs?q=a%2Fb')
  })

  it.each([
    [null],
    [''],
    ['families'],
    ['https://evil.example/'],
    ['//evil.example/'],
    ['/\\evil.example/'],
    ['/families\r\nSet-Cookie: x'],
    [`/${'a'.repeat(255)}`],
  ])('falls back to landing for external, malformed or too long values (%j)', (candidate) => {
    expect(sanitizeRedirectTo(candidate)).toBe('/')
  })
})

describe('signInPathFor', () => {
  it('puts the path and query being opened into redirect_to', () => {
    expect(signInPathFor({ pathname: '/admin/logs', search: '?q=a&page=2' })).toBe(
      '/login?redirect_to=%2Fadmin%2Flogs%3Fq%3Da%26page%3D2',
    )
  })

  it('adds no destination when coming from the landing page', () => {
    expect(signInPathFor({ pathname: '/', search: '' })).toBe('/login')
  })
})
