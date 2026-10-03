import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { usePaged } from './usePaged'

const items = Array.from({ length: 45 }, (_, index) => index + 1)

describe('usePaged', () => {
  it('先頭のページから size 件ずつ切り出す', () => {
    const { result } = renderHook(() => usePaged(items, 20))

    expect(result.current.pageCount).toBe(3)
    expect(result.current.rows).toEqual(items.slice(0, 20))
  })

  it('最後のページは残りだけ', () => {
    const { result } = renderHook(() => usePaged(items, 20))

    act(() => {
      result.current.setPage(3)
    })

    expect(result.current.rows).toEqual([41, 42, 43, 44, 45])
  })

  it('件数が減ってページが無くなったら最後のページへ寄せる', () => {
    const { result, rerender } = renderHook(({ list }) => usePaged(list, 20), {
      initialProps: { list: items },
    })
    act(() => {
      result.current.setPage(3)
    })

    rerender({ list: items.slice(0, 30) })

    expect(result.current.page).toBe(2)
    expect(result.current.rows).toEqual(items.slice(20, 30))
  })
})
