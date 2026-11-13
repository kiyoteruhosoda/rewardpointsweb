/**
 * One child's ledger (balance and history).
 *
 * The ledger is append-only; corrections are expressed by adding a reversal row (ADR-0010).
 * Nothing disappears from history, so reversed records are marked and shown as a pair.
 *
 * Input mistakes are fixed with "correct" (ADR-0022): one action that reverses and rewrites
 * the right content, adding two rows to history (the reversal and the corrected record).
 *
 * Modification UI is shown only when the server returns `can_modify`. The child sees the
 * balance and history on the same screen, but no entry to modify appears.
 *
 * The family's agreed rules (ADR-0027) are shown **read-only** below the record input.
 * They are edited in family settings, and the daily bonus setting (ADR-0024) was moved
 * there too — family rules are kept in one place.
 *
 * This is not the only screen that shows balances. The dashboard, navigation and family settings
 * read balances from the family response (FamilyContext), so after recording reload **both**
 * (ADR-0021). Reloading only one makes the same balance disagree between screens.
 */
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ActionButton } from '../components/ActionButton'
import { Pager } from '../components/Pager'
import { BalanceTrend } from '../components/BalanceTrend'
import { PointEntryForm } from '../components/PointEntryForm'
import { useToast } from '../components/ToastNotification'
import { usePaged } from '../hooks/usePaged'
import { usePendingRows } from '../hooks/usePendingRows'
import { useRefreshOnReturn } from '../hooks/useRefreshOnReturn'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import {
  families,
  newIdempotencyKey,
  parseUtc,
  type Ledger,
  type Transaction,
} from '../services/families'
import { useFamily } from '../store/FamilyContext'

/** History page size. On a smartphone, 2–3 swipes read through one page. */
const HISTORY_PAGE_SIZE = 20

/** Prefix additions with a sign so the change is readable (spending already has `-`). */
function withSign(amount: number): string {
  return amount > 0 ? `+${amount}` : String(amount)
}

