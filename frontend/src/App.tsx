import { useCallback, useState } from 'react'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'

import { Footer } from './components/Footer'
import { Header } from './components/Header'
import { Sidebar } from './components/Sidebar'
import { useI18n } from './i18n'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { ConfigPage } from './pages/ConfigPage'
import { DashboardPage } from './pages/DashboardPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { LoginPage } from './pages/LoginPage'
import { MemberPointsPage } from './pages/MemberPointsPage'
import { MembersPage } from './pages/MembersPage'
import { PermissionsPage } from './pages/PermissionsPage'
import { ProfilePage } from './pages/ProfilePage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { RolesPage } from './pages/RolesPage'
import { SecurityPage } from './pages/SecurityPage'
import { SystemLogsPage } from './pages/SystemLogsPage'
import { UsersPage } from './pages/UsersPage'
import { useAuth } from './store/AuthContext'

function RequireAuth() {
  const { user, loading } = useAuth()
  const { t } = useI18n()
  // 狭い画面でナビゲーションを引き出しにするための開閉状態。広い画面では
  // ナビゲーションが出たままなので、この値は使われない（index.css 側で無視される）。
  const [navOpen, setNavOpen] = useState(false)
  const toggleNav = useCallback(() => {
    setNavOpen((open) => !open)
  }, [])
  const closeNav = useCallback(() => {
    setNavOpen(false)
  }, [])

  if (loading) return <p className="loading">{t('common.loading')}</p>
  if (!user) return <Navigate to="/login" replace />
  return (
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
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/members" element={<MembersPage />} />
        <Route path="/members/:memberId" element={<MemberPointsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/change-password" element={<ChangePasswordPage />} />
        <Route path="/security" element={<SecurityPage />} />
        <Route path="/admin/users" element={<UsersPage />} />
        <Route path="/admin/roles" element={<RolesPage />} />
        <Route path="/admin/permissions" element={<PermissionsPage />} />
        <Route path="/admin/config" element={<ConfigPage />} />
        <Route path="/admin/logs" element={<SystemLogsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
