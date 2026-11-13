/**
 * Card for one event (ADR-0042).
 *
 * The goal at the top, below it one cell per required achievement. Each achievement sticks one
 * sticker, and when all cells are filled the stamp is pressed. The cell layout (number of columns) is
 * derived from the count (`gridColumns`), so 10 fits as 5 x 2, 30 as 6 x 5, and so on, on one card.
 *
 * Entries to stick, peel off and delete appear only when `canModify`. The child themself only
 * views the same card.
 *
 * Cards past their deadline (ADR-0043) don't show "complete" and show the stickers dimmed. If a
 * parent extends the deadline, stickers can be added again.
 */
import type { CSSProperties } from 'react'

import { useI18n } from '../i18n'
import { parseUtc } from '../services/families'
import type { RewardEvent } from '../services/rewardEvents'
import { gridColumns, stickerLook } from '../services/stickerSheet'
import { ActionButton } from './ActionButton'
import { EventDeadline } from './EventDeadline'
import { Hanko, Sticker } from './StickerArt'

/** The action currently pressed. Spinner only on the pressed button. */
export type RewardEventAction = 'stick' | 'peel' | 'remove' | 'deadline'

interface Props {
  event: RewardEvent
  canModify: boolean
  pending: RewardEventAction | null
  /** The number just stuck. Only that one gets the "stick" animation. */
  freshNumber: number | null
  /** Whether it was just completed on this screen. Adds the stamp-press animation. */
  freshlyCompleted: boolean
  /** Today on the device calendar (YYYY-MM-DD). Used to count days left to the deadline. */
  today: string
  onStick: () => void
  /** Resets the deadline. Rethrows on failure. */
  onChangeDeadline: (deadline: string | null) => Promise<void>
  onPeel: () => void
  onRemove: () => void
}

export function RewardEventCard({
  event,
  canModify,
  pending,
  freshNumber,
  freshlyCompleted,
  today,
  onStick,
  onChangeDeadline,
  onPeel,
  onRemove,
}: Props) {
  const { t, locale } = useI18n()
  const count = event.stickers.length
  const completed = event.completed_at !== null
  const expired = event.is_expired
  const busy = pending !== null
  const squares = Array.from({ length: event.goal_count }, (_, index) => index + 1)
  const sheetStyle = { '--sheet-columns': gridColumns(event.goal_count) } as CSSProperties

  return (
    <article
      className={
        completed
          ? 'event-card event-card-completed'
          : expired
            ? 'event-card event-card-expired'
            : 'event-card'
      }
    >
      <header className="event-card-header">
        <h3 className="event-card-title">{event.title}</h3>
        {canModify && (
          <ActionButton
            type="button"
            className="event-card-remove"
            pending={pending === 'remove'}
            disabled={busy}
            aria-label={`${t('events.remove')}: ${event.title}`}
            onClick={onRemove}
          >
            {t('events.remove')}
          </ActionButton>
        )}
      </header>
      <div className="event-card-tags">
        <span className="event-card-reward">
          {t('events.reward', { points: event.reward_points })}
        </span>
        {!completed && (
          <EventDeadline
            // If the deadline changed after reloading, rebuild the input in its closed state
            key={event.deadline ?? 'none'}
            event={event}
            today={today}
            canModify={canModify}
            pending={pending === 'deadline'}
            disabled={busy}
            onChange={onChangeDeadline}
          />
        )}
      </div>

      <div className="sticker-sheet-frame">
        <ol
          className="sticker-sheet"
          style={sheetStyle}
          aria-label={t('events.progressLabel', { count, goal: event.goal_count })}
        >
          {squares.map((number) => {
            const look = stickerLook(event.id, number)
            const stuck = number <= count
            return (
              <li
                key={number}
                className={stuck ? 'sticker-slot sticker-slot-filled' : 'sticker-slot'}
                aria-hidden="true"
              >
                {stuck ? (
                  <span
                    className={number === freshNumber ? 'sticker sticker-fresh' : 'sticker'}
                    style={{ '--tilt': `${look.tilt}deg` } as CSSProperties}
                  >
                    <Sticker shape={look.shape} color={look.color} />
                  </span>
                ) : (
                  <span className="sticker-slot-number">{number}</span>
                )}
              </li>
            )
          })}
        </ol>
        {completed && (
          <div className={freshlyCompleted ? 'hanko-mark hanko-fresh' : 'hanko-mark'}>
            <Hanko label={t('events.stamp')} />
          </div>
        )}
      </div>

      <footer className="event-card-footer">
        {completed && event.completed_at !== null ? (
          <p className="event-card-progress">
            {t('events.completedOn', {
              date: parseUtc(event.completed_at).toLocaleDateString(locale),
            })}
          </p>
        ) : (
          <p className="event-card-progress" aria-hidden="true">
            <strong>{count}</strong> / {event.goal_count}
          </p>
        )}
        {canModify && !completed && !expired && (
          <div className="event-card-actions">
            {count > 0 && (
              <ActionButton
                type="button"
                className="event-card-quiet"
                pending={pending === 'peel'}
                disabled={busy}
                onClick={onPeel}
              >
                {t('events.peel')}
              </ActionButton>
            )}
            <ActionButton
              type="button"
              className="event-card-achieve"
              pending={pending === 'stick'}
              disabled={busy}
              aria-label={t('events.achieveFor', { title: event.title })}
              onClick={onStick}
            >
              {t('events.achieve')}
            </ActionButton>
          </div>
        )}
      </footer>
    </article>
  )
}
