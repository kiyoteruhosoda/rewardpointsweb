/**
 * Entry to a family. Only people who do not belong to any family yet stay here.
 *
 * A person can belong to at most one family (ADR-0013), so listing families makes no sense
 * when they already have one. In that case send them straight to the details (family settings).
 * Leaving create/join visible means every tap ends in `already_belongs_to_family`. When
 * membership could not be confirmed (load failure), they are hidden for the same reason.
 *
 * Only parents (member role — the full guardian scope set) can create a family, and the
 * creator becomes owner (ADR-0018). Children (guest) join with an invitation code, so this
 * screen has no "create" for them. If a child uses a parent's invitation code the server
 * refuses (guardian_account_required).
 *
 * This is the only path for someone who already has an account to use a code. When coming
 * from the account creation screen via login, the code is in the URL fragment (`#code=...`)
 * (ADR-0025), so it is prefilled into the join field.
 *
 * Restore from backup (ADR-0026) also lives here. Restoring creates a new family and is only
 * possible while not belonging to one — the same condition as creating, so they sit together.
 */
import { useState, type SubmitEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { ActionButton } from '../components/ActionButton'
import { FamilyImportPanel } from '../components/FamilyImportPanel'
import { useToast } from '../components/ToastNotification'
import { usePendingAction } from '../hooks/usePendingAction'
import { useSessionValue } from '../hooks/useSessionDraft'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families } from '../services/families'
import { readInvitationCode } from '../services/invitationLink'
import { useAuth } from '../store/AuthContext'
import { useFamily } from '../store/FamilyContext'

export function FamiliesPage() {
  const { t } = useI18n()
  const { hasScope } = useAuth()
  const { notify } = useToast()
  const { family, failed, loading, reload } = useFamily()
  const navigate = useNavigate()
  const { pathname, hash } = useLocation()
  const carriedCode = readInvitationCode(hash)
  // Keep unfinished input across the login round trip (ADR-0058)
  const [name, setName] = useSessionValue('families.name', '')
  const [code, setCode] = useState(carriedCode)

  // Creating requires the full guardian scope set (same condition as the server entry — ADR-0018)
  const canCreate = hasScope('family:view', 'family:manage', 'point:view', 'point:manage')

  const enter = async (familyId: number) => {
    // Reload first, then navigate: the left nav and details switch to the new family at once.
    await reload()
    void navigate(`/families/${String(familyId)}`)
  }

  const [create, creating] = usePendingAction(async (event: SubmitEvent) => {
    event.preventDefault()
    try {
      const created = await families.create(name)
      setName('')
      await enter(created.id)
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  })

  const [join, joining] = usePendingAction(async (event: SubmitEvent) => {
    event.preventDefault()
    try {
      const joined = await families.acceptInvitation(code, null)
      setCode('')
      // Do not leave the used code in the URL (a reload would bring back only the notice)
      if (carriedCode) void navigate(pathname, { replace: true })
      notify('success', t('families.joined'))
      await enter(joined.family_id)
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  })

  if (loading) return <p className="loading">{t('common.loading')}</p>
  // It may simply have failed to load. Assuming no membership and showing create/join would
  // always end in `already_belongs_to_family` when tapped.
  if (failed) return <p className="error">{t('families.unavailable')}</p>
  if (family) return <Navigate to={`/families/${String(family.id)}`} replace />

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{t('families.setUp')}</h1>
        <p className="page-subtitle">{t('families.empty')}</p>
      </div>

      {canCreate && (
        <section className="card">
          <h2>{t('families.create')}</h2>
          <form className="inline-form" onSubmit={create}>
            <label>
              {t('families.name')}
              <input
                value={name}
                onChange={(event) => {
                  setName(event.target.value)
                }}
                required
              />
            </label>
            <ActionButton type="submit" pending={creating}>
              {t('families.create')}
            </ActionButton>
          </form>
        </section>
      )}

      {/* Restoring also creates a family, so it requires the same scope as creating (ADR-0026) */}
      {canCreate && <FamilyImportPanel onImported={enter} />}

      <section className="card">
        <h2>{t('families.join')}</h2>
        {carriedCode ? (
          <p className="notice">{t('families.joinPending')}</p>
        ) : (
          <p>{t('families.joinHint')}</p>
        )}
        <form className="inline-form" onSubmit={join}>
          <label>
            {t('families.code')}
            <input
              value={code}
              onChange={(event) => {
                setCode(event.target.value)
              }}
              required
            />
          </label>
          <ActionButton type="submit" pending={joining}>
            {t('families.join')}
          </ActionButton>
        </form>
      </section>
    </div>
  )
}
