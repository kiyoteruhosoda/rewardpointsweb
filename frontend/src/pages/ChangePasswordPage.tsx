import { useState, type FormEvent } from 'react'

import { PasswordField } from '../components/PasswordField'
import { useToast } from '../components/ToastNotification'
import { useI18n } from '../i18n'
import { api, errorMessageKey } from '../services/api'

export function ChangePasswordPage() {
  const { t } = useI18n()
  const { notify } = useToast()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await api.post('/api/auth/change-password', {
        current_password: current,
        new_password: next,
      })
      notify('success', t('common.saved'))
      setCurrent('')
      setNext('')
    } catch (err) {
      notify('error', t(errorMessageKey(err)))
    }
  }

  return (
    <form
      className="card"
      onSubmit={(e) => {
        void submit(e)
      }}
    >
      <h1>{t('changePassword.title')}</h1>
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
      <button type="submit">{t('changePassword.submit')}</button>
    </form>
  )
}
