/**
 * ログイン中のアカウントが所属する家族。
 *
 * 所属できる家族は 1 つまで（ADR-0013）なので、状態も 1 つで足りる。ここに
 * 集めるのは、ナビゲーション（子の一覧）・ダッシュボード・家族設定が同じ内容を
 * 見るため。画面ごとに取得すると、子を追加した直後に左のナビゲーションだけが
 * 古いままになる。
 *
 * 取得は `family:view` を持つ人にだけ行う。持たないアカウントで呼ぶと 403 が
 * 「家族がない」に化けて、案内の文言が嘘になる。
 */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

import { families, type FamilyDetail } from '../services/families'
import { useAuth } from './AuthContext'

export interface FamilyValue {
  /** 所属している家族。どこにも所属していなければ null。 */
  family: FamilyDetail | null
  /** 最初の取得が終わるまで真。「家族がない」との区別に使う。 */
  loading: boolean
  reload: () => Promise<void>
}

/** テストが状態を差し替えて描画できるよう公開する（本番の生成は FamilyProvider）。 */
export const FamilyContext = createContext<FamilyValue | null>(null)

export function FamilyProvider({ children }: { children: ReactNode }) {
  const { hasScope } = useAuth()
  const canView = hasScope('family:view')
  const [family, setFamily] = useState<FamilyDetail | null>(null)
  const [loading, setLoading] = useState(true)

  const reload = useCallback(async () => {
    if (!canView) {
      setFamily(null)
      setLoading(false)
      return
    }
    try {
      const list = await families.list()
      const first = list[0]
      setFamily(first ? await families.view(first.id) : null)
    } catch {
      // 取得できないこと自体は画面を壊さない（オフライン・権限の変化）。
      // 「家族がない」と同じ見え方になり、作成・参加の入口が出る。
      setFamily(null)
    } finally {
      setLoading(false)
    }
  }, [canView])

  useEffect(() => {
    void reload()
  }, [reload])

  return (
    <FamilyContext.Provider value={{ family, loading, reload }}>{children}</FamilyContext.Provider>
  )
}

export function useFamily(): FamilyValue {
  const value = useContext(FamilyContext)
  if (!value) throw new Error('useFamily must be used within a FamilyProvider')
  return value
}
