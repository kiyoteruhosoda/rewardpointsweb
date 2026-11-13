/**
 * The frame at the top of the screen. Holds only the app name and actions for the signed-in account.
 *
 * Language/theme switching is in profile settings (ProfilePage), not here.
 * On narrow screens it would not fit on this row; two `<select>`s whose width depends on option text
 * would push even the title out.
 *
 * On narrow screens the account entry is just a circle with the initial (display in index.css).
 * User names vary in length, and longer names take up the right side and push the title out.
 * The user name remains for screen readers and the mouse cursor (`aria-label` / `title`).
 */
import { Link } from 'react-router-dom'

import { useI18n } from '../i18n'
import { useAuth } from '../store/AuthContext'
import { NAV_ID } from './Sidebar'

interface Props {
  navOpen: boolean
  onToggleNav: () => void
}

/**
 * Initial shown in the circle.
 *
 * Taken by code point so names starting with emoji or combining characters are not cut midway
 * (`username[0]` can yield a broken character).
 */
function initialOf(name: string): string {
  const [first] = Array.from(name.trim())
  return (first ?? '?').toUpperCase()
}

export function Header({ navOpen, onToggleNav }: Props) {
  const { t } = useI18n()
  const { user, logout } = useAuth()

  return (
    <header className="header">
      {/* Drawer toggle. Shown only on narrow screens (visibility decided in index.css). */}
      <button
        type="button"
        className="nav-toggle"
        aria-label={t('nav.menu')}
        aria-controls={NAV_ID}
        aria-expanded={navOpen}
        onClick={onToggleNav}
      >
        <span aria-hidden="true">☰</span>
      </button>
      <Link to="/" className="header-title">
        {t('app.title')}
      </Link>
      <div className="header-actions">
        {user && (
          <>
            <Link
              to="/profile"
              className="header-account"
              title={user.username}
              aria-label={t('nav.account', { name: user.username })}
            >
              <span className="header-account-initial" aria-hidden="true">
                {initialOf(user.username)}
              </span>
              <span className="header-account-name">{user.username}</span>
            </Link>
            <button onClick={logout}>{t('nav.logout')}</button>
          </>
        )}
      </div>
    </header>
  )
}
