/**
 * Input form for adding/spending points. The same form is used to correct a record (ADR-0022).
 *
 * The ledger distinguishes adding and spending by sign (ADR-0010). On screen these are split into two
 * buttons, "add" and "spend", and the sign is applied when sending. Negative numbers are not typed in.
 * When correcting, swapping add and spend is rare, so radio buttons preselected with the original
 * record's kind are shown and a single "save" sends it. You can see which side is being fixed, and
 * switch the radio only when deliberately swapping (ADR-0049).
 *
 * One idempotency key is issued per record and **carried over until it succeeds**. If the connection
 * drops midway and the user presses again, the server treats it as the same single row
 * (recreating the key every time would turn that resend into a duplicate). On failure the
 * input is also kept as is (no retyping).
 *
 * Empty-field checks are left to the browser (`required` and `useRequiredText`). Silently dropping in
 * JavaScript makes a screen where pressing does nothing.
 */
import { useRef, useState } from 'react'

import { useI18n } from '../i18n'
import { useRequiredText } from '../hooks/useRequiredText'
import { newIdempotencyKey } from '../services/families'
import { ActionButton } from './ActionButton'

/** Passed only when correcting. The original record's content and where to return on cancel. */
interface CorrectionTarget {
  /** Original signed amount. The input holds the absolute value (the radio decides the sign). */
  amount: number
  reason: string
  onCancel: () => void
}

interface Props {
  onSubmit: (amount: number, reason: string, idempotencyKey: string) => Promise<void>
  /** Reasons commonly used in this family. Saves retyping the same wording. */
  reasonSuggestions: string[]
  /** When passed, this becomes a correction form (original content filled in, button becomes "save"). */
  editing?: CorrectionTarget
}

const REASON_LIST_ID = 'point-entry-reasons'

// The pressed button decides the sign. Unless both are submit buttons, only the spend side
// would be sent without the browser's required check (silently dropped inside `submit()`,
// making a screen where pressing with empty fields does nothing).
const CONSUME = 'consume'

/** Which button submitted. Submitting with the Enter key uses the default button (add). */
function signOf(event: SubmitEvent): 1 | -1 {
  return event.submitter?.getAttribute('value') === CONSUME ? -1 : 1
}

export function PointEntryForm({ onSubmit, reasonSuggestions, editing }: Props) {
  const { t } = useI18n()
  const [points, setPoints] = useState(editing ? String(Math.abs(editing.amount)) : '')
  // Kind when correcting. Preselect the same side as the original record
  const [editingSign, setEditingSign] = useState<1 | -1>(editing && editing.amount < 0 ? -1 : 1)
  const [reason, setReason] = useState(editing?.reason ?? '')
  // Sign being sent (spinner only on the pressed button). null means not sending.
  const [submittingSign, setSubmittingSign] = useState<1 | -1 | null>(null)
  const busy = submittingSign !== null
  const pendingKey = useRef<string | null>(null)
  const reasonRef = useRequiredText(reason, t('common.reasonRequired'))

  const submit = async (sign: 1 | -1) => {
    const amount = sign * Number(points)
    if (busy || !Number.isFinite(amount) || amount === 0 || !reason.trim()) return
    pendingKey.current ??= newIdempotencyKey()
    setSubmittingSign(sign)
    try {
      await onSubmit(amount, reason, pendingKey.current)
      pendingKey.current = null
      setPoints('')
      setReason('')
    } catch {
      // The caller reports failures with a toast. Keep the input and key here
      // so it can be pressed again with the same content and the same key
    } finally {
      setSubmittingSign(null)
    }
  }

  return (
    <form
      className="inline-form"
      onSubmit={(event) => {
        event.preventDefault()
        void submit(editing ? editingSign : signOf(event.nativeEvent))
      }}
    >
      {editing && (
        <fieldset className="entry-kind" disabled={busy}>
          <legend>{t('points.kind')}</legend>
          {([1, -1] as const).map((sign) => (
            <label key={sign}>
              <input
                type="radio"
                name="entry-kind"
                checked={editingSign === sign}
                onChange={() => {
                  setEditingSign(sign)
                }}
              />
              {sign === 1 ? t('points.kindAdd') : t('points.kindConsume')}
            </label>
          ))}
        </fieldset>
      )}
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
          ref={reasonRef}
          value={reason}
          onChange={(event) => {
            setReason(event.target.value)
          }}
          list={REASON_LIST_ID}
          required
        />
      </label>
      {/* Suggestions come from a datalist. We want to keep free input, so no select */}
      <datalist id={REASON_LIST_ID}>
        {reasonSuggestions.map((suggestion) => (
          <option key={suggestion} value={suggestion} />
        ))}
      </datalist>
      {editing ? (
        <>
          <ActionButton type="submit" pending={busy} disabled={busy}>
            {t('common.save')}
          </ActionButton>
          <button type="button" disabled={busy} onClick={editing.onCancel}>
            {t('common.cancel')}
          </button>
        </>
      ) : (
        <>
          <ActionButton type="submit" pending={submittingSign === 1} disabled={busy}>
            {t('points.add')}
          </ActionButton>
          <ActionButton
            type="submit"
            value={CONSUME}
            pending={submittingSign === -1}
            disabled={busy}
          >
            {t('points.consume')}
          </ActionButton>
        </>
      )}
    </form>
  )
}
