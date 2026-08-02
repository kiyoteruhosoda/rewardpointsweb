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
 *
 * ここには残高も入る。**ポイントを変えたら `reload` を呼ぶ**（ADR-0021）。
 * 呼ばないと、記録した画面だけが新しい残高になり、ダッシュボード・
 * ナビゲーション・家族設定は古い数字を出したままになる。
 *
 * 取得は 1 回きりにしない。画面を移るたび・手元に戻るたびに読み直す。ログイン中に
 * 1 回だけだと、別の端末や別のタブで足されたポイントがブラウザの再読込まで
 * 出てこない。読み直しても表示は消さないので、画面はちらつかない。
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useLocation } from 'react-router-dom'

import { useRefreshOnReturn } from '../hooks/useRefreshOnReturn'
import { families, type FamilyDetail } from '../services/families'
import { useAuth } from './AuthContext'

export interface FamilyValue {
  /** 所属している家族。どこにも所属していなければ null。 */
  family: FamilyDetail | null
  /**
   * 読み込めず、出せるものが何も無い。所属の有無は分からない
   * （「所属していない」ではない）。一度読めた後の読み直しが失敗しても、
   * 前の内容を出したままにするので、ここは偽のままになる（ADR-0021）。
   */
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
  const { pathname } = useLocation()
  const [loaded, setLoaded] = useState<Loaded>(NONE)
  const [loading, setLoading] = useState(true)
  /** 何番目の取得か。追い越された（古い）応答を捨てるために持つ。 */
  const latest = useRef(0)

  const reload = useCallback(async () => {
    // 読み直しは重なり得る（記録の直後に画面を移る等）。先に始めた取得が後から
    // 届いても、新しい取得の結果を古い内容で上書きしない。
    const ticket = ++latest.current
    const isLatest = () => ticket === latest.current

    if (!canView) {
      setLoaded(NONE)
      setLoading(false)
      return
    }
    try {
      const list = await families.list()
      const first = list[0]
      const family = first ? await families.view(first.id) : null
      if (isLatest()) setLoaded({ family, failed: false })
    } catch {
      if (!isLatest()) return
      // 読み直しに失敗しても、すでに読めている家族は捨てない（ADR-0021）。手元に
      // 戻った瞬間の一時的な不通で残高・子への入口が消えると、家族から外された
      // ようにしか見えない。「読めなかった」と伝えるのは、出せるものが無いときだけ。
      setLoaded((current) => (current.family ? current : { family: null, failed: true }))
    } finally {
      setLoading(false)
    }
  }, [canView])

  // 最初の 1 回と、**画面を移るたび**に読み直す。ログイン中に 1 回だけ取ると、
  // 別の端末・別のタブで足されたポイントはブラウザを再読込するまで出てこない
  // （利用者からは「ダッシュボードに古い値が残る」に見える）。表示は消さないので、
  // 読み直しは画面のちらつきにならず、値が届いたときに入れ替わるだけ。
  useEffect(() => {
    void reload()
  }, [reload, pathname])

  // 別の端末（もう一人の親・子ども本人）の記録は、こちらの画面には届かない。
  // 手元に戻ってきたときに読み直して、開きっぱなしの残高が居座らないようにする。
  useRefreshOnReturn(reload)

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
