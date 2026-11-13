/**
 * Navigation. Visibility is controlled by scope, not role name.
 *
 * The upper part holds screens the family uses daily. Right under the dashboard, children with a ledger
 * are listed in the family's chosen order (changeable in family settings) — this is the entry opened
 * every day, so it does not go through family details. System administration (users, roles, permissions,
 * system settings, logs) appears as a separate lower section, shown only to people with the scope (admin).
 *
 * On wide screens it stays to the left of the content; on narrow screens it becomes a drawer sliding in
 * from off-screen (switched by a media query in index.css; there is one DOM, and only whether it is open
 * is received as `open`). It closes in three ways: "choose an item", "touch the backdrop", "Escape".
 *
 * While open, keyboard focus is trapped inside the drawer. The drawer covers the backdrop and blocks
 * the content, so letting Tab go into the (invisible) controls behind it would leave only keyboard and
 * assistive-technology users lost.
 */
import { Fragment, useEffect, useRef } from 'react'
import { NavLink } from 'react-router-dom'

import { useI18n } from '../i18n'
import { useAuth } from '../store/AuthContext'
import { useFamily } from '../store/FamilyContext'

interface Item {
  to: string
  labelKey: string
  scopes: string[]
}

const ITEMS: Item[] = [
  { to: '/', labelKey: 'nav.dashboard', scopes: ['dashboard:view'] },
  { to: '/families', labelKey: 'nav.familySettings', scopes: ['family:view'] },
  { to: '/profile', labelKey: 'nav.profile', scopes: [] },
]

/** Where child entries are inserted. Right after the dashboard (after this item). */
const CHILDREN_AFTER = '/'

/** System administration entries. Shown as a separate section only to people with the scope. */
const ADMIN_ITEMS: Item[] = [
  { to: '/admin/users', labelKey: 'nav.users', scopes: ['user:manage'] },
  { to: '/admin/roles', labelKey: 'nav.roles', scopes: ['role:manage'] },
  { to: '/admin/permissions', labelKey: 'nav.permissions', scopes: ['permission:manage'] },
  { to: '/admin/config', labelKey: 'nav.config', scopes: ['admin:system-settings'] },
  { to: '/admin/logs', labelKey: 'nav.logs', scopes: ['log:view'] },
  // Display-device approval/list is for operators only (not shown to admin; ADR-0047)
  { to: '/admin/displays', labelKey: 'nav.displays', scopes: ['display:approve'] },
]

/** The drawer's id. The header toggle button points to it with `aria-controls`. */
export const NAV_ID = 'primary-nav'

/** Same breakpoint as the index.css media query. Crossing it means it is no longer a drawer. */
const NARROW = '(max-width: 48rem)'

interface Props {
  open: boolean
  onClose: () => void
}

/**
 * Elements focus cycles through while the drawer is open.
 *
 * Order is "items -> the backdrop's 'close' button". The backdrop comes before the items in the DOM,
 * but having focus land on "close" right after opening is a detour for people looking for a
 * destination, so it goes last in the cycle.
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
  const { family } = useFamily()
  const navRef = useRef<HTMLElement>(null)
  const adminItems = ADMIN_ITEMS.filter((item) => hasScope(...item.scopes))
  // Participants with a ledger = children. Hidden siblings' ledgers come without ledger_id,
  // so only "entries I can open" are listed here (ADR-0009).
  const children = family?.memberships.filter((member) => member.ledger_id !== null) ?? []

  // Close with Escape, and cycle Tab within the drawer. Move focus to the first item when opened,
  // and back to the control that opened it (the header ☰) when closed.
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

  // When the screen becomes wide it is no longer a drawer. If left open only the trap would remain, so close it.
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
          <Fragment key={item.to}>
            <NavLink to={item.to} end={item.to === '/'} onClick={onClose}>
              {t(item.labelKey)}
            </NavLink>
            {item.to === CHILDREN_AFTER &&
              children.map((child) => (
                <NavLink
                  key={child.id}
                  to={`/families/${family?.id ?? 0}/ledgers/${child.ledger_id ?? 0}`}
                  className="sidebar-child"
                  onClick={onClose}
                >
                  {child.display_name}
                </NavLink>
              ))}
          </Fragment>
        ))}
        {adminItems.length > 0 && (
          <>
            <p className="sidebar-heading">{t('nav.admin')}</p>
            {adminItems.map((item) => (
              <NavLink key={item.to} to={item.to} onClick={onClose}>
                {t(item.labelKey)}
              </NavLink>
            ))}
          </>
        )}
      </nav>
    </>
  )
}
