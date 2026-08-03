/**
 * 表示名とメールアドレスの変更。
 *
 * ログイン識別子（`username`）はここでは変えない。変えるとログインの手順が
 * 変わり、家族から本人へ伝えた ID とも食い違う（ADR-0011）。
 *
 * メールアドレスは任意項目。空にして保存すると外れる — メールアドレスを持たない
 * アカウントは、パスワードのリセットを親からの一時パスワードで受ける。
 */
import { useState, type FormEvent } from 'react'

import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { api, errorMessageKey } from '../services/api'
import { useAuth, type Me } from '../store/AuthContext'
import { ActionButton } from './ActionButton'
import { useToast } from './ToastNotification'

export function ProfileForm() {
  const { t } = useI18n()
  const { user, refreshMe } = useAuth()
  const { notify } = useToast()
  const [displayName, setDisplayName] = useState(user?.display_name ?? '')
  const [email, setEmail] = useState(user?.email ?? '')

  const [submit, submitting] = usePendingAction(async (event: FormEvent) => {
    event.preventDefault()
    try {
      await api.put<Me>('/api/auth/me', {
        display_name: displayName,
        email: email.trim() === '' ? null : email.trim(),
      })
      await refreshMe()
      notify('success', t('common.saved'))
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  })

  return (
    <form onSubmit={submit}>
      <label>
        {t('profile.displayName')}
        <input
          value={displayName}
          onChange={(event) => {
            setDisplayName(event.target.value)
          }}
          maxLength={100}
          required
        />
      </label>
      <label>
        {t('profile.email')}
        <input
          type="email"
          value={email}
          onChange={(event) => {
            setEmail(event.target.value)
          }}
          placeholder={t('profile.emailPlaceholder')}
        />
      </label>
      <p className="page-subtitle">{t('profile.emailHint')}</p>
      <ActionButton type="submit" pending={submitting}>
        {t('common.save')}
      </ActionButton>
    </form>
  )
}
