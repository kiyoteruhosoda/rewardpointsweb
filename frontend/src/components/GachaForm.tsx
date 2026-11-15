/**
 * Input for creating or editing a gacha machine (ADR-0060).
 *
 * Name, price of one draw, and the prizes (name, weight, miss or not). Each prize shows its chance
 * as the weights are typed, so a parent can see "how often does the big one come out" before saving.
 * A machine of only misses cannot be saved (the server refuses it too).
 *
 * On failure the input is kept (no retyping). After creating, it is cleared for the next one.
 */
import { useRef, useState, type SubmitEvent } from 'react'

import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import {
  MAX_PRIZES,
  MAX_WEIGHT,
  NAME_MAX_LENGTH,
  chanceOf,
  type GachaDesign,
  type GachaPrize,
} from '../services/gacha'
import { ActionButton } from './ActionButton'
import { capsuleColor } from './GachaArt'

interface PrizeRow {
  /** Stable key for React while rows are added and removed. */
  key: number
  name: string
  weight: string
  isMiss: boolean
}

interface Props {
  /** The machine being edited. Omit to create a new one. */
  initial?: GachaDesign
  /** Sends. Rethrows on failure (to keep the input). */
  onSubmit: (design: GachaDesign) => Promise<void>
  /** Shown only when editing. */
  onCancel?: () => void
}

function toRows(prizes: readonly GachaPrize[]): PrizeRow[] {
  return prizes.map((prize, index) => ({
    key: index,
    name: prize.name,
    weight: String(prize.weight),
    isMiss: prize.is_miss,
  }))
}

const STARTER_ROWS: readonly GachaPrize[] = [{ name: '', weight: 1, is_miss: false }]

function weightOf(row: PrizeRow): number {
  const weight = Number(row.weight)
  return Number.isInteger(weight) && weight >= 1 && weight <= MAX_WEIGHT ? weight : 0
}

export function GachaForm({ initial, onSubmit, onCancel }: Props) {
  const { t } = useI18n()
  const [name, setName] = useState(initial?.name ?? '')
  const [price, setPrice] = useState(initial === undefined ? '' : String(initial.price))
  const [rows, setRows] = useState<PrizeRow[]>(() => toRows(initial?.prizes ?? STARTER_ROWS))
  const nextKey = useRef(rows.length)

  const prizes: GachaPrize[] = rows.map((row) => ({
    name: row.name.trim(),
    weight: weightOf(row),
    is_miss: row.isMiss,
  }))
  const chances = prizes.map((prize) => chanceOf(prize, prizes))
  const onlyMisses = rows.every((row) => row.isMiss)

  const change = (key: number, patch: Partial<PrizeRow>) => {
    setRows((current) => current.map((row) => (row.key === key ? { ...row, ...patch } : row)))
  }

  const addRow = () => {
    const key = nextKey.current++
    setRows((current) => [...current, { key, name: '', weight: '1', isMiss: false }])
  }

  const [submit, submitting] = usePendingAction(async (event: SubmitEvent) => {
    event.preventDefault()
    try {
      await onSubmit({ name: name.trim(), price: Number(price), prizes })
    } catch {
      // Reporting is the caller's job. Keep the input as is
      return
    }
    if (initial === undefined) {
      setName('')
      setPrice('')
      setRows(toRows(STARTER_ROWS))
    }
  })

  return (
    <form className="gacha-form" onSubmit={submit}>
      <div className="gacha-form-head">
        <label>
          {t('gacha.fieldName')}
          <input
            value={name}
            maxLength={NAME_MAX_LENGTH}
            placeholder={t('gacha.fieldNamePlaceholder')}
            onChange={(event) => {
              setName(event.target.value)
            }}
            required
          />
        </label>
        <label>
          {t('gacha.fieldPrice')}
          <input
            type="number"
            inputMode="numeric"
            min={1}
            step={1}
            value={price}
            onChange={(event) => {
              setPrice(event.target.value)
            }}
            required
          />
        </label>
      </div>

      <fieldset className="gacha-form-prizes">
        <legend>{t('gacha.prizes')}</legend>
        <p className="gacha-form-hint">{t('gacha.weightHint')}</p>
        <ul>
          {rows.map((row, index) => (
            <li key={row.key} className="gacha-form-prize">
              <span
                className="gacha-prize-dot"
                style={{ background: row.isMiss ? 'var(--slot-line)' : capsuleColor(index) }}
                aria-hidden="true"
              />
              <label>
                <span className="visually-hidden">{t('gacha.fieldPrizeName')}</span>
                <input
                  value={row.name}
                  maxLength={NAME_MAX_LENGTH}
                  placeholder={row.isMiss ? t('gacha.miss') : t('gacha.fieldPrizeName')}
                  aria-label={t('gacha.fieldPrizeNameFor', { number: index + 1 })}
                  onChange={(event) => {
                    change(row.key, { name: event.target.value })
                  }}
                  required
                />
              </label>
              <label className="gacha-form-weight">
                {t('gacha.fieldWeight')}
                <input
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={MAX_WEIGHT}
                  step={1}
                  value={row.weight}
                  aria-label={t('gacha.fieldWeightFor', { number: index + 1 })}
                  onChange={(event) => {
                    change(row.key, { weight: event.target.value })
                  }}
                  required
                />
              </label>
              <label className="gacha-form-miss">
                <input
                  type="checkbox"
                  checked={row.isMiss}
                  onChange={(event) => {
                    change(row.key, { isMiss: event.target.checked })
                  }}
                />
                {t('gacha.miss')}
              </label>
              <span className="gacha-form-chance">
                {t('gacha.chance', { percent: chances[index] ?? 0 })}
              </span>
              <button
                type="button"
                className="gacha-text-button"
                disabled={rows.length === 1}
                aria-label={t('gacha.removePrizeFor', { number: index + 1 })}
                onClick={() => {
                  setRows((current) => current.filter((r) => r.key !== row.key))
                }}
              >
                {t('gacha.removePrize')}
              </button>
            </li>
          ))}
        </ul>
        <button type="button" disabled={rows.length >= MAX_PRIZES} onClick={addRow}>
          {t('gacha.addPrize')}
        </button>
        {onlyMisses && (
          <p className="error" role="alert">
            {t('gacha.needsPrize')}
          </p>
        )}
      </fieldset>

      <div className="gacha-form-actions">
        {onCancel !== undefined && (
          <button type="button" onClick={onCancel}>
            {t('common.cancel')}
          </button>
        )}
        <ActionButton type="submit" pending={submitting} disabled={onlyMisses}>
          {initial === undefined ? t('gacha.create') : t('common.save')}
        </ActionButton>
      </div>
    </form>
  )
}
