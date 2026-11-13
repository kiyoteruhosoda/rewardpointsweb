/**
 * Changing the password.
 *
 * While signed in with a temporary password, every other screen redirects here
 * (ADR-0011). Once changed, `must_change_password` is cleared and normal screens return.
 */
import { useState, type SubmitEvent } from 'react'

import { ActionButton } from '../components/ActionButton'
import { PasswordField } from '../components/PasswordField'
import { useToast } from '../components/ToastNotification'
import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { api, errorMessageKey } from '../services/api'
import { useAuth } from '../store/AuthContext'

export function ChangePasswordPage() {
  const { t } = useI18n()
  const { notify } = useToast()
  const { user, refreshMe } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')

  const [submit, submitting] = usePendingAction(async (e: SubmitEvent) => {
    e.preventDefault()
    try {
      await api.post('/api/auth/change-password', {
        current_password: current,
        new_password: next,
      })
      notify('success', t('common.saved'))
      setCurrent('')
      setNext('')
      // Reload the state after the change to lift the temporary-password gate
      await refreshMe()
    } catch (err) {
      notify('error', t(errorMessageKey(err)))
    }
  })

  // Don't show the form to users without a password (ADR-0034). Showing it would present
  // a field that can never pass to someone who cannot enter a "current password".
  if (user && !user.has_password) {
    return (
      <div className="card">
        <h1>{t('changePassword.title')}</h1>
        <p>{t('changePassword.notSet')}</p>
      </div>
    )
  }

  return (
    <form className="card" onSubmit={submit}>
      <h1>{t('changePassword.title')}</h1>
      {user?.must_change_password && <p>{t('changePassword.required')}</p>}
      <PasswordField
        label={t('changePassword.current')}
        autoComplete="current-password"
        value={current}
        onChange={setCurrent}
        required
      />
      <PasswordField
        label={t('changePassword.new')}
        autoComplete="new-password"
        value={next}
        onChange={setNext}
        minLength={8}
        required
      />
      <ActionButton type="submit" pending={submitting}>
        {t('changePassword.submit')}
      </ActionButton>
    </form>
  )
}
