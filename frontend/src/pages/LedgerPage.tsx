/**
 * 1 人の子の台帳（残高と履歴）。
 *
 * 台帳は追記専用で、訂正は打ち消しの行を足して表す（ADR-0010）。履歴からは
 * 何も消えないので、取り消されたレコードには印を付けて対で見せる。
 *
 * 変更 UI を出すのはサーバーが `can_modify` を返したときだけ。子ども本人は同じ
 * 画面で残高と履歴を見るが、変更の入り口は現れない。
 *
 * 残高を出すのはこの画面だけではない。ダッシュボード・ナビゲーション・家族設定は
 * 家族の応答（FamilyContext）に載る残高を見るので、記録したら**両方**読み直す
 * （ADR-0021）。片方だけだと、同じ残高が画面ごとに食い違う。
 */
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { PointEntryForm } from '../components/PointEntryForm'
import { useToast } from '../components/ToastNotification'
import { useRefreshOnReturn } from '../hooks/useRefreshOnReturn'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families, newIdempotencyKey, parseUtc, type Ledger } from '../services/families'
import { useFamily } from '../store/FamilyContext'

/** 増減が読み取れるよう、加算には符号を付ける（消費は元から `-`）。 */
function withSign(amount: number): string {
  return amount > 0 ? `+${amount}` : String(amount)
}

export function LedgerPage() {
  const { familyId, ledgerId } = useParams<{ familyId: string; ledgerId: string }>()
  const { t, locale } = useI18n()
  const { notify } = useToast()
  const { reload: reloadFamily } = useFamily()
  const [ledger, setLedger] = useState<Ledger | null>(null)
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null)
  const [reasons, setReasons] = useState<string[]>([])
  const [failed, setFailed] = useState(false)

  const family = Number(familyId)
  const id = Number(ledgerId)

  const reload = useCallback(
    () =>
      families
        .viewLedger(family, id)
        .then((result) => {
          setLedger(result.data)
          setFetchedAt(result.fetchedAt)
          setFailed(false)
        })
        .catch((error: unknown) => {
          setFailed(true)
          notify('error', t(errorMessageKey(error)))
        }),
    [family, id, notify, t],
  )

  // 別の子の台帳へ移ったら、前の子の残高と履歴を消してから読む。残したまま読むと、
  // 応答が届くまでのあいだ、開いた覚えのない子の数字がこの画面の見出しの下に出る。
  useEffect(() => {
    setLedger(null)
    setFetchedAt(null)
    void reload()
  }, [reload])

  // 手元に戻ってきたら読み直す（別の端末からの記録はこの画面には届かない）
  useRefreshOnReturn(reload)

  // 候補が取れなくても記録はできる（自由入力なので、無ければ何も出さないだけ）
  useEffect(() => {
    void families
      .reasonSuggestions(family)
      .then(setReasons)
      .catch(() => {
        setReasons([])
      })
  }, [family])

  /**
   * 記録の後は台帳と家族の両方を読み直す。残高の出所は 2 つあり
   * （台帳の応答とこの家族の応答）、片方だけ読み直すと、この画面は増えたのに
   * ダッシュボードとナビゲーションの子は古い数字のまま、という食い違いになる。
   */
  const run = async (action: Promise<unknown>) => {
    try {
      await action
      await Promise.all([reload(), reloadFamily()])
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  const record = (amount: number, reason: string, idempotencyKey: string) =>
    run(families.record(family, id, { amount, reason, idempotencyKey }))

  const reverse = (transactionId: number) => {
    if (!window.confirm(t('points.confirmReverse'))) return
    void run(families.reverse(family, id, transactionId, newIdempotencyKey()))
  }

  // 読み直しに失敗しても、いま出している残高は消さない（手元に戻った瞬間の
  // 一時的な不通で、読めていた履歴まで消えると出所の分からない画面になる）。
  // 失敗はトーストで伝わっており、時刻の行が古さを示す。
  if (ledger === null) {
    return failed ? (
      <p className="error">{t('points.unavailable')}</p>
    ) : (
      <p className="loading">{t('common.loading')}</p>
    )
  }

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{t('points.title', { name: ledger.display_name })}</h1>
      </div>

      <section className="card">
        <p className="balance">
          {t('points.balance')}: <strong>{t('points.value', { points: ledger.balance })}</strong>
        </p>
        {ledger.balance < 0 && <p>{t('points.negative', { points: -ledger.balance })}</p>}
        {/* オフラインでは古いキャッシュが出得るので、いつの情報かを常に示す（ADR-0015） */}
        {fetchedAt !== null && (
          <p className="fetched-at">
            {t('points.fetchedAt', { time: fetchedAt.toLocaleString(locale) })}
          </p>
        )}
      </section>

      <section className="card">
        {ledger.can_modify ? (
          <PointEntryForm onSubmit={record} reasonSuggestions={reasons} />
        ) : (
          <p>{t('points.readOnly')}</p>
        )}
      </section>

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
                {ledger.transactions.map((transaction) => (
                  <tr key={transaction.id} className={transaction.is_reversed ? 'reversed' : ''}>
                    <td>{parseUtc(transaction.occurred_at).toLocaleString(locale)}</td>
                    <td>
                      {transaction.reason}
                      {transaction.reversal_of_id !== null && ` (${t('points.isReversal')})`}
                      {transaction.is_reversed && ` (${t('points.wasReversed')})`}
                    </td>
                    <td>{t('points.value', { points: withSign(transaction.amount) })}</td>
                    <td>{transaction.granted_by ?? '—'}</td>
                    {ledger.can_modify && (
                      <td>
                        {transaction.reversal_of_id === null && !transaction.is_reversed && (
                          <button
                            type="button"
                            onClick={() => {
                              reverse(transaction.id)
                            }}
                          >
                            {t('points.reverse')}
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <p>
        <Link to={`/families/${family}`}>{t('common.back')}</Link>
      </p>
    </div>
  )
}
