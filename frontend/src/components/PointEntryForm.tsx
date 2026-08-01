/**
 * ポイントの加算・消費の入力フォーム。
 *
 * 台帳は符号で加算と消費を区別する（ADR-0010）。画面では「加算」「消費」の
 * 2 つのボタンに分け、送るときに符号を付ける。入力欄で負の数を打たせない。
 *
 * 冪等キーは 1 回の記録につき 1 つ発行し、**成功するまで持ち越す**。通信が
 * 途中で切れたときに利用者がもう一度押しても、サーバー側で同じ 1 行として
 * 扱われる（キーを毎回作り直すと、その再送が二重登録になる）。
 */
import { useRef, useState } from 'react'

import { useI18n } from '../i18n'
import { newIdempotencyKey } from '../services/families'

interface Props {
  onSubmit: (amount: number, reason: string, idempotencyKey: string) => Promise<void>
}

export function PointEntryForm({ onSubmit }: Props) {
  const { t } = useI18n()
  const [points, setPoints] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const pendingKey = useRef<string | null>(null)

  const submit = async (sign: 1 | -1) => {
    const amount = sign * Number(points)
    if (busy || !Number.isFinite(amount) || amount === 0 || !reason.trim()) return
    pendingKey.current ??= newIdempotencyKey()
    setBusy(true)
    try {
      await onSubmit(amount, reason, pendingKey.current)
      pendingKey.current = null
      setPoints('')
      setReason('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form
      className="inline-form"
      onSubmit={(event) => {
        // Enter キーでの送信は加算として扱う（消費は明示的に押してもらう）
        event.preventDefault()
        void submit(1)
      }}
    >
      <label>
        {t('points.amount')}
        <input
          type="number"
          min={1}
          value={points}
          onChange={(event) => {
            setPoints(event.target.value)
          }}
          required
        />
      </label>
      <label>
        {t('points.reason')}
        <input
          value={reason}
          onChange={(event) => {
            setReason(event.target.value)
          }}
          required
        />
      </label>
      <button type="submit" disabled={busy}>
        {t('points.add')}
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          void submit(-1)
        }}
      >
        {t('points.consume')}
      </button>
    </form>
  )
}
