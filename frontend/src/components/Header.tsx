/**
 * 画面上端の枠。アプリ名と、ログイン中のアカウントに関わる操作だけを置く。
 *
 * 言語・テーマの切り替えはここではなくプロフィール設定（ProfilePage）に置いている。
 * 狭い画面ではこの行に収まらず、選択肢の文字数で幅が決まる `<select>` が 2 つ並ぶと
 * タイトルまで押し出されるため。
 *
 * アカウントへの入口は、狭い画面では頭文字の丸だけにする（表示は index.css）。
 * 利用者名は長さがまちまちで、長い名前ほど右側を占めてタイトルを押し出すため。
 * 読み上げ・マウスカーソルには利用者名が残る（`aria-label` / `title`）。
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
 * 丸に出す頭文字。
 *
 * 絵文字や結合文字で始まる名前を途中で切らないよう、コードポイントで取り出す
 * （`username[0]` は壊れた文字になりうる）。
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
