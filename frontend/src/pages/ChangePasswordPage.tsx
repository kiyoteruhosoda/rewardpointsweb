/**
 * パスワードの変更。
 *
 * 一時パスワードでログインしている間は、他の画面がすべてここへ寄せられる
 * （ADR-0011）。変更が終わると `must_change_password` が下り、通常の画面へ戻る。
 */
import { useState, type FormEvent } from 'react'

import { PasswordField } from '../components/PasswordField'
import { useToast } from '../components/ToastNotification'
import { useI18n } from '../i18n'
import { api, errorMessageKey } from '../services/api'
import { useAuth } from '../store/AuthContext'

export function ChangePasswordPage() {
  const { t } = useI18n()
  const { notify } = useToast()
  const { user, refreshMe } = useAuth()
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
      // 一時パスワードでの関門を外すため、変更後の状態を読み直す
      await refreshMe()
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
      <button type="submit">{t('changePassword.submit')}</button>
    </form>
  )
}
