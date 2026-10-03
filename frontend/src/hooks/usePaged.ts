/**
 * 一覧を *size* 件ずつのページに分ける。
 *
 * 読み直して件数が減った（取り消し・別の端末での変更）ときは、はみ出したページに
 * 取り残されないよう最後のページへ寄せる。
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
