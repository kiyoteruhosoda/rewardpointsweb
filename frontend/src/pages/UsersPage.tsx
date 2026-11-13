/**
 * User management (requires `user:manage`).
 *
 * The login identifier is `username`, kept separate from the on-screen name `display_name`.
 * Email is optional; users can be created without it (ADR-0011).
 *
 * Permissions are granted only via roles. So the list **assigns and removes roles**, and the
 * resulting effective scopes (union of roles) are shown read-only, exactly as the server
 * returns them. There is no way to change scopes directly (CLAUDE.md 「権限管理」, permissions).
 */
import { useEffect, useState, type SubmitEvent } from 'react'

import { ActionButton } from '../components/ActionButton'
import { PasswordField } from '../components/PasswordField'
import { useToast } from '../components/ToastNotification'
import { usePendingAction } from '../hooks/usePendingAction'
import { usePendingRows } from '../hooks/usePendingRows'
import { useSessionValue } from '../hooks/useSessionDraft'
import { useI18n } from '../i18n'
import { api, errorMessageKey } from '../services/api'
import { roleLabel } from '../services/roles'

/** The **ways this user can get into this app** (ADR-0035). */
interface SignInEntrances {
  password: boolean
  totp: boolean
  passkeys: number
  identity_providers: string[]
  /** Whether they can get in as a paired display device (ADR-0047). */
  display_device: boolean
}

/**
 * Turns the ways in into a short list (ADR-0035).
 *
 * ⚠ **IdP-side multi-factor does not show here.** Only the ways this app knows about can be shown,
 * which is precisely what "two authentication systems" means.
 */
function entranceLabels(entrances: SignInEntrances, t: (key: string) => string): string[] {
  const labels: string[] = []
  if (entrances.password) labels.push(t('users.entrance.password'))
  if (entrances.totp) labels.push(t('users.entrance.totp'))
  if (entrances.passkeys > 0) labels.push(`${t('users.entrance.passkey')} ×${entrances.passkeys}`)
  if (entrances.identity_providers.length > 0) labels.push(t('users.entrance.sso'))
  if (entrances.display_device) labels.push(t('users.entrance.display'))
  return labels
}

interface User {
  id: number
  email: string | null
  username: string
  display_name: string
  is_active: boolean
  roles: string[]
  /** Union of the permissions of assigned roles (computed by the server; not editable here). */
  permissions: string[]
  /** Inventory of ways in (ADR-0035). Display only; they cannot be revoked from here. */
  entrances: SignInEntrances
}

interface Role {
  id: number
  name: string
}

/** Actions that can run within a row (affects where the in-progress marker appears). */
type RowAction = 'update' | 'removal'

interface RoleCheckboxesProps {
  user: User
  roles: Role[]
  disabled: boolean
  onToggle: (user: User, roleName: string) => void
}

/**
 * Assigning and removing roles for one user.
 *
 * Listing roles requires `role:manage` (`/api/admin/roles`). Admins without it cannot be
 * offered choices, so in that case only the current role names are shown.
 */
function RoleCheckboxes({ user, roles, disabled, onToggle }: RoleCheckboxesProps) {
  const { t } = useI18n()
  if (roles.length === 0)
    return <>{user.roles.map((name) => roleLabel(t, name)).join(', ') || '—'}</>
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
          <span>{roleLabel(t, role.name)}</span>
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
  // Keep unfinished input across the login round trip (ADR-0058). Passwords are never kept
  const [email, setEmail] = useSessionValue('users.email', '')
  const [username, setUsername] = useSessionValue('users.username', '')
  const [displayName, setDisplayName] = useSessionValue('users.displayName', '')
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

  const [create, creating] = usePendingAction(async (e: SubmitEvent) => {
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

  /** Update for one row. No further action on that row is accepted until it finishes. */
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

  /** Assign/remove roles. Sends the whole resulting set, not a diff (as the API expects). */
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
              {roleLabel(t, r.name)}
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
              <th className="entrance-heading">{t('users.entrances')}</th>
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
                    {/* The ways in cannot be changed (this is an inventory display).
                        Each is revoked on its own side. */}
                    {entranceLabels(user.entrances, t).length === 0 ? (
                      t('users.entrance.none')
                    ) : (
                      <ul className="entrance-list">
                        {entranceLabels(user.entrances, t).map((label) => (
                          <li key={label}>{label}</li>
                        ))}
                      </ul>
                    )}
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
                    {/* Toggling a checkbox does not change the display, so mark the row. */}
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
