/**
 * 表示端末（サイネージ）の画面（ADR-0047）。
 *
 * ログインの画面を通らない。端末の資格情報が無ければペアリング（確認コードと QR を
 * 大きく出し、承認されたら受け取る）、あれば家族の子どもの残高と最近の記録を全画面で
 * 出し続ける。メニュー・ログアウト・操作のボタンは出さない。
 *
 * - 資格情報からアクセストークンへの取り直しは `api.ts`（401 の取り直しと同じ入口）
 * - 届かないときは最後の表示を残して「つなぎ直しています」を出す（ADR-0046）。
 *   資格情報を消すのは、サーバーが「外された・失効した」と答えたときだけ
 * - 新しい版は見る人が押せないので、有効になったらすぐ再読み込みする（ADR-0045 の例外）
 * - 画面の消灯を止め（Screen Wake Lock）、保存領域の永続化を頼む（合鍵が消えないように）
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { useI18n } from '../i18n'
import {
  ApiError,
  clearOfflineViewCache,
  clearTokens,
  displayCredential,
  openDisplaySession,
  rememberDisplayCredential,
} from '../services/api'
import { watchForUpdate } from '../services/appUpdate'
import { claimPairing, startPairing, type StartedPairing } from '../services/display'
import { families, parseUtc, type FamilyDetail, type Transaction } from '../services/families'

/** 表示を読み直す間隔。親のスマホで足した記録が 1 分以内に映る。 */
export const BOARD_REFRESH_MS = 60 * 1000
/** 届かないとき・始められないときに聞き直す間隔。 */
export const RETRY_MS = 5 * 1000
/** 子ごとに出す最近の記録の数。 */
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

/** 打ち消し・打ち消された行は出さない。いま効いている記録だけを並べる。 */
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

/** 画面を消さない。タブが手前へ戻るたびに取り直す（裏へ回ると外れるため）。 */
function useScreenKeptOn(): void {
  useEffect(() => {
    if (!('wakeLock' in navigator)) return
    const request = () => {
      if (document.visibilityState !== 'visible') return
      navigator.wakeLock.request('screen').catch(() => {
        // 断られても表示は続ける（設定で自動ロックを切ってもらう。画面に注意を出してある）
      })
    }
    request()
    document.addEventListener('visibilitychange', request)
    return () => {
      document.removeEventListener('visibilitychange', request)
    }
  }, [])
}

/** 保存領域の永続化を頼む。合鍵（端末の資格情報）がブラウザの片付けで消えないように。 */
function usePersistentStorage(): void {
  useEffect(() => {
    if (!('storage' in navigator)) return
    void navigator.storage.persist().then((granted) => {
      console.info('[display] storage.persist', granted)
    })
  }, [])
}

/** 新しい版が有効になったら、押されるのを待たずに再読み込みする。 */
function useImmediateUpdates(): void {
  useEffect(() => {
    watchForUpdate((apply) => {
      apply()
    })
  }, [])
}

export function DisplayPage() {
  const [paired, setPaired] = useState(() => displayCredential() !== null)
  useScreenKeptOn()
  usePersistentStorage()
  useImmediateUpdates()

  const onPaired = useCallback(() => {
    setPaired(true)
  }, [])
  const onRemoved = useCallback(() => {
    setPaired(false)
  }, [])

  return (
    <div className="display-screen">
      {paired ? <DisplayBoard onRemoved={onRemoved} /> : <Pairing onPaired={onPaired} />}
    </div>
  )
}

function Pairing({ onPaired }: { onPaired: () => void }) {
  const { t } = useI18n()
  const [pairing, setPairing] = useState<StartedPairing | null>(null)
  const [unreachable, setUnreachable] = useState(false)

  // 始める → 承認を待つ → 期限が切れたら始め直す、を 1 本の流れで回す
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
          // 同じ端末で人が入っていた跡（トークン・オフライン閲覧）を持ち越さない
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
  // 起動して最初の 1 回は、手元のトークンに頼らず資格情報から取り直す
  // （同じ端末に人のトークンが残っていても、その人の家族を映さない）
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
      // 取り直しで「外された」と分かったら資格情報は消えている（api.ts）
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
