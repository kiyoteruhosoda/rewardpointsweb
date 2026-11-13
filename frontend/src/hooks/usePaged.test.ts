import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { usePaged } from './usePaged'

const items = Array.from({ length: 45 }, (_, index) => index + 1)

describe('usePaged', () => {
  it('slices size items at a time from the first page', () => {
    const { result } = renderHook(() => usePaged(items, 20))

    expect(result.current.pageCount).toBe(3)
    expect(result.current.rows).toEqual(items.slice(0, 20))
  })

  it('the last page holds only the remainder', () => {
    const { result } = renderHook(() => usePaged(items, 20))

    act(() => {
      result.current.setPage(3)
    })

    expect(result.current.rows).toEqual([41, 42, 43, 44, 45])
  })

  it('moves to the last page when the count shrinks and the page disappears', () => {
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