export function LedgerPage() {
  const { familyId, ledgerId } = useParams<{ familyId: string; ledgerId: string }>()
  const { t, locale } = useI18n()
  const { notify } = useToast()
  const { family: myFamily, reload: reloadFamily } = useFamily()
  const [ledger, setLedger] = useState<Ledger | null>(null)
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null)
  // Where the trend line extends to. If the response has no time, use the time it was received
  const [asOf, setAsOf] = useState<Date>(() => new Date())
  const [reasons, setReasons] = useState<string[]>([])
  const [failed, setFailed] = useState(false)
  // Target of a correction. null means the input is for a normal record
  const [editing, setEditing] = useState<Transaction | null>(null)
  // Record being reversed (show a spinner only on the tapped row's button)
  const { pendingActionOf, runForRow } = usePendingRows<'reversal'>()
  // History is paged (newest first, so page 1 is the latest). The trend chart uses all rows
  const history = usePaged(ledger?.transactions ?? [], HISTORY_PAGE_SIZE)
  const { setPage: setHistoryPage } = history

  const family = Number(familyId)
  const id = Number(ledgerId)

  const reload = useCallback(
    () =>
      families
        .viewLedger(family, id)
        .then((result) => {
          setLedger(result.data)
          setFetchedAt(result.fetchedAt)
          setAsOf(result.fetchedAt ?? new Date())
          setFailed(false)
        })
        .catch((error: unknown) => {
          setFailed(true)
          notify('error', t(errorMessageKey(error)))
        }),
    [family, id, notify, t],
  )

  // When moving to another child's ledger, clear the previous child's balance and history first.
  // Otherwise, until the response arrives, numbers of a child never opened show under the heading.
  useEffect(() => {
    setLedger(null)
    setFetchedAt(null)
    setEditing(null)
    setHistoryPage(1)
    void reload()
  }, [reload, setHistoryPage])

  // Reload when returning to the app (records from other devices do not reach this screen)
  useRefreshOnReturn(reload)

  // Recording works without suggestions (free input; nothing is shown if there are none)
  const loadReasons = useCallback(
    () =>
      families
        .reasonSuggestions(family)
        .then(setReasons)
        .catch(() => {
          setReasons([])
        }),
    [family],
  )

  useEffect(() => {
    void loadReasons()
  }, [loadReasons])

  /**
   * After recording, reload both the ledger and the family. Balances come from two sources
   * (the ledger response and this family response); reloading only one leaves this screen
   * updated while the dashboard and navigation still show the old number for the child.
   *
   * Write failures are reported here and then **rethrown to the caller**. Only the sender can
   * decide whether to keep what was typed or keep the correction input open.
   * Reload failures are not rethrown (the write itself succeeded).
   */
  const run = async (action: Promise<unknown>) => {
    try {
      await action
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
      throw error
    }
    // Also refetch suggestions. Reasons just written join them, and reasons rephrased by a
    // correction drop out. Without refetching, a fixed typo could be picked again
    await Promise.all([reload(), reloadFamily(), loadReasons()])
  }

  // A written row goes to the top of page 1. Go back there if viewing another page
  const record = async (amount: number, reason: string, idempotencyKey: string) => {
    await run(families.record(family, id, { amount, reason, idempotencyKey }))
    setHistoryPage(1)
  }

  /** Close the input only when the correction succeeds (keep the edits on failure). */
  const correct = async (
    target: number,
    amount: number,
    reason: string,
    idempotencyKey: string,
  ) => {
    await run(families.correct(family, id, target, { amount, reason, idempotencyKey }))
    setEditing(null)
  }

  const reverse = (transactionId: number) => {
    if (!window.confirm(t('points.confirmReverse'))) return
    // A reversal has no input, so reporting the error is enough
    void runForRow(transactionId, 'reversal', () =>
      run(families.reverse(family, id, transactionId, newIdempotencyKey())).catch(() => undefined),
    )
  }

  // Even if reloading fails, keep the balance shown (a brief outage just after returning
  // should not wipe history already loaded, leaving a screen of unknown origin).
  // The failure is reported by a toast, and the timestamp row shows how stale it is.
  if (ledger === null) {
    return failed ? (
      <p className="error">{t('points.unavailable')}</p>
    ) : (
      <p className="loading">{t('common.loading')}</p>
    )
  }

  // Family rules (ADR-0027). Show nothing when the family is not loaded (this screen is useful
  // as long as the ledger shows; an unreadable rule is not worth a disclaimer)
  const familyRules = myFamily?.rules ?? null

  // While correcting, replace the record input in place. With "add" and "fix" inputs
  // side by side on one screen, it is unclear which one you are typing into.
  const entryForm =
    editing === null ? (
      <PointEntryForm onSubmit={record} reasonSuggestions={reasons} />
    ) : (
      <>
        <h2>{t('points.correctTitle')}</h2>
        <p>{t('points.correctNote')}</p>
        <PointEntryForm
          // When switching to correct another record, rebuild the input from that record
          key={editing.id}
          onSubmit={(amount, reason, idempotencyKey) =>
            correct(editing.id, amount, reason, idempotencyKey)
          }
          reasonSuggestions={reasons}
          editing={{
            amount: editing.amount,
            reason: editing.reason,
            onCancel: () => {
              setEditing(null)
            },
          }}
        />
      </>
    )

  return (
    <div className="page">
      <div className="page-heading page-heading-row">
        <h1>{t('points.title', { name: ledger.display_name })}</h1>
        {/* Events (effort cards, ADR-0042) are per child, so they are entered from the ledger */}
        <Link className="page-heading-link" to={`/families/${family}/ledgers/${id}/events`}>
          {t('events.open')}
        </Link>
      </div>

      <section className="card">
        <p className="balance">
          {t('points.balance')}: <strong>{t('points.value', { points: ledger.balance })}</strong>
        </p>
        {ledger.balance < 0 && <p>{t('points.negative', { points: -ledger.balance })}</p>}
        {/* Offline may show stale cache, so always show how current the info is (ADR-0015) */}
        {fetchedAt !== null && (
          <p className="fetched-at">
            {t('points.fetchedAt', { time: fetchedAt.toLocaleString(locale) })}
          </p>
        )}
      </section>

      <section className="card">
        {ledger.can_modify ? entryForm : <p>{t('points.readOnly')}</p>}

        {/* The family's agreed rules (ADR-0027). **Read-only**; edited in family settings.
            Placed right below the input so they can be read before deciding to add or spend.
            Source is the family response (FamilyContext) — not in the ledger response (returning
            the same text from 2 places makes screens disagree right after an edit) */}
        {familyRules !== null && (
          <div className="card-inset family-rules">
            <h2>{t('families.rules')}</h2>
            <p className="family-rules-text">{familyRules}</p>
          </div>
        )}
      </section>

      <BalanceTrend transactions={ledger.transactions} asOf={asOf} />

      <section className="card">
        <h2>{t('points.history')}</h2>
        {ledger.transactions.length === 0 ? (
          <p>{t('points.historyEmpty')}</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t('points.when')}</th>
                  <th>{t('points.what')}</th>
                  <th>{t('points.change')}</th>
                  <th>{t('points.by')}</th>
                  {ledger.can_modify && <th>{t('common.actions')}</th>}
                </tr>
              </thead>
              <tbody>
                {history.rows.map((transaction) => (
                  <tr key={transaction.id} className={transaction.is_reversed ? 'reversed' : ''}>
                    <td>{parseUtc(transaction.occurred_at).toLocaleString(locale)}</td>
                    <td>
                      {transaction.reason}
                      {transaction.reversal_of_id !== null && ` (${t('points.isReversal')})`}
                      {transaction.corrects_id !== null && ` (${t('points.isCorrection')})`}
                      {transaction.is_reversed && ` (${t('points.wasReversed')})`}
                    </td>
                    <td>{t('points.value', { points: withSign(transaction.amount) })}</td>
                    <td>{transaction.granted_by ?? '—'}</td>
                    {ledger.can_modify && (
                      <td>
                        {/* Reversal rows and already-reversed rows cannot be corrected */}
                        {transaction.reversal_of_id === null && !transaction.is_reversed && (
                          <>
                            <button
                              type="button"
                              onClick={() => {
                                setEditing(transaction)
                              }}
                            >
                              {t('points.edit')}
                            </button>
                            <ActionButton
                              type="button"
                              pending={pendingActionOf(transaction.id) === 'reversal'}
                              onClick={() => {
                                reverse(transaction.id)
                              }}
                            >
                              {t('points.reverse')}
                            </ActionButton>
                          </>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pager page={history.page} pageCount={history.pageCount} onChange={setHistoryPage} />
      </section>

      <p>
        <Link to={`/families/${family}`}>{t('common.back')}</Link>
      </p>
    </div>
  )
}
