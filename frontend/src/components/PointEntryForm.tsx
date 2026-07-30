/**
 * ポイントの加算・消費に共通の入力フォーム。
 *
 * 加算（理由）と消費（用途）で変わるのは呼び名と送信先だけなので、同じ形を 2 つ
 * 書かずに文言と送信処理を差し替える。
 */
import { useState, type FormEvent } from 'react'

import { useI18n } from '../i18n'

interface PointEntryFormProps {
  title: string
  descriptionLabel: string
  submitLabel: string
  onSubmit: (points: number, description: string) => Promise<void>
}

export function PointEntryForm({
  title,
  descriptionLabel,
  submitLabel,
  onSubmit,
}: PointEntryFormProps) {
  const { t } = useI18n()
  const [points, setPoints] = useState('')
  const [description, setDescription] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    await onSubmit(Number(points), description)
    setPoints('')
    setDescription('')
  }

  return (
    <form
      className="inline-form"
      onSubmit={(event) => {
        void submit(event)
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
          aria-label={`${title} - ${t('points.amount')}`}
          required
        />
      </label>
      <label>
        {descriptionLabel}
        <input
          value={description}
          onChange={(event) => {
            setDescription(event.target.value)
          }}
          aria-label={`${title} - ${descriptionLabel}`}
          required
        />
      </label>
      <button type="submit">{submitLabel}</button>
    </form>
  )
}
