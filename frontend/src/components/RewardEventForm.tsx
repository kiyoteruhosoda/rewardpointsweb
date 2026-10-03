/**
 * イベントを作る入力欄（ADR-0042）。
 *
 * 目標・達成でもらえるポイント・達成回数の 3 つだけ。達成回数を打つと、できあがる
 * カードのマスの並び（何列 × 何行）を添える — 「1 画面で見渡せるか」を作る前に
 * 確かめられるように。
 *
 * 失敗したときは入力を残す（打ち直させない）。通ったら空にして次を作れるようにする。
 */
import { useState, type FormEvent } from 'react'

import { usePendingAction } from '../hooks/usePendingAction'
import { useRequiredText } from '../hooks/useRequiredText'
import { useI18n } from '../i18n'
import { MAX_GOAL_COUNT, TITLE_MAX_LENGTH, type NewRewardEvent } from '../services/rewardEvents'
import { gridColumns } from '../services/stickerSheet'
import { ActionButton } from './ActionButton'

interface Props {
  /** 送る。失敗したら投げ直す（入力を残すため）。 */
  onCreate: (event: NewRewardEvent) => Promise<void>
}

const DEFAULT_GOAL = '10'

export function RewardEventForm({ onCreate }: Props) {
  const { t } = useI18n()
  const [title, setTitle] = useState('')
  const [reward, setReward] = useState('')
  const [goal, setGoal] = useState(DEFAULT_GOAL)
  const titleRef = useRequiredText(title, t('events.titleRequired'))

  const goalCount = Number(goal)
  const goalIsValid = Number.isInteger(goalCount) && goalCount >= 1 && goalCount <= MAX_GOAL_COUNT
  const columns = goalIsValid ? gridColumns(goalCount) : null

  const [submit, submitting] = usePendingAction(async (event: FormEvent) => {
    event.preventDefault()
    try {
      await onCreate({
        title: title.trim(),
        reward_points: Number(reward),
        goal_count: goalCount,
      })
    } catch {
      // 伝えるのは呼び出し側。入力はそのまま残す
      return
    }
    setTitle('')
    setReward('')
    setGoal(DEFAULT_GOAL)
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
