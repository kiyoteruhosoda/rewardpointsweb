/**
 * Display device (signage) screen (ADR-0047).
 *
 * Does not go through the login screen. Without device credentials it shows pairing (a large
 * confirmation code and QR, then receives credentials once approved); with them it keeps showing
 * the family's children's balances and recent records full screen. No menu/logout/action buttons.
 *
 * - Exchanging the credential for an access token lives in `api.ts` (same entry as the 401 retry)
 * - When unreachable, keeps the last display and shows "Reconnecting…" (ADR-0046).
 *   Credentials are cleared only when the server answers "removed / revoked"
 * - Viewers cannot tap an update, so a new version reloads once active (exception to ADR-0045)
 * - Keeps the screen on (Screen Wake Lock) and requests persistent storage (so the key stays)
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { useVersionLabel } from '../hooks/useVersionLabel'
import { useI18n } from '../i18n'
import {
  ApiError,
  clearOfflineViewCache,
  clearTokens,
  displayCredential,
  openDisplaySession,
  rememberDisplayCredential,
} from '../services/api'
import { DISPLAY_UPDATE_CHECK_INTERVAL_MS, watchForUpdate } from '../services/appUpdate'
import { claimPairing, startPairing, type StartedPairing } from '../services/display'
import { families, parseUtc, type FamilyDetail, type Transaction } from '../services/families'

/** Interval for reloading the board. Records added on a parent's phone appear within 1 minute. */
export const BOARD_REFRESH_MS = 60 * 1000
/** Interval for retrying when unreachable or unable to start. */
export const RETRY_MS = 5 * 1000
/** Number of recent records shown per child. */
const RECENT_RECORDS = 3

interface ChildBoard {
  id: number
  name: string
  balance: number
  recent: Transaction[]
}

interface Board {
  familyName: string
  children: ChildBoard[]
  updatedAt: Date
}

/** Hide reversals and reversed rows. List only the records currently in effect. */
function effective(transactions: Transaction[]): Transaction[] {
  return transactions.filter((row) => !row.is_reversed && row.reversal_of_id === null)
}

async function loadBoard(): Promise<Board | null> {
  const [summary] = await families.list()
  if (!summary) return null
  const family: FamilyDetail = await families.view(summary.id)
  const children = await Promise.all(
    family.memberships
      .filter((member) => member.ledger_id !== null)
      .map(async (member) => {
        const ledger = await families.viewLedger(family.id, member.ledger_id ?? 0)
        return {
          id: member.id,
          name: member.display_name,
          balance: ledger.data.balance,
          recent: effective(ledger.data.transactions).slice(0, RECENT_RECORDS),
        }
      }),
  )
  return { familyName: family.name, children, updatedAt: new Date() }
}

/** Keep the screen on. Re-acquire each time the tab returns to the front (lost in background). */
function useScreenKeptOn(): void {
  useEffect(() => {
    if (!('wakeLock' in navigator)) return
    const request = () => {
      if (document.visibilityState !== 'visible') return
      navigator.wakeLock.request('screen').catch(() => {
        // Keep displaying if refused (users disable auto-lock in settings; the screen warns)
      })
    }
    request()
    document.addEventListener('visibilitychange', request)
    return () => {
      document.removeEventListener('visibilitychange', request)
    }
  }, [])
}

/** Request persistent storage so the key (device credential) is not lost to browser cleanup. */
function usePersistentStorage(): void {
  useEffect(() => {
    if (!('storage' in navigator)) return
    void navigator.storage.persist().then((granted) => {
      console.info('[display] storage.persist', granted)
    })
  }, [])
}

/**
 * When a new version becomes active, reload without waiting for a tap.
 * Nobody touches this screen, so check at a short interval (task #498).
 */
function useImmediateUpdates(): void {
  useEffect(() => {
    watchForUpdate(
      (apply) => {
        apply()
      },
      { checkIntervalMs: DISPLAY_UPDATE_CHECK_INTERVAL_MS },
    )
  }, [])
}

export function DisplayPage() {
  const [paired, setPaired] = useState(() => displayCredential() !== null)
  useScreenKeptOn()
  usePersistentStorage()
  useImmediateUpdates()
  const version = useVersionLabel()

  const onPaired = useCallback(() => {
    setPaired(true)
  }, [])
  const onRemoved = useCallback(() => {
    setPaired(false)
  }, [])

  return (
    <div className="display-screen">
      {paired ? <DisplayBoard onRemoved={onRemoved} /> : <Pairing onPaired={onPaired} />}
      {/* Make a version change visible on screen (task #498) */}
      <p className="display-version" data-testid="display-version">
        {version}
      </p>
    </div>
  )
}

