/**
 * 招待コードでアカウントを作る画面（未認証で開く）。
 *
 * 子アカウントの入り口はここだけ。子ども自身では作れず、親が参加を用意して
 * 招待コードを渡した場合にのみ成立する（ADR-0011）。メールアドレスは尋ねない。
 *
 * すでにアカウントを持つ人はここでは作れない（所属できる家族は 1 つまで —
 * ADR-0013）。その場合はログインしてから家族の画面で参加する経路になるため、
 * 入力済みの招待コードを `?code=` で持たせてログインへ送る。行き先で拾えないと
 * 「コードを持っているのに元の画面へ戻される」動線になる。
 */
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { ActionButton } from '../components/ActionButton'
import { PasswordField } from '../components/PasswordField'
import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families } from '../services/families'
import { useAuth } from '../store/AuthContext'

/** 家族の中での呼び名の上限（DisplayName の MAX_LENGTH と同じ）。 */
const DISPLAY_NAME_MAX_LENGTH = 100

export function RedeemInvitationPage() {
  const { t } = useI18n()
  const { login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [code, setCode] = useState(() => searchParams.get('code') ?? '')
  const [displayName, setDisplayName] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  // 打ち込んだコードはログインの先まで運ぶ。空のまま送っても意味がないので付けない。
  const signInPath = code.trim() ? `/login?code=${encodeURIComponent(code.trim())}` : '/login'

  const [submit, submitting] = usePendingAction(async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      const joined = await families.redeemInvitation(code, username, password, displayName)
      // 作った直後はまだログインしていない。設定したばかりの資格情報でそのまま入る
      await login(joined.username, password)
      navigate('/')
    } catch (err) {
      setError(errorMessageKey(err))
    }
  })

  return (
    <div className="auth-page">
      <form className="card" onSubmit={submit}>
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
        {/* ここで名乗る名前はアカウントの表示名（プロフィール）。家族の中での呼び名は
            別に持つ（ADR-0010）ので、親が参加を用意していた場合は親が付けた呼び名の
            ままになる。案内でも「家族に出る名前」とは言い切らない。 */}
        <label>
          {t('join.displayName')}
          <input
            autoComplete="nickname"
            value={displayName}
            onChange={(event) => {
              setDisplayName(event.target.value)
            }}
            maxLength={DISPLAY_NAME_MAX_LENGTH}
            required
          />
        </label>
        <p className="field-hint">{t('join.displayNameHint')}</p>
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
        <ActionButton type="submit" pending={submitting}>
          {t('join.submit')}
        </ActionButton>

        <div className="card-inset">
          <h2>{t('join.haveAccountTitle')}</h2>
          <p>{t('join.haveAccountHint')}</p>
          <Link to={signInPath}>{t('join.haveAccount')}</Link>
        </div>
      </form>
    </div>
  )
}
