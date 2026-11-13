/**
 * Input for one child's "daily bonus" (ADR-0024).
 *
 * Once set, the chosen amount is added to the ledger as one row each time the date changes. The server
 * does the adding; this input only sets or stops the commitment. Nothing is added at the moment it is set,
 * so the text says when it starts, to avoid it reading as "I saved but the balance didn't change".
 *
 * The amount may differ per child. Listing them is the family settings screen's job (`DailyBonusPanel`);
 * this handles just one child.
 */
import { useState, type SubmitEvent } from 'react'

import { useI18n } from '../i18n'
import { useRequiredText } from '../hooks/useRequiredText'
import { errorMessageKey } from '../services/api'
import { families, type DailyBonus } from '../services/families'
import { usePendingAction } from '../hooks/usePendingAction'
import { ActionButton } from './ActionButton'
import { useToast } from './ToastNotification'

interface Props {
  familyId: number
  ledgerId: number
  /** Whose bonus it is. Siblings' inputs appear on the same screen, so the name goes with the input. */
  childName: string
  /** Current setting. null if not set. */
  bonus: DailyBonus | null
  /** Reloads the family after save/stop. */
  onChanged: () => Promise<unknown>
}

export function DailyBonusForm({ familyId, ledgerId, childName, bonus, onChanged }: Props) {
  const { t } = useI18n()
  const { notify } = useToast()
  // Use the setting at open time as the initial value. After saving, the family is reloaded and this is rebuilt
  // (whether a setting exists is passed as `key`; see the caller)
  const [amount, setAmount] = useState(bonus ? String(bonus.amount) : '')
  const [reason, setReason] = useState(bonus?.reason ?? t('dailyBonus.defaultReason'))
  const reasonRef = useRequiredText(reason, t('common.reasonRequired'))

  const [save, saving] = usePendingAction(async (event: SubmitEvent) => {
    event.preventDefault()
    const points = Number(amount)
    if (!Number.isFinite(points) || points < 1 || !reason.trim()) return
    try {
      await families.setDailyBonus(familyId, ledgerId, points, reason)
      notify('success', t('dailyBonus.saved'))
      await onChanged()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  })

  const [stop, stopping] = usePendingAction(async () => {
    if (!window.confirm(t('dailyBonus.confirmStop', { name: childName }))) return
    try {
      await families.stopDailyBonus(familyId, ledgerId)
      notify('success', t('dailyBonus.stopped'))
      await onChanged()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  })

  return (
    <div className="card-inset">
      <p className="daily-bonus-child">{childName}</p>
      <p>{bonus ? t('dailyBonus.active', { points: bonus.amount }) : t('dailyBonus.inactive')}</p>
      <form className="inline-form" onSubmit={save}>
        <label>
          {t('dailyBonus.amount')}
          <input
            type="number"
            min={1}
            aria-label={t('dailyBonus.amountFor', { name: childName })}
            value={amount}
            onChange={(event) => {
              setAmount(event.target.value)
            }}
            required
          />
        </label>
        {/* The record input also has a "reason", so use different wording (with two identical
            labels on the same screen, you can't tell which one you're typing into) */}
        <label>
          {t('dailyBonus.reason')}
          <input
            ref={reasonRef}
            aria-label={t('dailyBonus.reasonFor', { name: childName })}
            value={reason}
            onChange={(event) => {
              setReason(event.target.value)
            }}
            required
          />
        </label>
        <ActionButton type="submit" pending={saving} disabled={stopping}>
          {bonus ? t('dailyBonus.update') : t('dailyBonus.start')}
        </ActionButton>
        {bonus && (
          <ActionButton type="button" pending={stopping} disabled={saving} onClick={stop}>
            {t('dailyBonus.stop')}
          </ActionButton>
        )}
      </form>
    </div>
  )
}
