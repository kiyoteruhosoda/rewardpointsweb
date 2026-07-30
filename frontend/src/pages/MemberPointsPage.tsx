/**
 * 1 人のメンバーの残高と履歴。
 *
 * 加算・消費の UI を出すのは「`point:manage` を持っていて、かつサーバーがこの
 * メンバーへ `manage` を返した」ときだけ。メンバー本人は同じ画面で残高と履歴を
 * 見るが、変更の入り口は現れない。
 */
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { MemberSharePanel } from '../components/MemberSharePanel'
import { PointEntryForm } from '../components/PointEntryForm'
import { useToast } from '../components/ToastNotification'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { parseUtc, rewardPoints, type PointLedger } from '../services/rewardPoints'
import { useAuth } from '../store/AuthContext'

/** 履歴では増減が読み取れるよう、加算には符号を付ける（消費は元から `-`）。 */
function withSign(points: number): string {
  return points > 0 ? `+${points}` : String(points)
}

export function MemberPointsPage() {
  const { memberId } = useParams<{ memberId: string }>()
  const { t, locale } = useI18n()
  const { hasScope } = useAuth()
  const { notify } = useToast()
  const [ledger, setLedger] = useState<PointLedger | null>(null)
  const [failed, setFailed] = useState(false)

  const id = Number(memberId)

  const reload = useCallback(
    () =>
      rewardPoints
        .viewPoints(id)
        .then(setLedger)
        .catch((error: unknown) => {
          setFailed(true)
          notify('error', t(errorMessageKey(error)))
        }),
    [id, notify, t],
  )

  useEffect(() => {
    void reload()
  }, [reload])

  const record = async (action: Promise<unknown>) => {
    try {
      await action
      await reload()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  const removeEntry = (entryId: number) => record(rewardPoints.deleteEntry(id, entryId))

  if (failed) return <p className="error">{t('points.unavailable')}</p>
  if (ledger === null) return <p className="loading">{t('common.loading')}</p>

  const canChange = hasScope('point:manage') && ledger.access_level === 'manage'
  // 共有を配れるのは所有者だけ（manage で共有された相手は記録のみ）
  const canShare = hasScope('member:manage') && ledger.is_owner

  return (
    <div className="card">
      <h1>{t('points.title', { name: ledger.member_name })}</h1>
      <p className="balance">
        {t('points.balance')}: <strong>{t('points.value', { points: ledger.balance })}</strong>
      </p>

      {canChange ? (
        <>
          <PointEntryForm
            title={t('points.add')}
            descriptionLabel={t('points.reason')}
            submitLabel={t('points.add')}
            onSubmit={(points, reason) => record(rewardPoints.addPoints(id, points, reason))}
          />
          <PointEntryForm
            title={t('points.consume')}
            descriptionLabel={t('points.application')}
            submitLabel={t('points.consume')}
            onSubmit={(points, application) =>
              record(rewardPoints.consumePoints(id, points, application))
            }
          />
        </>
      ) : (
        <p>{t('points.readOnly')}</p>
      )}

      <h2>{t('points.history')}</h2>
      {ledger.entries.length === 0 ? (
        <p>{t('points.historyEmpty')}</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t('points.when')}</th>
                <th>{t('points.what')}</th>
                <th>{t('points.change')}</th>
                {canChange && <th>{t('common.actions')}</th>}
              </tr>
            </thead>
            <tbody>
              {ledger.entries.map((entry) => (
                <tr key={entry.id}>
                  <td>{parseUtc(entry.occurred_at).toLocaleString(locale)}</td>
                  <td>{entry.description}</td>
                  <td>{t('points.value', { points: withSign(entry.signed_points) })}</td>
                  {canChange && (
                    <td>
                      <button
                        onClick={() => {
                          void removeEntry(entry.id)
                        }}
                      >
                        {t('common.delete')}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {canShare && <MemberSharePanel memberId={id} />}

      <p>
        <Link to="/members">{t('common.back')}</Link>
      </p>
    </div>
  )
}
