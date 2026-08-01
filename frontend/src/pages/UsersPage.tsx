/**
 * ユーザー管理（要 `user:manage`）。
 *
 * ログイン識別子は `username`、画面に出す名前は `display_name` と別に持つ。
 * メールアドレスは任意項目で、空のまま作れる（ADR-0011）。
 */
import { useEffect, useState, type FormEvent } from 'react'

import { PasswordField } from '../components/PasswordField'
import { useToast } from '../components/ToastNotification'
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

  const create = async (e: FormEvent) => {
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
  }

  const toggleActive = async (user: User) => {
    await api.put(`/api/admin/users/${user.id}`, { is_active: !user.is_active })
    await reload()
  }

  const remove = async (user: User) => {
    await api.delete(`/api/admin/users/${user.id}`)
    await reload()
  }

  return (
    <div className="card">
      <h1>{t('users.title')}</h1>
      <form
        className="inline-form"
        onSubmit={(e) => {
          void create(e)
        }}
      >
        <input
          value={username}
          onChange={(e) => {
            setUsername(e.target.value)
          }}
          placeholder={t('common.username')}
          aria-label={t('common.username')}
          autoComplete="off"
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
        <button type="submit">{t('users.add')}</button>
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
            {users.map((user) => (
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
                    onChange={() => {
                      void toggleActive(user)
                    }}
                  />
                </td>
                <td>
                  <button
                    onClick={() => {
                      void remove(user)
                    }}
                  >
                    {t('common.delete')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
