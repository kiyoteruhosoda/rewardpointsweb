/**
 * 1 人の子の「毎日のボーナス」を決める入力欄（ADR-0024）。
 *
 * 決めておくと、日付が変わるたびに決めた量が台帳へ 1 行足される。足すのはサーバー
 * 側で、この入力欄は約束を決める・やめるだけ。決めた瞬間には何も足さないので、
 * 「保存したのに残高が変わらない」と読まれないよう、いつから始まるかを文言で示す。
 *
 * 量は子ども一人ひとりで違ってよい。並べるのは家族設定の画面（`DailyBonusPanel`）で、
 * ここは 1 人ぶんだけを受け持つ。
 */
import { useState, type FormEvent } from 'react'

import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families, type DailyBonus } from '../services/families'
import { usePendingAction } from '../hooks/usePendingAction'
import { ActionButton } from './ActionButton'
import { useToast } from './ToastNotification'

interface Props {
  familyId: number
  ledgerId: number
  /** 誰のボーナスか。同じ画面に兄弟の欄が並ぶので、名前を欄に添える。 */
  childName: string
  /** いまの設定。決めていなければ null。 */
  bonus: DailyBonus | null
  /** 保存・停止のあと、家族を読み直す。 */
  onChanged: () => Promise<unknown>
}

export function DailyBonusForm({ familyId, ledgerId, childName, bonus, onChanged }: Props) {
  const { t } = useI18n()
  const { notify } = useToast()
  // 開いた時点の設定を初期値にする。保存後は家族を読み直して作り直される
  // （`key` に設定の有無を渡す。呼び出し側を参照）
  const [amount, setAmount] = useState(bonus ? String(bonus.amount) : '')
  const [reason, setReason] = useState(bonus?.reason ?? t('dailyBonus.defaultReason'))

  const [save, saving] = usePendingAction(async (event: FormEvent) => {
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
        {/* 記録の入力欄にも「理由」があるので、別の言い回しにする（同じ画面に
            同じラベルが 2 つ並ぶと、どちらへ打っているのか分からなくなる） */}
        <label>
          {t('dailyBonus.reason')}
          <input
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
