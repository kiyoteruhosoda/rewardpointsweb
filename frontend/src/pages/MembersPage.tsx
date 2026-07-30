/**
 * メンバー一覧（自分が所有・共有された・自分自身のメンバー）。
 *
 * メンバー本人がログインした場合も同じ画面で、自分 1 人だけが並ぶ。役割ごとに
 * 画面を分けず、サーバーが返す `access_level` で操作の可否を決める。
 */
import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { useToast } from '../components/ToastNotification'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { rewardPoints, type MemberSummary } from '../services/rewardPoints'
import { useAuth } from '../store/AuthContext'

export function MembersPage() {
  const { t } = useI18n()
  const { hasScope } = useAuth()
  const { notify } = useToast()
  const [members, setMembers] = useState<MemberSummary[] | null>(null)
  const [name, setName] = useState('')
  const [linkedEmail, setLinkedEmail] = useState('')

  const canRegister = hasScope('member:manage')

  const reload = () => rewardPoints.listMembers().then(setMembers)

  useEffect(() => {
    void reload().catch(() => {
      setMembers([])
    })
  }, [])

  const register = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await rewardPoints.createMember(name, linkedEmail.trim() || null)
      setName('')
      setLinkedEmail('')
      await reload()
      notify('success', t('common.saved'))
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  const remove = async (member: MemberSummary) => {
    if (!window.confirm(t('members.confirmDelete', { name: member.name }))) return
    try {
      await rewardPoints.deleteMember(member.id)
      await reload()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  if (members === null) return <p className="loading">{t('common.loading')}</p>

  return (
    <div className="card">
      <h1>{t('members.title')}</h1>

      {canRegister && (
        <form
          className="inline-form"
          onSubmit={(event) => {
            void register(event)
          }}
        >
          <label>
            {t('members.name')}
            <input
              value={name}
              onChange={(event) => {
                setName(event.target.value)
              }}
              required
            />
          </label>
          <label>
            {t('members.linkedEmail')}
            <input
              type="email"
              value={linkedEmail}
              onChange={(event) => {
                setLinkedEmail(event.target.value)
              }}
              placeholder={t('members.linkedEmailPlaceholder')}
            />
          </label>
          <button type="submit">{t('members.add')}</button>
        </form>
      )}

      {members.length === 0 ? (
        <p>{t('members.empty')}</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>{t('members.name')}</th>
              <th>{t('members.balance')}</th>
              <th>{t('common.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {members.map((member) => (
              <tr key={member.id}>
                <td>
                  <Link to={`/members/${member.id}`}>{member.name}</Link>
                  {member.is_self && ` (${t('members.self')})`}
                  {!member.is_self && member.has_linked_user && ` (${t('members.linked')})`}
                </td>
                <td>{t('points.value', { points: member.balance })}</td>
                <td>
                  <Link to={`/members/${member.id}`}>{t('members.history')}</Link>
                  {canRegister && member.access_level === 'manage' && (
                    <>
                      {' '}
                      <button
                        onClick={() => {
                          void remove(member)
                        }}
                      >
                        {t('common.delete')}
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
