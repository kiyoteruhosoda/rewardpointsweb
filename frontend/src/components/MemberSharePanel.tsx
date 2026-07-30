/**
 * メンバーの共有（誰に、どこまで渡すか）。
 *
 * 共有先はメールアドレスで指定する。アカウント一覧を配る API は無い（管理者に
 * 全アカウントを見せないため）。
 */
import { useCallback, useEffect, useState, type FormEvent } from 'react'

import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { rewardPoints, type AccessLevel, type MemberShare } from '../services/rewardPoints'
import { useToast } from './ToastNotification'

const LEVELS: AccessLevel[] = ['view', 'manage']

export function MemberSharePanel({ memberId }: { memberId: number }) {
  const { t } = useI18n()
  const { notify } = useToast()
  const [shares, setShares] = useState<MemberShare[]>([])
  const [email, setEmail] = useState('')
  const [level, setLevel] = useState<AccessLevel>('view')

  const reload = useCallback(
    () =>
      rewardPoints
        .listShares(memberId)
        .then(setShares)
        .catch(() => {
          setShares([])
        }),
    [memberId],
  )

  useEffect(() => {
    void reload()
  }, [reload])

  const share = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await rewardPoints.shareMember(memberId, email, level)
      setEmail('')
      await reload()
      notify('success', t('common.saved'))
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  const revoke = async (targetUserId: number) => {
    try {
      await rewardPoints.revokeShare(memberId, targetUserId)
      await reload()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  return (
    <section className="card-inset">
      <h2>{t('shares.title')}</h2>
      <p>{t('shares.hint')}</p>

      <form
        className="inline-form"
        onSubmit={(event) => {
          void share(event)
        }}
      >
        <label>
          {t('shares.email')}
          <input
            type="email"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value)
            }}
            required
          />
        </label>
        <label>
          {t('shares.level')}
          <select
            value={level}
            onChange={(event) => {
              setLevel(event.target.value as AccessLevel)
            }}
          >
            {LEVELS.map((value) => (
              <option key={value} value={value}>
                {t(`shares.level.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <button type="submit">{t('shares.add')}</button>
      </form>

      {shares.length === 0 ? (
        <p>{t('shares.empty')}</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t('shares.email')}</th>
                <th>{t('shares.level')}</th>
                <th>{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {shares.map((item) => (
                <tr key={item.user_id}>
                  <td>{item.email}</td>
                  <td>{t(`shares.level.${item.access_level}`)}</td>
                  <td>
                    <button
                      onClick={() => {
                        void revoke(item.user_id)
                      }}
                    >
                      {t('shares.revoke')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
