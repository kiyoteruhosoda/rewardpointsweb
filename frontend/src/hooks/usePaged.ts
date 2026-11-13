/**
 * Splits a list into pages of *size* items.
 *
 * When a reload shrinks the count (a cancellation, a change on another device), move to
 * the last page so the view is not stranded on a page past the end.
 */
import { useState } from 'react'

export function usePaged<T>(items: readonly T[], size: number) {
  const [requested, setPage] = useState(1)
  const pageCount = Math.max(1, Math.ceil(items.length / size))
  const page = Math.min(requested, pageCount)
  const start = (page - 1) * size
  return {
    page,
    pageCount,
    rows: items.slice(start, start + size),
    setPage,
  }
}
