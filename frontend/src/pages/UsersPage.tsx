/**
 * ユーザー管理（要 `user:manage`）。
 *
 * ログイン識別子は `username`、画面に出す名前は `display_name` と別に持つ。
 * メールアドレスは任意項目で、空のまま作れる（ADR-0011）。
 */
import { useEffect, useState, type FormEvent } from 'react'

import { ActionButton } from '../components/ActionButton'
import { PasswordField } from '../components/PasswordField'
import { useToast } from '../components/ToastNotification'
import { usePendingAction } from '../hooks/usePendingAction'
import { usePendingRows } from '../hooks/usePendingRows'
import { useI18n } from '../i18n'
import { api, errorMessageKey } from '../services/api'

interface User {
  id: number
  email: string | null
  username: string
  display_name: string
  is_active: boolean
  roles: string[]
}

interface Role {
  id: number
  name: string
}

/** 行の中で実行しうる操作（実行中の目印をどこに出すかが変わる）。 */
type RowAction = 'update' | 'removal'

export function UsersPage() {
  const { t } = useI18n()
  const { notify } = useToast()
  const [users, setUsers] = useState<User[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('member')
  const { pendingActionOf, runForRow } = usePendingRows<RowAction>()

  const reload = () => api.get<User[]>('/api/admin/users').then(setUsers)

  useEffect(() => {
    void reload()
    void api
      .get<Role[]>('/api/admin/roles')
      .then(setRoles)
      .catch(() => {
        setRoles([])
      })
  }, [])

  const [create, creating] = usePendingAction(async (e: FormEvent) => {
    e.preventDefault()
    try {
      await api.post('/api/admin/users', {
        username,
        display_name: displayName,
        email: email.trim() === '' ? null : email.trim(),
        password,
        roles: [role],
      })
      setEmail('')
      setUsername('')
      setDisplayName('')
      setPassword('')
      await reload()
      notify('success', t('common.saved'))
    } catch (err) {
      notify('error', t(errorMessageKey(err)))
    }
  })

  /** 1 行分の更新。終わるまでその行の次の操作を受け付けない。 */
  const runExclusively = (user: User, action: RowAction, request: () => Promise<unknown>) =>
    runForRow(user.id, action, async () => {
      try {
        await request()
        await reload()
      } catch (err) {
        notify('error', t(errorMessageKey(err)))
      }
    })

  const toggleActive = (user: User) =>
    runExclusively(user, 'update', () =>
      api.put(`/api/admin/users/${user.id}`, { is_active: !user.is_active }),
    )

  const remove = (user: User) =>
    runExclusively(user, 'removal', () => api.delete(`/api/admin/users/${user.id}`))

  return (
    <div className="card">
      <h1>{t('users.title')}</h1>
      <form className="inline-form" onSubmit={create}>
        <input
          value={username}
          onChange={(e) => {
            setUsername(e.target.value)
          }}
          placeholder={t('common.username')}
          aria-label={t('common.username')}
          autoComplete="off"
          minLength={3}
          maxLength={255}
          required
        />
        <input
          value={displayName}
          onChange={(e) => {
            setDisplayName(e.target.value)
          }}
          placeholder={t('common.displayName')}
          aria-label={t('common.displayName')}
          maxLength={100}
          required
        />
        <input
          type="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value)
          }}
          placeholder={t('users.emailOptional')}
          aria-label={t('users.emailOptional')}
        />
        <PasswordField
          placeholder={t('common.password')}
          autoComplete="new-password"
          value={password}
          onChange={setPassword}
          minLength={8}
          required
        />
        <select
          value={role}
          onChange={(e) => {
            setRole(e.target.value)
          }}
          aria-label={t('users.role')}
        >
          {roles.map((r) => (
            <option key={r.id} value={r.name}>
              {r.name}
            </option>
          ))}
        </select>
        <ActionButton type="submit" pending={creating}>
          {t('users.add')}
        </ActionButton>
      </form>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>{t('common.username')}</th>
              <th>{t('common.displayName')}</th>
              <th>{t('common.email')}</th>
              <th>{t('users.role')}</th>
              <th>{t('common.active')}</th>
              <th>{t('common.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => {
              const rowAction = pendingActionOf(user.id)
              const busy = rowAction !== null
              return (
                <tr key={user.id}>
                  <td>{user.id}</td>
                  <td>{user.username}</td>
                  <td>{user.display_name}</td>
                  <td>{user.email ?? '—'}</td>
                  <td>{user.roles.join(', ')}</td>
                  <td>
                    <input
                      type="checkbox"
                      checked={user.is_active}
                      aria-label={t('common.active')}
                      disabled={busy}
                      onChange={() => {
                        void toggleActive(user)
                      }}
                    />
                  </td>
                  <td>
                    <ActionButton
                      type="button"
                      pending={rowAction === 'removal'}
                      disabled={busy}
                      onClick={() => {
                        void remove(user)
                      }}
                    >
                      {t('common.delete')}
                    </ActionButton>
                    {/* チェックの付け外しは押しても表示が変わらないので、行に目印を出す。 */}
                    {rowAction === 'update' && (
                      <span className="spinner" role="status" aria-label={t('common.processing')} />
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