function Pairing({ onPaired }: { onPaired: () => void }) {
  const { t } = useI18n()
  const [pairing, setPairing] = useState<StartedPairing | null>(null)
  const [unreachable, setUnreachable] = useState(false)

  // Run start -> wait for approval -> start over on expiry as one flow
  useEffect(() => {
    let stopped = false
    let timer = 0
    const later = (step: () => Promise<void>, ms: number) => {
      if (!stopped) timer = window.setTimeout(() => void step(), ms)
    }

    const start = async (): Promise<void> => {
      try {
        const started = await startPairing(window.location.origin)
        if (stopped) return
        setPairing(started)
        setUnreachable(false)
        later(() => poll(started), started.interval * 1000)
      } catch {
        setUnreachable(true)
        later(start, RETRY_MS)
      }
    }

    const poll = async (started: StartedPairing): Promise<void> => {
      try {
        const outcome = await claimPairing(started.device_code)
        setUnreachable(false)
        if (outcome.kind === 'claimed') {
          // Do not carry over traces of a person who used this device (tokens, offline view)
          clearTokens()
          await clearOfflineViewCache()
          rememberDisplayCredential(outcome.credential)
          if (!stopped) onPaired()
          return
        }
        if (outcome.kind === 'expired') {
          await start()
          return
        }
      } catch {
        setUnreachable(true)
      }
      later(() => poll(started), started.interval * 1000)
    }

    void start()
    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [onPaired])

  return (
    <section className="display-pairing" aria-live="polite">
      <h1>{t('display.pairingTitle')}</h1>
      <p>{t('display.pairingLead')}</p>
      {pairing && (
        <>
          <p className="display-pairing-code" data-testid="pairing-code">
            {pairing.user_code}
          </p>
          {pairing.qr_code && (
            <img className="display-pairing-qr" src={pairing.qr_code} alt={t('display.qrAlt')} />
          )}
          <p className="display-note">
            {t('display.codeExpires', { minutes: Math.round(pairing.expires_in / 60) })}
          </p>
        </>
      )}
      {unreachable && <Reconnecting />}
    </section>
  )
}

function Reconnecting() {
  const { t } = useI18n()
  return (
    <p className="display-reconnecting" role="status">
      <span className="spinner" aria-hidden="true" /> {t('display.reconnecting')}
    </p>
  )
}

function DisplayBoard({ onRemoved }: { onRemoved: () => void }) {
  const { t, locale } = useI18n()
  const [board, setBoard] = useState<Board | null>(null)
  const [empty, setEmpty] = useState(false)
  const [unreachable, setUnreachable] = useState(false)
  const loading = useRef(false)
  // On the first load after startup, re-fetch from the credential instead of local tokens
  // (even if a person's token remains on this device, do not show that person's family)
  const opened = useRef(false)

  const refresh = useCallback(async () => {
    if (loading.current) return
    loading.current = true
    try {
      if (!opened.current) {
        const outcome = await openDisplaySession()
        if (outcome === 'removed') {
          onRemoved()
          return
        }
        if (outcome === 'unreachable') {
          setUnreachable(true)
          return
        }
        opened.current = true
      }
      const loaded = await loadBoard()
      setBoard(loaded)
      setEmpty(loaded === null)
      setUnreachable(false)
    } catch (error) {
      // If re-fetching revealed "removed", the credential is already cleared (api.ts)
      if (displayCredential() === null) {
        onRemoved()
        return
      }
      setUnreachable(!(error instanceof ApiError) || error.status >= 500 || error.status === 401)
    } finally {
      loading.current = false
    }
  }, [onRemoved])

  useEffect(() => {
    void refresh()
    const interval = window.setInterval(
      () => void refresh(),
      unreachable ? RETRY_MS : BOARD_REFRESH_MS,
    )
    const onVisible = () => {
      if (document.visibilityState === 'visible') void refresh()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [refresh, unreachable])

  if (!board) {
    return (
      <section className="display-board">
        {empty ? (
          <p className="display-note">{t('display.noFamily')}</p>
        ) : (
          unreachable && <Reconnecting />
        )}
      </section>
    )
  }

  return (
    <section className="display-board">
      <header className="display-board-header">
        <h1>{board.familyName}</h1>
        <span className="display-note">
          {t('display.updatedAt', {
            time: board.updatedAt.toLocaleTimeString(locale, {
              hour: '2-digit',
              minute: '2-digit',
            }),
          })}
        </span>
      </header>
      <ul className="display-children">
        {board.children.map((child) => (
          <li key={child.id} className="display-child">
            <p className="display-child-name">{child.name}</p>
            <p className="display-child-balance">{t('points.value', { points: child.balance })}</p>
            <RecentRecords records={child.recent} />
          </li>
        ))}
      </ul>
      {unreachable && <Reconnecting />}
      <p className="display-note display-screen-hint">{t('display.screenStaysOn')}</p>
    </section>
  )
}

function RecentRecords({ records }: { records: Transaction[] }) {
  const { t, locale } = useI18n()
  if (records.length === 0) return <p className="display-note">{t('display.noRecords')}</p>
  return (
    <ul className="display-records">
      {records.map((record) => (
        <li key={record.id}>
          <span className="display-record-date">
            {parseUtc(record.occurred_at).toLocaleDateString(locale, {
              month: 'numeric',
              day: 'numeric',
            })}
          </span>
          <span className="display-record-reason">{record.reason}</span>
          <span
            className={
              record.amount < 0 ? 'display-record-amount negative' : 'display-record-amount'
            }
          >
            {record.amount > 0 ? `+${record.amount}` : record.amount}
          </span>
        </li>
      ))}
    </ul>
  )
}
