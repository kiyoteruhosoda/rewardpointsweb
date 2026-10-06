/**
 * scope を持たない人を入口へ戻す（ルートの包み）。
 *
 * メニューに出さないだけだと、URL を直接開いた人に画面の枠と操作のボタンが出て、
 * 押すと 403 になる。表示端末の画面は運用管理者だけのもの（ADR-0047）。
 */
import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../store/AuthContext'

export function RequireScope({ scopes }: { scopes: string[] }) {
  const { hasScope } = useAuth()
  if (!hasScope(...scopes)) return <Navigate to="/" replace />
  return <Outlet />
}
