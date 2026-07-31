/**
 * プロフィール設定。自分のアカウント・表示設定（言語・テーマ）・セキュリティ、
 * そして権限があるときだけシステム管理への入口をここへ集める。
 *
 * 管理者は親（家族）なので、日々のナビゲーションにはシステム関連を出さず、
 * この画面の一番下にだけ置く。言語とテーマの保存先は localStorage で、
 * サーバーへは送らない（i18n/index.tsx・theme/index.tsx）。
 */
import { Link } from 'react-router-dom'

import { LOCALE_LABELS, useI18n, type Locale } from '../i18n'
import { useAuth } from '../store/AuthContext'
import { THEME_PREFERENCES, useTheme, type ThemePreference } from '../theme'

interface AdminLink {
  to: string
  labelKey: string
  scopes: string[]
}

/** システム管理の入口。Sidebar には出さず、scope を持つ人にだけここで見せる。 */
const ADMIN_LINKS: AdminLink[] = [
  { to: '/admin/users', labelKey: 'nav.users', scopes: ['user:manage'] },
  { to: '/admin/roles', labelKey: 'nav.roles', scopes: ['role:manage'] },
  { to: '/admin/permissions', labelKey: 'nav.permissions', scopes: ['permission:manage'] },
  { to: '/admin/config', labelKey: 'nav.config', scopes: ['admin:system-settings'] },
  { to: '/admin/logs', labelKey: 'nav.logs', scopes: ['log:view'] },
]

export function ProfilePage() {
  const { t, locale, locales, setLocale } = useI18n()
  const { theme, setTheme } = useTheme()
  const { user, hasScope } = useAuth()
  if (!user) return null

  const adminLinks = ADMIN_LINKS.filter((link) => hasScope(...link.scopes))

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{t('profile.title')}</h1>
      </div>

      <section className="card">
        <h2>{t('profile.account')}</h2>
        <div className="account-row">
          <span className="avatar" aria-hidden="true">
            {user.username.slice(0, 1)}
          </span>
          <div className="account-identity">
            <p className="account-name">{user.username}</p>
            <p className="account-email">{user.email}</p>
          </div>
        </div>
      </section>

      <section className="card">
        <h2>{t('profile.appearance')}</h2>
        <div className="inline-form">
          <label>
            {t('common.language')}
            <select
              value={locale}
              onChange={(event) => {
                setLocale(event.target.value as Locale)
              }}
            >
              {locales.map((value) => (
                <option key={value} value={value}>
                  {LOCALE_LABELS[value]}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t('common.theme')}
            <select
              value={theme}
              onChange={(event) => {
                setTheme(event.target.value as ThemePreference)
              }}
            >
              {THEME_PREFERENCES.map((value) => (
                <option key={value} value={value}>
                  {t(`theme.${value}`)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="card">
        <h2>{t('security.title')}</h2>
        <div className="link-list">
          <Link to="/change-password">{t('changePassword.title')}</Link>
          <Link to="/security">{t('profile.securitySettings')}</Link>
        </div>
      </section>

      {adminLinks.length > 0 && (
        <section className="card">
          <h2>{t('profile.admin')}</h2>
          <div className="link-list">
            {adminLinks.map((link) => (
              <Link key={link.to} to={link.to}>
                {t(link.labelKey)}
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
