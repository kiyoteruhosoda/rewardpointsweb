/**
 * ポイントの加算・消費の入力フォーム。記録の訂正にも同じ形を使う（ADR-0022）。
 *
 * 台帳は符号で加算と消費を区別する（ADR-0010）。画面では「加算」「消費」の
 * 2 つのボタンに分け、送るときに符号を付ける。入力欄で負の数を打たせない。
 * 訂正のときも同じで、符号の付け間違い（加算のつもりが消費）はボタンで直せる。
 *
 * 冪等キーは 1 回の記録につき 1 つ発行し、**成功するまで持ち越す**。通信が
 * 途中で切れたときに利用者がもう一度押しても、サーバー側で同じ 1 行として
 * 扱われる（キーを毎回作り直すと、その再送が二重登録になる）。失敗したときは
 * 入力もそのまま残す（打ち直させない）。
 */
import { useRef, useState } from 'react'

import { useI18n } from '../i18n'
import { newIdempotencyKey } from '../services/families'

/** 訂正のときだけ渡す。元の記録の内容と、やめるときの戻り先。 */
interface CorrectionTarget {
  /** 元の符号付きの量。入力欄には絶対値を入れる（符号はボタンが決める）。 */
  amount: number
  reason: string
  onCancel: () => void
}

interface Props {
  onSubmit: (amount: number, reason: string, idempotencyKey: string) => Promise<void>
  /** その家族でよく使われている理由。同じ言い回しを打ち直さずに済ませる。 */
  reasonSuggestions: string[]
  /** 渡すと訂正の入力になる（元の内容が入り、ボタンが「保存」になる）。 */
  editing?: CorrectionTarget
}

const REASON_LIST_ID = 'point-entry-reasons'

export function PointEntryForm({ onSubmit, reasonSuggestions, editing }: Props) {
  const { t } = useI18n()
  const [points, setPoints] = useState(editing ? String(Math.abs(editing.amount)) : '')
  const [reason, setReason] = useState(editing?.reason ?? '')
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
    } catch {
      // 失敗は呼び出し元がトーストで伝える。ここでは入力と鍵を残し、
      // 同じ内容・同じ鍵でもう一度押せる状態にしておく
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
          list={REASON_LIST_ID}
          required
        />
      </label>
      {/* 候補は datalist で出す。自由入力のままにしておきたいので select にしない */}
      <datalist id={REASON_LIST_ID}>
        {reasonSuggestions.map((suggestion) => (
          <option key={suggestion} value={suggestion} />
        ))}
      </datalist>
      <button type="submit" disabled={busy}>
        {editing ? t('points.saveAsAdd') : t('points.add')}
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          void submit(-1)
        }}
      >
        {editing ? t('points.saveAsConsume') : t('points.consume')}
      </button>
      {editing && (
        <button type="button" disabled={busy} onClick={editing.onCancel}>
          {t('common.cancel')}
        </button>
      )}
    </form>
  )
}
