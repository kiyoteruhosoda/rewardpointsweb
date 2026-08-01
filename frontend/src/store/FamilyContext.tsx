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
 *
 * **読めなかったことを「所属していない」と言わない。** 一覧は引けたのに詳細で
 * 落ちた（5xx・オフライン）ときに `family` を null にすると、画面は「家族が
 * ない」と判断して作成・参加を出し、押せば必ず `already_belongs_to_family` に
 * なる。読めなかったことは `failed` として別に伝える。
 */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

import { families, type FamilyDetail } from '../services/families'
import { useAuth } from './AuthContext'

export interface FamilyValue {
  /** 所属している家族。どこにも所属していなければ null。 */
  family: FamilyDetail | null
  /** 読み込めなかった。所属の有無は分からない（「所属していない」ではない）。 */
  failed: boolean
  /** 最初の取得が終わるまで真。「家族がない」との区別に使う。 */
  loading: boolean
  reload: () => Promise<void>
}

/** 取り違えを防ぐため、家族と失敗はいつも 1 組で入れ替える。 */
interface Loaded {
  family: FamilyDetail | null
  failed: boolean
}

const NONE: Loaded = { family: null, failed: false }

/** テストが状態を差し替えて描画できるよう公開する（本番の生成は FamilyProvider）。 */
export const FamilyContext = createContext<FamilyValue | null>(null)

export function FamilyProvider({ children }: { children: ReactNode }) {
  const { hasScope } = useAuth()
  const canView = hasScope('family:view')
  const [loaded, setLoaded] = useState<Loaded>(NONE)
  const [loading, setLoading] = useState(true)

  const reload = useCallback(async () => {
    if (!canView) {
      setLoaded(NONE)
      setLoading(false)
      return
    }
    try {
      const list = await families.list()
      const first = list[0]
      setLoaded({ family: first ? await families.view(first.id) : null, failed: false })
    } catch {
      setLoaded({ family: null, failed: true })
    } finally {
      setLoading(false)
    }
  }, [canView])

  useEffect(() => {
    void reload()
  }, [reload])

  return (
    <FamilyContext.Provider value={{ ...loaded, loading, reload }}>
      {children}
    </FamilyContext.Provider>
  )
}

export function useFamily(): FamilyValue {
  const value = useContext(FamilyContext)
  if (!value) throw new Error('useFamily must be used within a FamilyProvider')
  return value
}
