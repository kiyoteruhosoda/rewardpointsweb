/**
 * 画面が手元に戻ってきたときに読み直す。
 *
 * ポイントは同じ家族の複数の端末から記録される。ホーム画面から開いた PWA は
 * タブが何日も生きたままになるので、開いた時点の残高を持ち続けると、別の親が
 * 足したポイントがいつまでも出ない。「見に戻ってきた」瞬間を取得のきっかけに
 * する。
 *
 * 裏に回っているあいだは読み直さない（見ていない画面のために通信しない）。
 * 圏外から戻ったとき（`online`）も同じ扱いにする — オフラインで出していたのは
 * キャッシュ（ADR-0015）なので、回線が戻ったら最新へ差し替える。
 *
 * 読み直しの中身は呼び出し側が決める。失敗の扱いも呼び出し側に任せるため、
 * ここでは待たずに投げっぱなしにする（`refresh` は自分で失敗を処理すること）。
 */
import { useEffect } from 'react'

export function useRefreshOnReturn(refresh: () => Promise<void>): void {
  useEffect(() => {
    const refreshIfVisible = () => {
      if (document.visibilityState === 'visible') void refresh()
    }
    document.addEventListener('visibilitychange', refreshIfVisible)
    window.addEventListener('online', refreshIfVisible)
    return () => {
      document.removeEventListener('visibilitychange', refreshIfVisible)
      window.removeEventListener('online', refreshIfVisible)
    }
  }, [refresh])
}
