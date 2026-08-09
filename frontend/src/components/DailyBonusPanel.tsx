/**
 * 毎日のボーナスの設定（ADR-0024）。
 *
 * 決めておくと、日付が変わるたびに決めた量が台帳へ 1 行足される。足すのはサーバー
 * 側で、この画面は約束を決める・やめるだけ。決めた瞬間には何も足さないので、
 * 「保存したのに残高が変わらない」と読まれないよう、いつから始まるかを文言で示す。
 *
 * 出るのは台帳を変更できる相手だけ（`can_modify`）。子ども本人は同じ画面で残高と
 * 履歴を見るが、この入り口は現れない。
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
  /** いまの設定。決めていなければ null。 */
  bonus: DailyBonus | null
  /** 保存・停止のあと、台帳を読み直す。 */
  onChanged: () => Promise<unknown>
}

export function DailyBonusPanel({ familyId, ledgerId, bonus, onChanged }: Props) {
  const { t } = useI18n()
  const { notify } = useToast()
  // 開いた時点の設定を初期値にする。保存後は台帳を読み直して作り直される
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
    if (!window.confirm(t('dailyBonus.confirmStop'))) return
    try {
      await families.stopDailyBonus(familyId, ledgerId)
      notify('success', t('dailyBonus.stopped'))
      await onChanged()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  })

  return (
    <section className="card">
      <h2>{t('dailyBonus.title')}</h2>
      <p>{bonus ? t('dailyBonus.active', { points: bonus.amount }) : t('dailyBonus.hint')}</p>
      <form className="inline-form" onSubmit={save}>
        <label>
          {t('dailyBonus.amount')}
          <input
            type="number"
            min={1}
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
    </section>
  )
}
