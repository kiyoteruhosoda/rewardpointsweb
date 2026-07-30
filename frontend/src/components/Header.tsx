/**
 * 画面上端の枠。アプリ名と、ログイン中のアカウントに関わる操作だけを置く。
 *
 * 言語・テーマの切り替えはここではなく Sidebar の下に置いている。狭い画面では
 * この行に収まらず、選択肢の文字数で幅が決まる `<select>` が 2 つ並ぶとタイトルまで
 * 押し出されるため（Sidebar は広い画面では出たままなので、どちらの幅でも届く）。
 */
import { Link } from 'react-router-dom'

import { useI18n } from '../i18n'
import { useAuth } from '../store/AuthContext'
import { NAV_ID } from './Sidebar'

interface Props {
  navOpen: boolean
  onToggleNav: () => void
}

export function Header({ navOpen, onToggleNav }: Props) {
  const { t } = useI18n()
  const { user, logout } = useAuth()

  return (
    <header className="header">
      {/* 引き出しの開閉。狭い画面でだけ出す（表示の判定は index.css）。 */}
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
            <Link to="/profile">{user.username}</Link>
            <button onClick={logout}>{t('nav.logout')}</button>
          </>
        )}
      </div>
    </header>
  )
}
