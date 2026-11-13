import { useEffect, useState } from 'react'

import { ActionButton } from '../components/ActionButton'
import { useToast } from '../components/ToastNotification'
import { usePendingAction } from '../hooks/usePendingAction'
import { usePendingRows } from '../hooks/usePendingRows'
import { useSessionValue } from '../hooks/useSessionDraft'
import { useI18n } from '../i18n'
import { api, errorMessageKey } from '../services/api'
import { roleLabel } from '../services/roles'

interface Role {
  id: number
  name: string
  permissions: string[]
}

interface Permission {
  id: number
  code: string
}

/** Operations that can run within a row (decides where the in-progress marker goes). */
type RowAction = 'update' | 'removal'

export function RolesPage() {
  const { t } = useI18n()
  const { notify } = useToast()
  const [roles, setRoles] = useState<Role[]>([])
  const [permissions, setPermissions] = useState<Permission[]>([])
  // Keep the draft across the login round trip (ADR-0058)
  const [name, setName] = useSessionValue('roles.name', '')
  const { pendingActionOf, runForRow } = usePendingRows<RowAction>()

  const reload = () => api.get<Role[]>('/api/admin/roles').then(setRoles)

  useEffect(() => {
    void reload()
    void api
      .get<Permission[]>('/api/admin/permissions')
      .then(setPermissions)
      .catch(() => {
        setPermissions([])
      })
  }, [])

  const [create, creating] = usePendingAction(async () => {
    if (!name.trim()) return
    try {
      await api.post('/api/admin/roles', { name, permissions: [] })
      setName('')
      await reload()
    } catch (err) {
      notify('error', t(errorMessageKey(err)))
    }
  })

  /** Updates one row. Rejects further operations on that row until it finishes. */
  const runExclusively = (roleId: number, action: RowAction, request: () => Promise<unknown>) =>
    runForRow(roleId, action, async () => {
      try {
        await request()
        await reload()
      } catch (err) {
        notify('error', t(errorMessageKey(err)))
      }
    })

  const togglePermission = (role: Role, code: string) => {
    const next = role.permissions.includes(code)
      ? role.permissions.filter((c) => c !== code)
      : [...role.permissions, code]
    return runExclusively(role.id, 'update', () =>
      api.put(`/api/admin/roles/${role.id}`, { permissions: next }),
    )
  }

  const remove = (role: Role) =>
    runExclusively(role.id, 'removal', () => api.delete(`/api/admin/roles/${role.id}`))

  return (
    <div className="card">
      <h1>{t('roles.title')}</h1>
      <div className="inline-form">
        <input
          value={name}
          onChange={(e) => {
            setName(e.target.value)
          }}
          placeholder="name"
        />
        <ActionButton type="button" pending={creating} onClick={create}>
          {t('roles.add')}
        </ActionButton>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Role</th>
              {permissions.map((p) => (
                <th key={p.id} className="vertical">
                  <code>{p.code}</code>
                </th>
              ))}
              <th>{t('common.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {roles.map((role) => {
              const rowAction = pendingActionOf(role.id)
              const busy = rowAction !== null
              return (
                <tr key={role.id}>
                  <td>{roleLabel(t, role.name)}</td>
                  {permissions.map((p) => (
                    <td key={p.id}>
                      <input
                        type="checkbox"
                        aria-label={`${role.name}: ${p.code}`}
                        checked={role.permissions.includes(p.code)}
                        disabled={busy}
                        onChange={() => {
                          void togglePermission(role, p.code)
                        }}
                      />
                    </td>
                  ))}
                  <td>
                    <ActionButton
                      type="button"
                      pending={rowAction === 'removal'}
                      disabled={busy}
                      onClick={() => {
                        void remove(role)
                      }}
                    >
                      {t('common.delete')}
                    </ActionButton>
                    {/* Toggling a checkbox does not change the display on press, so show a marker on the row. */}
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
