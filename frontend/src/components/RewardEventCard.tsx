/**
 * イベント 1 枚ぶんのカード（ADR-0042）。
 *
 * 一番上に目標、その下に達成回数ぶんのマス。1 回達成するたびにシールが 1 枚貼られ、
 * マスが全部埋まると判子が押される。マスの並び（列の数）は達成回数から決める
 * （`gridColumns`）ので、10 回なら 5 × 2、30 回なら 6 × 5 のように 1 枚に収まる。
 *
 * 貼る・はがす・消すの入口は `canModify` のときだけ出す。子ども本人は同じカードを
 * 見るだけ。
 */
import type { CSSProperties } from 'react'

import { useI18n } from '../i18n'
import { parseUtc } from '../services/families'
import type { RewardEvent } from '../services/rewardEvents'
import { gridColumns, stickerLook } from '../services/stickerSheet'
import { ActionButton } from './ActionButton'
import { Hanko, Sticker } from './StickerArt'

/** いま押されている操作。押したボタンにだけスピナーを出す。 */
export type RewardEventAction = 'stick' | 'peel' | 'remove'

interface Props {
  event: RewardEvent
  canModify: boolean
  pending: RewardEventAction | null
  /** 直前に貼られた番号。その 1 枚だけ「貼る」動きを付ける。 */
  freshNumber: number | null
  /** この画面で達成したばかりか。判子を押す動きを付ける。 */
  freshlyCompleted: boolean
  onStick: () => void
  onPeel: () => void
  onRemove: () => void
}

export function RewardEventCard({
  event,
  canModify,
  pending,
  freshNumber,
  freshlyCompleted,
  onStick,
  onPeel,
  onRemove,
}: Props) {
  const { t, locale } = useI18n()
  const count = event.stickers.length
  const completed = event.completed_at !== null
  const busy = pending !== null
  const squares = Array.from({ length: event.goal_count }, (_, index) => index + 1)
  const sheetStyle = { '--sheet-columns': gridColumns(event.goal_count) } as CSSProperties

  return (
    <article className={completed ? 'event-card event-card-completed' : 'event-card'}>
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
      <p className="event-card-reward">{t('events.reward', { points: event.reward_points })}</p>

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
        {canModify && !completed && (
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
