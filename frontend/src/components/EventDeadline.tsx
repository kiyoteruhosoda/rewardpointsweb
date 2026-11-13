/**
 * The deadline badge on a card (ADR-0043) and the input to reset it.
 *
 * The badge changes wording and colour by days left (N days left / until tomorrow / until today / expired).
 * Whether it is expired comes from the server's `is_expired`; days are counted on the device calendar.
 *
 * Parents get "change deadline". Even an expired card can be stuck again once extended. Past dates
 * cannot be chosen (`min` is today; the server also refuses).
 */
import { useState, type SubmitEvent } from 'react'

import { useI18n } from '../i18n'
import { DEADLINE_SOON_DAYS, daysUntil } from '../services/eventDeadline'
import type { RewardEvent } from '../services/rewardEvents'
import { ActionButton } from './ActionButton'

interface Props {
  event: RewardEvent
  /** Today on the device calendar (YYYY-MM-DD). */
  today: string
  canModify: boolean
  pending: boolean
  disabled: boolean
  /** Resets the deadline (null means no deadline). Rethrows on failure (keeps the input open). */
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
      // Reporting is the caller's job. Keep the input open
    }
  }

  if (editing) {
    return (
      <form
        className="event-deadline-form"
        onSubmit={(formEvent: SubmitEvent) => {
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
