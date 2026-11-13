import { useEffect, useState, type SubmitEvent } from 'react'
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
import { REDIRECT_TO_PARAM, sanitizeRedirectTo } from '../services/returnTo'
import { markSilentSsoTried, maySilentSso } from '../services/silentSso'
import { fetchSsoProvider, startSsoLogin, type SsoProvider } from '../services/sso'
import { isPasskeySupported, passkeyErrorKey } from '../services/webauthn'
import { RECONNECT_INTERVAL_MS, useAuth } from '../store/AuthContext'

/** Credentials input -> (if two-factor auth is enabled) one-time code input. */
type Step = 'credentials' | 'totp'

export function LoginPage() {
  const { t } = useI18n()
  const { login, loginWithPasskey } = useAuth()
  const navigate = useNavigate()
  // People may arrive here holding an invitation code (sent from the account creation screen,
  // or directly from an invitation link). The code travels in the URL fragment (ADR-0025).
  // After login, go to the screen for joining the family with that code, not the default.
  // Without a code, return to the screen they were trying to open (`?redirect_to=`, ADR-0051).
  const { hash } = useLocation()
  const [searchParams] = useSearchParams()
  const pendingCode = readInvitationCode(hash)
  const returnTo = sanitizeRedirectTo(searchParams.get(REDIRECT_TO_PARAM))
  const destination = pendingCode ? invitationAcceptPath(pendingCode) : returnTo
  // The SSO return path goes through the server, so pass only a path without the code
  const ssoDestination = pendingCode ? '/families' : returnTo
  // Do not drop the code when navigating back and forth (dropping it means retyping)
  const joinPath = invitationJoinPath(pendingCode)
  const [step, setStep] = useState<Step>('credentials')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [sso, setSso] = useState<SsoProvider | null>(null)
  const [ssoUnreachable, setSsoUnreachable] = useState(false)
  // If signed in at the IdP, enter without a tap (ADR-0052). The opening URL decides whether to try
  // Skip it when holding an invitation code (the destination is the join screen; let them choose).
  // ⚠ **Once it decides to try, do not render the entry.** Rendering first flashes the login page.
  const [silentAllowed] = useState(() => !pendingCode && maySilentSso(searchParams))
  // SSO failures come back via navigation, so they are in the URL rather than a response body
  const ssoError = searchParams.get('sso_error')

  // The query fails when the server is unreachable (e.g. during a release). ⚠ **Do not give up
  // after one try** — giving up strands the user without the SSO button after the server is back.
  // Say it is unreachable and retry until connected (ADR-0046). Keep the password field (main entry)
  useEffect(() => {
    let timer: number | undefined
    let cancelled = false
    const ask = () => {
      fetchSsoProvider()
        .then((provider) => {
          if (cancelled) return
          if (provider.enabled && silentAllowed && markSilentSsoTried()) {
            startSsoLogin(returnTo, { silent: true })
            return
          }
          setSso(provider)
          setSsoUnreachable(false)
        })
        .catch(() => {
          if (cancelled) return
          setSsoUnreachable(true)
          timer = window.setTimeout(ask, RECONNECT_INTERVAL_MS)
        })
    }
    ask()
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [returnTo, silentAllowed])

  const [submit, submitting] = usePendingAction(async (e: SubmitEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await login(username, password, step === 'totp' ? totpCode : undefined)
      void navigate(destination)
    } catch (err) {
      const code = err instanceof ApiError ? err.code : 'unknown_error'
      if (code === 'totp_required') {
        // A code request is not an error but the next step. Move on to code input as guidance.
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
      void navigate(destination)
    } catch (err) {
      setError(passkeyErrorKey(err) ?? errorMessageKey(err))
    }
  })

  const backToCredentials = () => {
    setStep('credentials')
    setTotpCode('')
    setError(null)
  }

  // Do not render the entry until deciding whether to try (ADR-0052). Rendering, then going to the
  // IdP flashes the password field. Once known unreachable (ssoUnreachable), show the usual entry.
  if (silentAllowed && sso === null && !ssoUnreachable) {
    return (
      <div className="auth-page">
        <p className="card loading">{t('common.loading')}</p>
      </div>
    )
  }

  return (
    <div className="auth-page">
      <form className="card" onSubmit={submit}>
        <h1>{step === 'totp' ? t('login.totpTitle') : t('login.title')}</h1>
        {pendingCode && <p className="notice">{t('login.invitationPending')}</p>}
        {/* A passkey misconfiguration is shown with the currently open domain ({domain}). */}
        {error && <p className="error">{t(error, { domain: window.location.hostname })}</p>}
        {ssoUnreachable && (
          <p className="notice">
            <span className="spinner" aria-hidden="true" /> {t('common.unreachable')}
          </p>
        )}
        {/* A failure returned from the IdP. Unknown codes fall back to a generic message */}
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
                  // The return path stays on the server; the invitation code is kept in this tab
                  // (once a fragment moves into the query it stays in logs in plain text. ADR-0025)
                  rememberInvitationCode(pendingCode)
                  startSsoLogin(ssoDestination)
                }}
              >
                {t('login.withSso', { provider: sso.display_name })}
              </button>
            )}
            <Link to="/forgot-password">{t('login.forgot')}</Link>
            <Link to={joinPath}>{t('login.withInvitation')}</Link>
            {/* Entry for using this as a display (signage); home-screen web apps cannot type URLs (ADR-0047) */}
            <Link to="/display">{t('login.useAsDisplay')}</Link>
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
