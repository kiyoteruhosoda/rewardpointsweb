/**
 * Requesting a password reset.
 *
 * The request uses the login identifier (username). Email is optional,
 * so it cannot be the starting point (ADR-0011). Accounts without an email (children)
 * cannot be sent a link, but the server returns the same `accepted` as for a nonexistent name (so outsiders
 * cannot check whether a child's username exists; task #733). So the "sent"
 * message always adds that accounts without an email should ask a parent.
 *
 * When email sending itself is unavailable, `mail_unavailable` is returned. Saying "sent"
 * here would leave the user waiting for an email that never arrives, so likewise guide them to a parent.
 */
import { useState, type SubmitEvent } from 'react'

import { ActionButton } from '../components/ActionButton'
import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { api } from '../services/api'

interface Outcome {
  status: 'accepted' | 'mail_unavailable'
}

const OUTCOME_MESSAGE: Record<Outcome['status'], string> = {
  accepted: 'forgot.sent',
  mail_unavailable: 'forgot.mailUnavailable',
}

export function ForgotPasswordPage() {
  const { t } = useI18n()
  const [username, setUsername] = useState('')
  const [outcome, setOutcome] = useState<Outcome['status'] | null>(null)

  const [submit, submitting] = usePendingAction(async (e: SubmitEvent) => {
    e.preventDefault()
    const response = await api.post<Outcome>('/api/auth/forgot-password', { username })
    setOutcome(response.status)
  })

  return (
    <div className="auth-page">
      <form className="card" onSubmit={submit}>
        <h1>{t('forgot.title')}</h1>
        {outcome !== null ? (
          <p>{t(OUTCOME_MESSAGE[outcome])}</p>
        ) : (
          <>
            <label>
              {t('login.username')}
              <input
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value)
                }}
                required
              />
            </label>
            <ActionButton type="submit" pending={submitting}>
              {t('forgot.submit')}
            </ActionButton>
          </>
        )}
      </form>
    </div>
  )
}
