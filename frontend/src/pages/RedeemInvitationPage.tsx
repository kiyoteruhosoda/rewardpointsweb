/**
 * 招待コードでアカウントを作る画面（未認証で開く）。
 *
 * 子アカウントの入り口はここだけ。子ども自身では作れず、親が参加を用意して
 * 招待コードを渡した場合にのみ成立する（ADR-0011）。メールアドレスは尋ねない。
 */
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { PasswordField } from '../components/PasswordField'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families } from '../services/families'
import { useAuth } from '../store/AuthContext'

export function RedeemInvitationPage() {
  const { t } = useI18n()
  const { login } = useAuth()
  const navigate = useNavigate()
  const [code, setCode] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      const joined = await families.redeemInvitation(code, username, password)
      // 作った直後はまだログインしていない。設定したばかりの資格情報でそのまま入る
      await login(joined.username, password)
      navigate('/')
    } catch (err) {
      setError(errorMessageKey(err))
    }
  }

  return (
    <div className="auth-page">
      <form
        className="card"
        onSubmit={(event) => {
          void submit(event)
        }}
      >
        <h1>{t('join.title')}</h1>
        <p>{t('join.hint')}</p>
        {error && <p className="error">{t(error)}</p>}

        <label>
          {t('join.code')}
          <input
            value={code}
            onChange={(event) => {
              setCode(event.target.value)
            }}
            maxLength={64}
            required
          />
        </label>
        <label>
          {t('join.username')}
          <input
            autoComplete="username"
            value={username}
            onChange={(event) => {
              setUsername(event.target.value)
            }}
            minLength={3}
            maxLength={255}
            required
          />
        </label>
        {/* 長さの下限はサーバーと同じ。欠けると打ち込んだ直後に 422 で跳ね返る。 */}
        <PasswordField
          label={t('join.password')}
          autoComplete="new-password"
          value={password}
          onChange={setPassword}
          minLength={8}
          required
        />
        <button type="submit">{t('join.submit')}</button>
        <Link to="/login">{t('join.haveAccount')}</Link>
      </form>
    </div>
  )
}
