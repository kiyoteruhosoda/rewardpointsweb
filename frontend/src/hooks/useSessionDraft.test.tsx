/** Keeps drafts across the login round trip (ADR-0058). */
import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { clearSessionDrafts, useSessionDraft, useSessionValue } from './useSessionDraft'

describe('useSessionDraft', () => {
  afterEach(() => {
    window.sessionStorage.clear()
  })

  it('keeps a written value even when the screen is rebuilt (back from the round trip)', () => {
    const first = renderHook(() => useSessionDraft<{ title: string }>('notes'))
    act(() => {
      first.result.current[1]({ title: '書きかけ' })
    })
    first.unmount()

    const again = renderHook(() => useSessionDraft<{ title: string }>('notes'))
    expect(again.result.current[0]).toEqual({ title: '書きかけ' })
  })

  it('clears it when set to null (saved or closed)', () => {
    const { result } = renderHook(() => useSessionDraft<{ title: string }>('notes'))
    act(() => {
      result.current[1]({ title: 'x' })
    })
    act(() => {
      result.current[1](null)
    })
    expect(window.sessionStorage.getItem('draft:notes')).toBeNull()
  })

  it('can be updated with a function', () => {
    const { result } = renderHook(() => useSessionDraft<{ n: number }>('count', { n: 1 }))
    act(() => {
      result.current[1]((current) => ({ n: (current?.n ?? 0) + 1 }))
    })
    expect(result.current[0]).toEqual({ n: 2 })
  })

  it('clears everything on sign-out (other values are kept)', () => {
    window.sessionStorage.setItem('draft:a', '{}')
    window.sessionStorage.setItem('ssoSilentTried', '1')
    clearSessionDrafts()
    expect(window.sessionStorage.getItem('draft:a')).toBeNull()
    expect(window.sessionStorage.getItem('ssoSilentTried')).toBe('1')
  })

  it('a single field starts from the empty value and keeps a written value when coming back', () => {
    const first = renderHook(() => useSessionValue('users.email', ''))
    expect(first.result.current[0]).toBe('')
    act(() => {
      first.result.current[1]('a@example.com')
    })
    first.unmount()

    const again = renderHook(() => useSessionValue('users.email', ''))
    expect(again.result.current[0]).toBe('a@example.com')
  })

  it('a single field can also be updated with a function', () => {
    const { result } = renderHook(() => useSessionValue<string[]>('users.roles', []))
    act(() => {
      result.current[1]((current) => [...current, 'member'])
    })
    expect(result.current[0]).toEqual(['member'])
  })
})
