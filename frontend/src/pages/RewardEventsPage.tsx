/**
 * Shows one child's events (effort cards) on a single screen (ADR-0042).
 *
 * Cards sit in a grid, in-progress first and completed ones after. Tapping "achieved"
 * puts a sticker on the spot (shown without waiting for the reply), then replaced by the
 * server's version once the reply arrives. On failure, reload and remove the sticker shown.
 *
 * The last sticker puts points into the ledger, so after completion also reload the family
 * (the source of balances in the navigation and dashboard; ADR-0021).
 *
 * Cards with a deadline (ADR-0043) come first, nearest deadline first; expired ones go on a shelf
 * between in-progress and completed (extending the deadline returns them to in-progress).
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
import { localDate } from '../services/eventDeadline'
import {
  rewardEvents,
  type NewRewardEvent,
  type RewardEvent,
  type RewardEventBoard,
} from '../services/rewardEvents'
import { useFamily } from '../store/FamilyContext'

/** The sticker just placed. Only that one gets the "stick" animation. */
interface FreshSticker {
  eventId: number
  number: number
}

function byCompletion(a: RewardEvent, b: RewardEvent): number {
  return (b.completed_at ?? '').localeCompare(a.completed_at ?? '')
}

/** Nearest deadline first. Cards without a deadline go last, in creation order. */
function byDeadline(a: RewardEvent, b: RewardEvent): number {
  if (a.deadline !== b.deadline) {
    if (a.deadline === null) return 1
    if (b.deadline === null) return -1
    return a.deadline.localeCompare(b.deadline)
  }
  return a.id - b.id
}

export function RewardEventsPage() {
  const { familyId, ledgerId } = useParams<{ familyId: string; ledgerId: string }>()
  const { t } = useI18n()
  const { notify } = useToast()
  const { reload: reloadFamily } = useFamily()
  const [board, setBoard] = useState<RewardEventBoard | null>(null)
  const [failed, setFailed] = useState(false)
  // "Today" for counting remaining days: the device calendar when loaded, advanced on each reload
  const [today, setToday] = useState('')
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
          setToday(localDate(new Date()))
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

  // Stickers placed on another device do not reach this screen
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

  /** Report the failure and reload (removing the sticker that was shown as stuck). */
  const recover = async (error: unknown) => {
    notify('error', t(errorMessageKey(error)))
    await reload()
  }

  const stick = (event: RewardEvent) => {
    const number = event.stickers.length + 1
    void runForRow(event.id, 'stick', async () => {
      // Show the sticker without waiting for the reply. If the tap feels slow, it gets tapped twice.
      // Shown inside runForRow (a second tap on the same card does not reach here)
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

  /** Change the deadline. Rethrow on failure (keeps the input open). */
  const changeDeadline = (event: RewardEvent, deadline: string | null) =>
    runForRow(event.id, 'deadline', async () => {
      try {
        replace(await rewardEvents.changeDeadline(family, ledger, event.id, deadline))
      } catch (error) {
        await recover(error)
        throw error
      }
    })

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

  /** Rethrow when creation fails (the input keeps its content). */
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

  const open = board.events.filter((event) => event.completed_at === null)
  const inProgress = open.filter((event) => !event.is_expired).sort(byDeadline)
  const expired = open.filter((event) => event.is_expired).sort(byDeadline)
  const completed = board.events.filter((event) => event.completed_at !== null).sort(byCompletion)

  const card = (event: RewardEvent) => (
    <RewardEventCard
      key={event.id}
      event={event}
      canModify={board.can_modify}
      pending={pendingActionOf(event.id)}
      freshNumber={fresh?.eventId === event.id ? fresh.number : null}
      freshlyCompleted={justCompleted.has(event.id)}
      today={today}
      onStick={() => {
        stick(event)
      }}
      onChangeDeadline={(deadline) => changeDeadline(event, deadline)}
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
        // Keep it open when there are none yet (the first thing to do is create one)
        <details className="card event-create" open={board.events.length === 0}>
          <summary>{t('events.createTitle')}</summary>
          <p className="event-create-hint">{t('events.createHint')}</p>
          <RewardEventForm onCreate={create} today={today} />
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
          {expired.length > 0 && (
            <section className="event-section">
              <h2 className="event-section-title">{t('events.expiredSection')}</h2>
              <div className="event-board">{expired.map(card)}</div>
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
