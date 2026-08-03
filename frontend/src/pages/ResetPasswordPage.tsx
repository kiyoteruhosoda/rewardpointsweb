import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { ActionButton } from '../components/ActionButton'
import { PasswordField } from '../components/PasswordField'
import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { api, errorMessageKey } from '../services/api'

export function ResetPasswordPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const [submit, submitting] = usePendingAction(async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await api.post('/api/auth/reset-password', {
        token: params.get('token') ?? '',
        new_password: password,
      })
      navigate('/login')
    } catch (err) {
      setError(errorMessageKey(err))
    }
  })

  return (
    <div className="auth-page">
      <form className="card" onSubmit={submit}>
        <h1>{t('reset.title')}</h1>
        {error && <p className="error">{t(error)}</p>}
        <PasswordField
          label={t('reset.newPassword')}
          autoComplete="new-password"
          value={password}
          onChange={setPassword}
          minLength={8}
          required
        />
        <ActionButton type="submit" pending={submitting}>
          {t('reset.submit')}
        </ActionButton>
      </form>
    </div>
  )
}
