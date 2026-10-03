/**
 * 1 人の子のイベント（がんばりカード）を 1 画面に並べる（ADR-0042）。
 *
 * カードは格子に並べ、挑戦中を先に、達成したものをその後ろに置く。「達成」を押すと
 * その場でシールが貼られ（返事を待たずに見せる）、返事が来たらサーバーの姿で
 * 置き換える。失敗したら読み直して、貼ったように見えたシールを戻す。
 *
 * 最後の 1 枚で台帳にポイントが入るので、達成したら家族（ナビゲーションと
 * ダッシュボードの残高の出所。ADR-0021）も読み直す。
 */
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { RewardEventCard, type RewardEventAction } from '../components/RewardEventCard'
import { RewardEventForm } from '../components/RewardEventForm'
import { useToast } from '../components/ToastNotification'
import { usePendingRows } from '../hooks/usePendingRows'
import { useRefreshOnReturn } from '../hooks/useRefreshOnReturn'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import {
  rewardEvents,
  type NewRewardEvent,
  type RewardEvent,
  type RewardEventBoard,
} from '../services/rewardEvents'
import { useFamily } from '../store/FamilyContext'

/** 直前に貼った 1 枚。その 1 枚にだけ「貼る」動きを付ける。 */
interface FreshSticker {
  eventId: number
  number: number
}

function byCompletion(a: RewardEvent, b: RewardEvent): number {
  return (b.completed_at ?? '').localeCompare(a.completed_at ?? '')
}

export function RewardEventsPage() {
  const { familyId, ledgerId } = useParams<{ familyId: string; ledgerId: string }>()
  const { t } = useI18n()
  const { notify } = useToast()
  const { reload: reloadFamily } = useFamily()
  const [board, setBoard] = useState<RewardEventBoard | null>(null)
  const [failed, setFailed] = useState(false)
  const [fresh, setFresh] = useState<FreshSticker | null>(null)
  const [justCompleted, setJustCompleted] = useState<ReadonlySet<number>>(new Set())
  const { pendingActionOf, runForRow } = usePendingRows<RewardEventAction>()

  const family = Number(familyId)
  const ledger = Number(ledgerId)

  const reload = useCallback(
    () =>
      rewardEvents
        .board(family, ledger)
        .then((result) => {
          setBoard(result)
          setFailed(false)
        })
        .catch((error: unknown) => {
          setFailed(true)
          notify('error', t(errorMessageKey(error)))
        }),
    [family, ledger, notify, t],
  )

  useEffect(() => {
    setBoard(null)
    void reload()
  }, [reload])

  // 別の端末で貼られたシールはこの画面には届かない
  useRefreshOnReturn(reload)

  const replace = (updated: RewardEvent) => {
    setBoard((current) =>
      current === null
        ? current
        : {
            ...current,
            events: current.events.map((event) => (event.id === updated.id ? updated : event)),
          },
    )
  }

  /** 失敗を伝えて読み直す（貼ったように見せたシールを戻す）。 */
  const recover = async (error: unknown) => {
    notify('error', t(errorMessageKey(error)))
    await reload()
  }

  const stick = (event: RewardEvent) => {
    const number = event.stickers.length + 1
    void runForRow(event.id, 'stick', async () => {
      // 返事を待たずに貼って見せる。押した手応えが遅れると、もう一度押される。
      // 見せるのは runForRow の中（同じカードへの 2 度目の押下はここまで来ない）
      replace({
        ...event,
        stickers: [...event.stickers, { number, stuck_at: new Date().toISOString() }],
      })
      setFresh({ eventId: event.id, number })
      try {
        const updated = await rewardEvents.stick(family, ledger, event.id, number)
        replace(updated)
        if (updated.completed_at !== null && event.completed_at === null) {
          setJustCompleted((done) => new Set(done).add(updated.id))
          notify('success', t('events.completed', { points: updated.reward_points }))
          await reloadFamily()
        }
      } catch (error) {
        await recover(error)
      }
    })
  }

  const peel = (event: RewardEvent) => {
    const number = event.stickers.length
    void runForRow(event.id, 'peel', async () => {
      try {
        replace(await rewardEvents.peel(family, ledger, event.id, number))
      } catch (error) {
        await recover(error)
      }
    })
  }

  const remove = (event: RewardEvent) => {
    if (!window.confirm(t('events.confirmRemove', { title: event.title }))) return
    void runForRow(event.id, 'remove', async () => {
      try {
        await rewardEvents.remove(family, ledger, event.id)
        notify('success', t('events.removed'))
        await reload()
      } catch (error) {
        await recover(error)
      }
    })
  }

  /** 作れなかったときは投げ直す（入力欄が内容を残す）。 */
  const create = async (event: NewRewardEvent) => {
    try {
      await rewardEvents.create(family, ledger, event)
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
      throw error
    }
    notify('success', t('events.created'))
    await reload()
  }

  if (board === null) {
    return failed ? (
      <p className="error">{t('events.unavailable')}</p>
    ) : (
      <p className="loading">{t('common.loading')}</p>
    )
  }

  const inProgress = board.events.filter((event) => event.completed_at === null)
  const completed = board.events.filter((event) => event.completed_at !== null).sort(byCompletion)

  const card = (event: RewardEvent) => (
    <RewardEventCard
      key={event.id}
      event={event}
      canModify={board.can_modify}
      pending={pendingActionOf(event.id)}
      freshNumber={fresh?.eventId === event.id ? fresh.number : null}
      freshlyCompleted={justCompleted.has(event.id)}
      onStick={() => {
        stick(event)
      }}
      onPeel={() => {
        peel(event)
      }}
      onRemove={() => {
        remove(event)
      }}
    />
  )

  return (
    <div className="page page-wide">
      <div className="page-heading page-heading-row">
        <h1>{t('events.title', { name: board.display_name })}</h1>
        <Link className="page-heading-link" to={`/families/${family}/ledgers/${ledger}`}>
          {t('events.backToLedger')}
        </Link>
      </div>

      {board.can_modify && (
        // まだ 1 枚も無ければ開いておく（最初にすることは作ること）
        <details className="card event-create" open={board.events.length === 0}>
          <summary>{t('events.createTitle')}</summary>
          <p className="event-create-hint">{t('events.createHint')}</p>
          <RewardEventForm onCreate={create} />
        </details>
      )}

      {board.events.length === 0 ? (
        <p className="event-empty">
          {board.can_modify ? t('events.empty') : t('events.emptyChild')}
        </p>
      ) : (
        <>
          {!board.can_modify && <p className="event-note">{t('events.readOnly')}</p>}
          {inProgress.length > 0 && (
            <section aria-label={t('events.inProgressSection')} className="event-board">
              {inProgress.map(card)}
            </section>
          )}
          {completed.length > 0 && (
            <section className="event-section">
              <h2 className="event-section-title">{t('events.completedSection')}</h2>
              <div className="event-board">{completed.map(card)}</div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
