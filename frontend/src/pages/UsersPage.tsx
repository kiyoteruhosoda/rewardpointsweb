/**
 * ユーザー管理（要 `user:manage`）。
 *
 * ログイン識別子は `username`、画面に出す名前は `display_name` と別に持つ。
 * メールアドレスは任意項目で、空のまま作れる（ADR-0011）。
 *
 * 権限はロール経由でのみ付く。そのため一覧では **ロールを付け外し** し、その結果
 * 実際に効く scope（ロールの和集合）はサーバーが返した値をそのまま読み取り専用で
 * 並べる。scope を直に付け替える口は用意しない（CLAUDE.md「権限管理」）。
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
  /** 所属ロールの権限の和集合（サーバーが計算する。ここでは変更できない）。 */
  permissions: string[]
}

interface Role {
  id: number
  name: string
}

/** 行の中で実行しうる操作（実行中の目印をどこに出すかが変わる）。 */
type RowAction = 'update' | 'removal'

interface RoleCheckboxesProps {
  user: User
  roles: Role[]
  disabled: boolean
  onToggle: (user: User, roleName: string) => void
}

/**
 * 1 人分のロールの付け外し。
 *
 * ロール一覧の取得には `role:manage` が要る（`/api/admin/roles`）。持っていない
 * 管理者には選択肢を出しようがないので、その場合は今のロール名だけを示す。
 */
function RoleCheckboxes({ user, roles, disabled, onToggle }: RoleCheckboxesProps) {
  if (roles.length === 0) return <>{user.roles.join(', ') || '—'}</>
  return (
    <div className="checkbox-list">
      {roles.map((role) => (
        <label key={role.id}>
          <input
            type="checkbox"
            aria-label={`${user.username}: ${role.name}`}
            checked={user.roles.includes(role.name)}
            disabled={disabled}
            onChange={() => {
              onToggle(user, role.name)
            }}
          />
          <span>{role.name}</span>
        </label>
      ))}
    </div>
  )
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

  /** ロールの付け外し。差分ではなく変更後の全体を送る（API がそう受け取る）。 */
  const toggleRole = (user: User, roleName: string) => {
    const next = user.roles.includes(roleName)
      ? user.roles.filter((name) => name !== roleName)
      : [...user.roles, roleName]
    return runExclusively(user, 'update', () =>
      api.put(`/api/admin/users/${user.id}`, { roles: next }),
    )
  }

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
              <th>{t('users.roles')}</th>
              <th>{t('users.effectivePermissions')}</th>
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
                  <td>
                    <RoleCheckboxes
                      user={user}
                      roles={roles}
                      disabled={busy}
                      onToggle={(target, roleName) => {
                        void toggleRole(target, roleName)
                      }}
                    />
                  </td>
                  <td>
                    {user.permissions.length === 0 ? (
                      '—'
                    ) : (
                      <div className="scope-list">
                        {user.permissions.map((code) => (
                          <code key={code}>{code}</code>
                        ))}
                      </div>
                    )}
                  </td>
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
