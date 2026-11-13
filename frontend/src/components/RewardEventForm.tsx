/**
 * Input for creating an event (ADR-0042).
 *
 * Goal, points earned on completion, required count, and an optional deadline (ADR-0043). Typing the count
 * shows the resulting card's cell layout (columns x rows) — so "does it fit on one screen" can be
 * checked before creating it.
 *
 * On failure the input is kept (no retyping). On success it is cleared so the next one can be made.
 */
import { type SubmitEvent } from 'react'

import { usePendingAction } from '../hooks/usePendingAction'
import { useRequiredText } from '../hooks/useRequiredText'
import { useSessionValue } from '../hooks/useSessionDraft'
import { useI18n } from '../i18n'
import { MAX_GOAL_COUNT, TITLE_MAX_LENGTH, type NewRewardEvent } from '../services/rewardEvents'
import { gridColumns } from '../services/stickerSheet'
import { ActionButton } from './ActionButton'

interface Props {
  /** Sends. Rethrows on failure (to keep the input). */
  onCreate: (event: NewRewardEvent) => Promise<void>
  /** Today on the device calendar (YYYY-MM-DD). Past dates cannot be chosen as the deadline. */
  today: string
}

const DEFAULT_GOAL = '10'

export function RewardEventForm({ onCreate, today }: Props) {
  const { t } = useI18n()
  // A draft survives the login round trip (ADR-0058)
  const [title, setTitle] = useSessionValue('events.title', '')
  const [reward, setReward] = useSessionValue('events.reward', '')
  const [goal, setGoal] = useSessionValue('events.goal', DEFAULT_GOAL)
  // Empty means no deadline
  const [deadline, setDeadline] = useSessionValue('events.deadline', '')
  const titleRef = useRequiredText(title, t('events.titleRequired'))

  const goalCount = Number(goal)
  const goalIsValid = Number.isInteger(goalCount) && goalCount >= 1 && goalCount <= MAX_GOAL_COUNT
  const columns = goalIsValid ? gridColumns(goalCount) : null

  const [submit, submitting] = usePendingAction(async (event: SubmitEvent) => {
    event.preventDefault()
    try {
      await onCreate({
        title: title.trim(),
        reward_points: Number(reward),
        goal_count: goalCount,
        deadline: deadline === '' ? null : deadline,
      })
    } catch {
      // Reporting is the caller's job. Keep the input as is
      return
    }
    setTitle('')
    setReward('')
    setGoal(DEFAULT_GOAL)
    setDeadline('')
  })

  return (
    <form className="event-form" onSubmit={submit}>
      <label className="event-form-title">
        {t('events.fieldTitle')}
        <input
          ref={titleRef}
          value={title}
          maxLength={TITLE_MAX_LENGTH}
          placeholder={t('events.fieldTitlePlaceholder')}
          onChange={(event) => {
            setTitle(event.target.value)
          }}
          required
        />
      </label>
      <label>
        {t('events.fieldReward')}
        <input
          type="number"
          inputMode="numeric"
          min={1}
          value={reward}
          onChange={(event) => {
            setReward(event.target.value)
          }}
          required
        />
      </label>
      <label>
        {t('events.fieldGoal')}
        <input
          type="number"
          inputMode="numeric"
          min={1}
          max={MAX_GOAL_COUNT}
          value={goal}
          onChange={(event) => {
            setGoal(event.target.value)
          }}
          required
        />
      </label>
      <label>
        {t('events.fieldDeadline')}
        <input
          type="date"
          min={today}
          value={deadline}
          onChange={(event) => {
            setDeadline(event.target.value)
          }}
        />
      </label>
      <ActionButton type="submit" pending={submitting}>
        {t('events.create')}
      </ActionButton>
      {columns !== null && (
        <p className="field-hint event-form-shape">
          {t('events.gridShape', { columns, rows: Math.ceil(goalCount / columns) })}
        </p>
      )}
    </form>
  )
}
