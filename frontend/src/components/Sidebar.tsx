/**
 * ナビゲーション。表示はロール名ではなく scope で制御する。
 *
 * 広い画面では本文の左に置いたままにし、狭い画面では画面外から滑り出す引き出しに
 * なる（切り替えは index.css のメディアクエリ。DOM は 1 つで、開いているかどうかだけを
 * `open` で受け取る）。閉じ方は「項目を選ぶ」「背景に触れる」「Escape」の 3 つ。
 */
import { useEffect } from 'react'
import { NavLink } from 'react-router-dom'

import { useI18n } from '../i18n'
import { useAuth } from '../store/AuthContext'

interface Item {
  to: string
  labelKey: string
  scopes: string[]
}

const ITEMS: Item[] = [
  { to: '/', labelKey: 'nav.dashboard', scopes: ['dashboard:view'] },
  { to: '/members', labelKey: 'nav.members', scopes: ['member:view'] },
  { to: '/items', labelKey: 'nav.items', scopes: ['item:view'] },
  { to: '/admin/users', labelKey: 'nav.users', scopes: ['user:manage'] },
  { to: '/admin/roles', labelKey: 'nav.roles', scopes: ['role:manage'] },
  { to: '/admin/permissions', labelKey: 'nav.permissions', scopes: ['permission:manage'] },
  { to: '/admin/config', labelKey: 'nav.config', scopes: ['admin:system-settings'] },
  { to: '/admin/logs', labelKey: 'nav.logs', scopes: ['log:view'] },
]

/** 引き出しの id。ヘッダーの開閉ボタンが `aria-controls` で指す。 */
export const NAV_ID = 'primary-nav'

interface Props {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: Props) {
  const { t } = useI18n()
  const { hasScope } = useAuth()

  useEffect(() => {
    if (!open) return
    const handle = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handle)
    return () => {
      window.removeEventListener('keydown', handle)
    }
  }, [open, onClose])

  return (
    <>
      {open && (
        <button
          type="button"
          className="nav-backdrop"
          aria-label={t('nav.closeMenu')}
          onClick={onClose}
        />
      )}
      <nav
        id={NAV_ID}
        className={open ? 'sidebar sidebar-open' : 'sidebar'}
        aria-label={t('nav.primary')}
      >
        {ITEMS.filter((item) => hasScope(...item.scopes)).map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === '/'} onClick={onClose}>
            {t(item.labelKey)}
          </NavLink>
        ))}
      </nav>
    </>
  )
}
