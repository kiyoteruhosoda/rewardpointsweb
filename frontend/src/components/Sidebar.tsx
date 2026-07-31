/**
 * ナビゲーション。表示はロール名ではなく scope で制御する。
 *
 * 並べるのは家族が日常で使う画面だけ。管理者は親（家族）なので、システム管理
 * （ユーザー・ロール・権限・システム設定・ログ）はここに出さず、プロフィール設定
 * （ProfilePage）の中から入る。
 *
 * 広い画面では本文の左に置いたままにし、狭い画面では画面外から滑り出す引き出しに
 * なる（切り替えは index.css のメディアクエリ。DOM は 1 つで、開いているかどうかだけを
 * `open` で受け取る）。閉じ方は「項目を選ぶ」「背景に触れる」「Escape」の 3 つ。
 *
 * 開いているあいだはキーボードの焦点を引き出しの中に閉じ込める。引き出しは背景を
 * 覆って本文を操作できなくするので、Tab で背後の（見えない）操作子へ入れてしまうと
 * キーボードや支援技術の利用者だけが迷子になる。
 */
import { useEffect, useRef } from 'react'
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
  { to: '/profile', labelKey: 'nav.profile', scopes: [] },
]

/** 引き出しの id。ヘッダーの開閉ボタンが `aria-controls` で指す。 */
export const NAV_ID = 'primary-nav'

/** index.css のメディアクエリと同じ境目。ここを跨いだら引き出しではなくなる。 */
const NARROW = '(max-width: 48rem)'

interface Props {
  open: boolean
  onClose: () => void
}

/**
 * 引き出しを開けているあいだ、焦点を巡回させる要素。
 *
 * 順は「項目 → 背景の『閉じる』ボタン」。背景は DOM 上は項目より前にあるが、
 * 開いた直後の焦点が「閉じる」になるのは行き先を探している人には遠回りなので、
 * 巡回の最後に置く。
 */
function focusables(nav: HTMLElement | null): HTMLElement[] {
  if (!nav) return []
  const links = Array.from(nav.querySelectorAll<HTMLElement>('a[href]'))
  const backdrop = nav.parentElement?.querySelector<HTMLElement>('.nav-backdrop')
  return backdrop ? [...links, backdrop] : links
}

export function Sidebar({ open, onClose }: Props) {
  const { t } = useI18n()
  const { hasScope } = useAuth()
  const navRef = useRef<HTMLElement>(null)

  // Escape で閉じ、Tab は引き出しの中で巡回させる。開いたときは先頭へ焦点を移し、
  // 閉じたら開いた操作子（ヘッダーの ☰）へ戻す。
  useEffect(() => {
    if (!open) return
    const opener = document.activeElement
    focusables(navRef.current)[0]?.focus()

    const handle = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
        return
      }
      if (event.key !== 'Tab') return
      const items = focusables(navRef.current)
      const first = items[0]
      const last = items[items.length - 1]
      if (!first || !last) return
      const active = document.activeElement
      const inside = items.some((item) => item === active)
      if (active === (event.shiftKey ? first : last) || !inside) {
        event.preventDefault()
        ;(event.shiftKey ? last : first).focus()
      }
    }

    window.addEventListener('keydown', handle)
    return () => {
      window.removeEventListener('keydown', handle)
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus()
    }
  }, [open, onClose])

  // 画面が広くなったら引き出しではなくなる。開いたままだと閉じ込めだけが残るので閉じる。
  useEffect(() => {
    if (!open) return
    const query = window.matchMedia(NARROW)
    const handle = () => {
      if (!query.matches) onClose()
    }
    query.addEventListener('change', handle)
    return () => {
      query.removeEventListener('change', handle)
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
        ref={navRef}
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
