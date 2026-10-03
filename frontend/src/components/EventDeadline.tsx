/**
 * カードの期限（ADR-0043）の札と、決め直す入力欄。
 *
 * 札は残りの日数で言い方と色を変える（あと N 日／あしたまで／今日まで／期限切れ）。
 * 期限切れかどうかはサーバーの `is_expired` で決め、日数は端末の暦で数える。
 *
 * 親には「期限を変える」を出す。期限切れのカードも、延ばせばまた貼れる。過ぎた日は
 * 選べない（`min` を今日にする。サーバーも断る）。
 */
import { useState, type FormEvent } from 'react'

import { useI18n } from '../i18n'
import { DEADLINE_SOON_DAYS, daysUntil } from '../services/eventDeadline'
import type { RewardEvent } from '../services/rewardEvents'
import { ActionButton } from './ActionButton'

interface Props {
  event: RewardEvent
  /** 端末の暦での今日（YYYY-MM-DD）。 */
  today: string
  canModify: boolean
  pending: boolean
  disabled: boolean
  /** 決め直す（null で期限なし）。失敗したら投げ直す（入力を開いたままにする）。 */
  onChange: (deadline: string | null) => Promise<void>
}

function formatDay(value: string, locale: string): string {
  const [year = 0, month = 1, day = 1] = value.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString(locale, {
    month: 'numeric',
    day: 'numeric',
  })
}

export function EventDeadline({ event, today, canModify, pending, disabled, onChange }: Props) {
  const { t, locale } = useI18n()
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(event.deadline ?? '')

  const save = async (deadline: string | null) => {
    try {
      await onChange(deadline)
      setEditing(false)
    } catch {
      // 伝えるのは呼び出し側。入力欄は開いたまま残す
    }
  }

  if (editing) {
    return (
      <form
        className="event-deadline-form"
        onSubmit={(formEvent: FormEvent) => {
          formEvent.preventDefault()
          void save(value === '' ? null : value)
        }}
      >
        <label>
          <span className="visually-hidden">{t('events.fieldDeadline')}</span>
          <input
            type="date"
            min={today}
            value={value}
            onChange={(changeEvent) => {
              setValue(changeEvent.target.value)
            }}
            required
          />
        </label>
        <ActionButton type="submit" pending={pending} disabled={disabled}>
          {t('common.save')}
        </ActionButton>
        {event.deadline !== null && (
          <button
            type="button"
            disabled={disabled || pending}
            onClick={() => {
              void save(null)
            }}
          >
            {t('events.deadlineClear')}
          </button>
        )}
        <button
          type="button"
          disabled={pending}
          onClick={() => {
            setEditing(false)
          }}
        >
          {t('common.cancel')}
        </button>
      </form>
    )
  }

  const left = event.deadline === null ? null : daysUntil(event.deadline, today)
  let label: string | null = null
  let tone = 'event-deadline'
  if (event.deadline !== null && left !== null) {
    const date = formatDay(event.deadline, locale)
    if (event.is_expired) {
      label = t('events.deadlineExpired', { date })
      tone = 'event-deadline event-deadline-expired'
    } else if (left <= 0) {
      label = t('events.deadlineToday')
      tone = 'event-deadline event-deadline-soon'
    } else if (left === 1) {
      label = t('events.deadlineTomorrow')
      tone = 'event-deadline event-deadline-soon'
    } else {
      label = t('events.deadlineDaysLeft', { days: left, date })
      if (left <= DEADLINE_SOON_DAYS) tone = 'event-deadline event-deadline-soon'
    }
  }

  return (
    <>
      {label !== null && <span className={tone}>{label}</span>}
      {canModify && (
        <button
          type="button"
          className="event-deadline-edit"
          disabled={disabled}
          onClick={() => {
            setValue(event.deadline ?? '')
            setEditing(true)
          }}
        >
          {event.deadline === null ? t('events.deadlineAdd') : t('events.deadlineChange')}
        </button>
      )}
    </>
  )
}
