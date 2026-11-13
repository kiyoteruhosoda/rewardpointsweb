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
import { signInPathFor } from './services/returnTo'
import { useAuth } from './store/AuthContext'
import { FamilyProvider } from './store/FamilyContext'

function RequireAuth() {
  const { user, loading, unreachable } = useAuth()
  const { t } = useI18n()
  const location = useLocation()
  // Open/closed state for turning the navigation into a drawer on narrow screens. On wide screens
  // the navigation stays visible, so this value is unused (index.css ignores it).
  const [navOpen, setNavOpen] = useState(false)
  const toggleNav = useCallback(() => {
    setNavOpen((open) => !open)
  }, [])
  const closeNav = useCallback(() => {
    setNavOpen(false)
  }, [])
  const navigate = useNavigate()

  // Return someone who came from a display device's QR code and signed in to the approval screen (ADR-0047)
  useEffect(() => {
    if (!user) return
    const pending = takePendingApproval()
    if (pending !== null) void navigate(pending, { replace: true })
  }, [user, navigate])

  if (loading) return <p className="loading">{t('common.loading')}</p>
  // Don't send to the login screen when merely unreachable (e.g. during a release; returns automatically once connected; ADR-0046)
  if (!user && unreachable)
    return (
      <p className="loading">
        <span className="spinner" aria-hidden="true" /> {t('common.unreachable')}
      </p>
    )
  if (!user) {
    // A paired display device goes to the display screen even when the home screen icon opens / (ADR-0047)
    if (displayCredential() !== null) return <Navigate to="/display" replace />
    if (location.pathname === APPROVE_PATH) rememberPendingApproval(location.hash)
    // Send along the screen they were trying to open (ADR-0051). Without it, login lands on the landing page.
    return <Navigate to={signInPathFor(location)} replace />
  }
  // A display device shows only the display screen (ADR-0047)
  if (user.display_device) return <Navigate to="/display" replace />
  // While signed in with a temporary password, no other screens until the change is done
  // (the server has the same gate; ADR-0011)
  if (user.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }
  // Navigation, dashboard and family settings all see the same family. Wrap the post-login
  // screens together to keep a single source (FamilyContext). It does not fetch several times
  // at the same moment, but reloads on every screen change (ADR-0021).
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
      {/* Return from the IdP. A relay that only exchanges the ticket for tokens (ADR-0029) */}
      <Route path="/login/sso" element={<SsoCallbackPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/join" element={<RedeemInvitationPage />} />
      {/* Display device (signage). Does not go through the login screen (ADR-0047) */}
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
