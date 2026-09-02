import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'

import { ActionButton } from '../components/ActionButton'
import { PasswordField } from '../components/PasswordField'
import { usePendingAction } from '../hooks/usePendingAction'
import { knownMessageKey, useI18n } from '../i18n'
import { ApiError, errorMessageKey } from '../services/api'
import {
  invitationAcceptPath,
  invitationJoinPath,
  readInvitationCode,
  rememberInvitationCode,
} from '../services/invitationLink'
import { fetchSsoProvider, startSsoLogin, type SsoProvider } from '../services/sso'
import { isPasskeySupported, passkeyErrorKey } from '../services/webauthn'
import { useAuth } from '../store/AuthContext'

/** 資格情報の入力 → （二要素認証が有効なら）ワンタイムコードの入力。 */
type Step = 'credentials' | 'totp'

export function LoginPage() {
  const { t } = useI18n()
  const { login, loginWithPasskey } = useAuth()
  const navigate = useNavigate()
  // 招待コードを持ったままここへ来ることがある（アカウント作成の画面から回された
  // 場合、または招待リンクから直接）。コードは URL の断片で運ばれる（ADR-0025）。
  // ログイン後は既定の行き先ではなく、そのコードで参加できる家族の画面へ送る。
  const { hash } = useLocation()
  const pendingCode = readInvitationCode(hash)
  const destination = pendingCode ? invitationAcceptPath(pendingCode) : '/'
  // SSO の戻り先はサーバーを経由するので、コードを含まない経路だけを渡す
  const ssoDestination = pendingCode ? '/families' : '/'
  // 行き来してもコードを落とさない（ここで落とすと打ち直しになる）
  const joinPath = invitationJoinPath(pendingCode)
  const [step, setStep] = useState<Step>('credentials')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [sso, setSso] = useState<SsoProvider | null>(null)
  // SSO の失敗は画面遷移で戻ってくるため、応答本文ではなく URL に載る
  const [searchParams] = useSearchParams()
  const ssoError = searchParams.get('sso_error')

  useEffect(() => {
    void fetchSsoProvider()
      .then(setSso)
      .catch(() => {
        // 問い合わせに失敗したらボタンを出さない。SSO が使えるかどうかは
        // ログインの前提ではないので、ここでは何も伝えない
        setSso(null)
      })
  }, [])

  const [submit, submitting] = usePendingAction(async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await login(username, password, step === 'totp' ? totpCode : undefined)
      navigate(destination)
    } catch (err) {
      const code = err instanceof ApiError ? err.code : 'unknown_error'
      if (code === 'totp_required') {
        // コード要求はエラーではなく次の手順。案内としてコード入力へ進める。
        setStep('totp')
        setTotpCode('')
        setError(null)
        return
      }
      if (code === 'invalid_totp') setTotpCode('')
      setError(errorMessageKey(err))
    }
  })

  const [signInWithPasskey, passkeyPending] = usePendingAction(async () => {
    setError(null)
    try {
      await loginWithPasskey()
      navigate(destination)
    } catch (err) {
      setError(passkeyErrorKey(err) ?? errorMessageKey(err))
    }
  })

  const backToCredentials = () => {
    setStep('credentials')
    setTotpCode('')
    setError(null)
  }

  return (
    <div className="auth-page">
      <form className="card" onSubmit={submit}>
        <h1>{step === 'totp' ? t('login.totpTitle') : t('login.title')}</h1>
        {pendingCode && <p className="notice">{t('login.invitationPending')}</p>}
        {/* パスキーの設定違いは、いま開いているドメインを添えて出す（{domain}）。 */}
        {error && <p className="error">{t(error, { domain: window.location.hostname })}</p>}
        {/* IdP から戻された失敗。知らないコードは一般的な文言へ倒す */}
        {!error && ssoError !== null && (
          <p className="error">{t(knownMessageKey(`error.${ssoError}`, 'error.sso_error'))}</p>
        )}

        {step === 'credentials' ? (
          <>
            <label>
              {t('login.username')}
              <input
                type="text"
                autoComplete="username webauthn"
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value)
                }}
                required
              />
            </label>
            <PasswordField
              label={t('login.password')}
              autoComplete="current-password"
              value={password}
              onChange={setPassword}
              required
            />
            <ActionButton type="submit" pending={submitting}>
              {t('login.submit')}
            </ActionButton>
            {isPasskeySupported() && (
              <ActionButton type="button" pending={passkeyPending} onClick={signInWithPasskey}>
                {t('login.withPasskey')}
              </ActionButton>
            )}
            {sso?.enabled === true && (
              <button
                type="button"
                onClick={() => {
                  // 戻り先はサーバーに残る。招待コードは載せず、同じタブへ預ける
                  // （断片はクエリへ移した時点でログに平文で残る。ADR-0025）
                  rememberInvitationCode(pendingCode)
                  startSsoLogin(ssoDestination)
                }}
              >
                {t('login.withSso', { provider: sso.display_name })}
              </button>
            )}
            <Link to="/forgot-password">{t('login.forgot')}</Link>
            <Link to={joinPath}>{t('login.withInvitation')}</Link>
          </>
        ) : (
          <>
            <p>{t('login.totpHint')}</p>
            <label>
              {t('login.totpCode')}
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]*"
                value={totpCode}
                onChange={(e) => {
                  setTotpCode(e.target.value)
                }}
                autoFocus
                required
              />
            </label>
            <ActionButton type="submit" pending={submitting}>
              {t('login.submit')}
            </ActionButton>
            <button type="button" onClick={backToCredentials}>
              {t('common.back')}
            </button>
          </>
        )}
      </form>
    </div>
  )
}
