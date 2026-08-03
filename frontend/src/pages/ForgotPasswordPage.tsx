/**
 * パスワード再設定の申し込み。
 *
 * 申し込みはログイン識別子（ユーザー名）で行う。メールアドレスは任意項目なので、
 * それを起点にできない（ADR-0011）。メールアドレスを持たないアカウント（子ども）
 * にはリンクを送れないため、サーバーが `ask_guardian` を返し、親へ頼むよう案内する。
 */
import { useState, type FormEvent } from 'react'

import { ActionButton } from '../components/ActionButton'
import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { api } from '../services/api'

interface Outcome {
  status: 'accepted' | 'ask_guardian'
}

export function ForgotPasswordPage() {
  const { t } = useI18n()
  const [username, setUsername] = useState('')
  const [outcome, setOutcome] = useState<Outcome['status'] | null>(null)

  const [submit, submitting] = usePendingAction(async (e: FormEvent) => {
    e.preventDefault()
    const response = await api.post<Outcome>('/api/auth/forgot-password', { username })
    setOutcome(response.status)
  })

  return (
    <div className="auth-page">
      <form className="card" onSubmit={submit}>
        <h1>{t('forgot.title')}</h1>
        {outcome !== null ? (
          <p>{outcome === 'ask_guardian' ? t('forgot.askGuardian') : t('forgot.sent')}</p>
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
