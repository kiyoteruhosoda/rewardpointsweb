import { useCallback, useEffect, useState } from 'react'
import { Navigate, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { Footer } from './components/Footer'
import { Header } from './components/Header'
import { RequireScope } from './components/RequireScope'
import { Sidebar } from './components/Sidebar'
import { useI18n } from './i18n'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { ConfigPage } from './pages/ConfigPage'
import { DashboardPage } from './pages/DashboardPage'
import { DisplayApprovePage } from './pages/DisplayApprovePage'
import { DisplayPage } from './pages/DisplayPage'
import { DisplaysPage } from './pages/DisplaysPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { LoginPage } from './pages/LoginPage'
import { FamiliesPage } from './pages/FamiliesPage'
import { FamilyPage } from './pages/FamilyPage'
import { LedgerPage } from './pages/LedgerPage'
import { PermissionsPage } from './pages/PermissionsPage'
import { ProfilePage } from './pages/ProfilePage'
import { RedeemInvitationPage } from './pages/RedeemInvitationPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { RewardEventsPage } from './pages/RewardEventsPage'
import { RolesPage } from './pages/RolesPage'
import { SsoCallbackPage } from './pages/SsoCallbackPage'
import { SecurityPage } from './pages/SecurityPage'
import { SystemLogsPage } from './pages/SystemLogsPage'
import { UsersPage } from './pages/UsersPage'
import { displayCredential } from './services/api'
import { APPROVE_PATH, rememberPendingApproval, takePendingApproval } from './services/display'
import { useAuth } from './store/AuthContext'
import { FamilyProvider } from './store/FamilyContext'

function RequireAuth() {
  const { user, loading, unreachable } = useAuth()
  const { t } = useI18n()
  const location = useLocation()
  // 狭い画面でナビゲーションを引き出しにするための開閉状態。広い画面では
  // ナビゲーションが出たままなので、この値は使われない（index.css 側で無視される）。
  const [navOpen, setNavOpen] = useState(false)
  const toggleNav = useCallback(() => {
    setNavOpen((open) => !open)
  }, [])
  const closeNav = useCallback(() => {
    setNavOpen(false)
  }, [])
  const navigate = useNavigate()

  // 表示端末の QR コードから来て、ログインを挟んだ人を承認の画面へ戻す（ADR-0047）
  useEffect(() => {
    if (!user) return
    const pending = takePendingApproval()
    if (pending !== null) navigate(pending, { replace: true })
  }, [user, navigate])

  if (loading) return <p className="loading">{t('common.loading')}</p>
  // 届かないだけならログイン画面へ送らない（リリース中など。つながれば自動で戻る。ADR-0046）
  if (!user && unreachable)
    return (
      <p className="loading">
        <span className="spinner" aria-hidden="true" /> {t('common.unreachable')}
      </p>
    )
  if (!user) {
    // ペアリング済みの表示端末は、ホーム画面のアイコンが / を開いても表示の画面へ（ADR-0047）
    if (displayCredential() !== null) return <Navigate to="/display" replace />
    if (location.pathname === APPROVE_PATH) rememberPendingApproval(location.hash)
    return <Navigate to="/login" replace />
  }
  // 表示端末は表示の画面だけを出す（ADR-0047）
  if (user.display_device) return <Navigate to="/display" replace />
  // 一時パスワードでのログイン中は、変更を終えるまで他の画面へ行かせない
  // （サーバー側も同じ関門を持つ。ADR-0011）
  if (user.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }
  // 家族はナビゲーション・ダッシュボード・家族設定が同じものを見る。ログイン後の
  // 画面をまとめて包み、出所を 1 つに保つ（FamilyContext）。同じ瞬間に何度も
  // 取りには行かないが、画面を移るたびには読み直す（ADR-0021）。
  return (
    <FamilyProvider>
      <div className="layout">
        <Header navOpen={navOpen} onToggleNav={toggleNav} />
        <div className="layout-body">
          <Sidebar open={navOpen} onClose={closeNav} />
          <main className="content">
            <Outlet />
          </main>
        </div>
        <Footer />
      </div>
    </FamilyProvider>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      {/* IdP からの戻り。引き換え券をトークンへ換えるだけの中継（ADR-0029） */}
      <Route path="/login/sso" element={<SsoCallbackPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/join" element={<RedeemInvitationPage />} />
      {/* 表示端末（サイネージ）。ログインの画面を通らない（ADR-0047） */}
      <Route path="/display" element={<DisplayPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/families" element={<FamiliesPage />} />
        <Route path="/families/:familyId" element={<FamilyPage />} />
        <Route path="/families/:familyId/ledgers/:ledgerId" element={<LedgerPage />} />
        <Route path="/families/:familyId/ledgers/:ledgerId/events" element={<RewardEventsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/change-password" element={<ChangePasswordPage />} />
        <Route path="/security" element={<SecurityPage />} />
        <Route path="/admin/users" element={<UsersPage />} />
        <Route path="/admin/roles" element={<RolesPage />} />
        <Route path="/admin/permissions" element={<PermissionsPage />} />
        <Route path="/admin/config" element={<ConfigPage />} />
        <Route path="/admin/logs" element={<SystemLogsPage />} />
        <Route element={<RequireScope scopes={['display:approve']} />}>
          <Route path="/admin/displays" element={<DisplaysPage />} />
          <Route path={APPROVE_PATH} element={<DisplayApprovePage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
