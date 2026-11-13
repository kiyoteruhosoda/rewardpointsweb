/**
 * The family the signed-in account belongs to.
 *
 * An account belongs to at most one family (ADR-0013), so one state is enough. It is
 * collected here because the navigation (list of children), dashboard and family settings
 * show the same content. Fetching per screen would leave only the left navigation stale
 * right after adding a child.
 *
 * Fetch only for people with `family:view`. Calling without it turns a 403 into
 * "no family", making the guidance text a lie.
 *
 * **Do not call a failed load "not a member".** If `family` became null when the list
 * loaded but the details failed (5xx, offline), the screen would decide "no family"
 * and show create/join, and tapping them always ends in `already_belongs_to_family`.
 * Load failure is reported separately as `failed`.
 *
 * Balances live here too. **Call `reload` after changing points** (ADR-0021).
 * Otherwise only the screen that recorded shows the new balance, while the dashboard,
 * navigation and family settings keep showing the old number.
 *
 * Do not fetch only once. Reload on every screen change and every return to the app. Fetching
 * once per login means points added on another device or tab do not show until a browser
 * reload. Reloading keeps the display, so the screen does not flicker.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useLocation } from 'react-router-dom'

import { useRefreshOnReturn } from '../hooks/useRefreshOnReturn'
import { families, type FamilyDetail } from '../services/families'
import { useAuth } from './AuthContext'

export interface FamilyValue {
  /** The family the account belongs to. null if none. */
  family: FamilyDetail | null
  /**
   * Failed to load and there is nothing to show. Membership is unknown
   * (not "not a member"). If a reload after a successful load fails, the previous
   * content stays shown, so this stays false (ADR-0021).
   */
  failed: boolean
  /** True until the first fetch finishes. Used to distinguish from "no family". */
  loading: boolean
  reload: () => Promise<void>
}

/** Family and failure are always swapped as one pair to avoid mixing them up. */
interface Loaded {
  family: FamilyDetail | null
  failed: boolean
}

const NONE: Loaded = { family: null, failed: false }

/** Exported so tests can render with replaced state (production builds it in FamilyProvider). */
export const FamilyContext = createContext<FamilyValue | null>(null)

export function FamilyProvider({ children }: { children: ReactNode }) {
  const { hasScope } = useAuth()
  const canView = hasScope('family:view')
  const { pathname } = useLocation()
  const [loaded, setLoaded] = useState<Loaded>(NONE)
  const [loading, setLoading] = useState(true)
  /** Sequence number of the fetch. Kept to discard overtaken (stale) responses. */
  const latest = useRef(0)

  const reload = useCallback(async () => {
    // Reloads can overlap (e.g. moving screens right after recording). Even if an earlier fetch
    // arrives later, do not overwrite the newer result with stale content.
    const ticket = ++latest.current
    const isLatest = () => ticket === latest.current

    if (!canView) {
      setLoaded(NONE)
      setLoading(false)
      return
    }
    try {
      const list = await families.list()
      const first = list[0]
      const family = first ? await families.view(first.id) : null
      if (isLatest()) setLoaded({ family, failed: false })
    } catch {
      if (!isLatest()) return
      // Even if a reload fails, keep the family already loaded (ADR-0021). If balances and child
      // entries vanished on a brief outage right after returning, it would look like being
      // removed from the family. Report "could not load" only when there is nothing to show.
      setLoaded((current) => (current.family ? current : { family: null, failed: true }))
    } finally {
      // An overtaken fetch does not announce its end either. Ending loading after discarding the
      // result would show the still-empty state as "no family / no children" on screen.
      if (isLatest()) setLoading(false)
    }
  }, [canView])

  // Reload on the first load and **on every screen change**. Fetching once per login means
  // points added on another device or tab do not show until a browser reload
  // (to the user, "the dashboard keeps an old value"). The display is kept, so a reload
  // does not flicker the screen; values simply swap in when they arrive.
  useEffect(() => {
    void reload()
  }, [reload, pathname])

  // Records from another device (the other parent, the child) do not reach this screen.
  // Reload on return so an open balance does not linger.
  useRefreshOnReturn(reload)

  return (
    <FamilyContext.Provider value={{ ...loaded, loading, reload }}>
      {children}
    </FamilyContext.Provider>
  )
}

export function useFamily(): FamilyValue {
  const value = useContext(FamilyContext)
  if (!value) throw new Error('useFamily must be used within a FamilyProvider')
  return value
}
