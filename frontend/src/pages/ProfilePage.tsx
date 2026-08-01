/**
 * プロフィール設定。自分のアカウント・表示設定（言語・テーマ）・セキュリティを
 * 集める。システム管理への入口は Sidebar の独立した節にある。
 *
 * 言語とテーマの保存先は localStorage で、サーバーへは送らない
 * （i18n/index.tsx・theme/index.tsx）。
 */
import { Link } from 'react-router-dom'

import { ProfileForm } from '../components/ProfileForm'
import { LOCALE_LABELS, useI18n, type Locale } from '../i18n'
import { useAuth } from '../store/AuthContext'
import { THEME_PREFERENCES, useTheme, type ThemePreference } from '../theme'

export function ProfilePage() {
  const { t, locale, locales, setLocale } = useI18n()
  const { theme, setTheme } = useTheme()
  const { user } = useAuth()
  if (!user) return null

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{t('profile.title')}</h1>
      </div>

      <section className="card">
        <h2>{t('profile.account')}</h2>
        <div className="account-row">
          <span className="avatar" aria-hidden="true">
            {user.display_name.slice(0, 1)}
          </span>
          <div className="account-identity">
            <p className="account-name">{user.display_name}</p>
            <p className="account-email">{t('profile.signInAs', { username: user.username })}</p>
          </div>
        </div>
        <ProfileForm />
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
    </div>
  )
}
