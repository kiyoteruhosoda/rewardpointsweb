/** 書きかけをログインの往復をまたいで残す（ADR-0058）。 */
import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { clearSessionDrafts, useSessionDraft, useSessionValue } from './useSessionDraft'

describe('useSessionDraft', () => {
  afterEach(() => {
    window.sessionStorage.clear()
  })

  it('書いた値は、画面を作り直しても（往復から戻っても）残る', () => {
    const first = renderHook(() => useSessionDraft<{ title: string }>('notes'))
    act(() => {
      first.result.current[1]({ title: '書きかけ' })
    })
    first.unmount()

    const again = renderHook(() => useSessionDraft<{ title: string }>('notes'))
    expect(again.result.current[0]).toEqual({ title: '書きかけ' })
  })

  it('null にしたら（保存した・閉じた）消す', () => {
    const { result } = renderHook(() => useSessionDraft<{ title: string }>('notes'))
    act(() => {
      result.current[1]({ title: 'x' })
    })
    act(() => {
      result.current[1](null)
    })
    expect(window.sessionStorage.getItem('draft:notes')).toBeNull()
  })

  it('関数で更新できる', () => {
    const { result } = renderHook(() => useSessionDraft<{ n: number }>('count', { n: 1 }))
    act(() => {
      result.current[1]((current) => ({ n: (current?.n ?? 0) + 1 }))
    })
    expect(result.current[0]).toEqual({ n: 2 })
  })

  it('サインアウトしたら全部消す（ほかの値は残す）', () => {
    window.sessionStorage.setItem('draft:a', '{}')
    window.sessionStorage.setItem('ssoSilentTried', '1')
    clearSessionDrafts()
    expect(window.sessionStorage.getItem('draft:a')).toBeNull()
    expect(window.sessionStorage.getItem('ssoSilentTried')).toBe('1')
  })

  it('欄 1 つ分は空の値から始まり、書いた値が戻ってきても残る', () => {
    const first = renderHook(() => useSessionValue('users.email', ''))
    expect(first.result.current[0]).toBe('')
    act(() => {
      first.result.current[1]('a@example.com')
    })
    first.unmount()

    const again = renderHook(() => useSessionValue('users.email', ''))
    expect(again.result.current[0]).toBe('a@example.com')
  })

  it('欄 1 つ分も関数で更新できる', () => {
    const { result } = renderHook(() => useSessionValue<string[]>('users.roles', []))
    act(() => {
      result.current[1]((current) => [...current, 'member'])
    })
    expect(result.current[0]).toEqual(['member'])
  })
})
