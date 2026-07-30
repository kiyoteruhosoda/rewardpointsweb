/**
 * 自分の情報と、自分の端末に閉じた表示設定（言語・テーマ）。
 *
 * 言語とテーマはヘッダーではなくここに置く。選択肢の文字数で幅が決まる `<select>` が
 * 2 つあると、狭い画面ではヘッダーが 3 行になってしまうため。どちらも保存先は
 * localStorage で、サーバーへは送らない（i18n/index.tsx・theme/index.tsx）。
 */
import { Link } from 'react-router-dom'

import { LOCALE_LABELS, useI18n, type Locale } from '../i18n'
import { useAuth } from '../store/AuthContext'
import { THEME_PREFERENCES, useTheme, type ThemePreference } from '../theme'

export function ProfilePage() {
  const { t, locale, locales, setLocale } = useI18n()
  const { theme, setTheme } = useTheme()
  const { user } = useAuth()
  if (!user) return null

  return (
    <div className="card">
      <h1>{t('profile.title')}</h1>
      <dl>
        <dt>{t('common.email')}</dt>
        <dd>{user.email}</dd>
        <dt>{t('common.username')}</dt>
        <dd>{user.username}</dd>
        <dt>{t('profile.scopes')}</dt>
        <dd>
          <ul className="scope-list">
            {user.scopes.map((scope) => (
              <li key={scope}>
                <code>{scope}</code>
              </li>
            ))}
          </ul>
        </dd>
      </dl>

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

      <div className="inline-form">
        <Link to="/change-password">{t('changePassword.title')}</Link>
        <Link to="/security">{t('security.title')}</Link>
      </div>
    </div>
  )
}
