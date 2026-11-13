/**
 * Screen for creating an account with an invitation code (opened unauthenticated).
 *
 * This is the only entry for child accounts. Children cannot create one themselves; it works
 * only when a parent has prepared a membership and handed over the code (ADR-0011). No email asked.
 *
 * When opened from an invitation link, the code is in the URL fragment (`#code=...`)
 * (ADR-0025). It becomes the input's initial value so they can start without typing it.
 *
 * ⚠ **With SSO, parent invitations cannot be used here** (ADR-0048). An adult has only the one
 * account created on SSO sign-in. If refused, proceed to "sign in and join" below.
 *
 * People who already have an account cannot create one here (at most one family —
 * ADR-0013). Their path is to sign in and join from the family screen, so they are sent
 * to login carrying the entered invitation code. If the destination did not pick it up,
 * they would be "sent back to the original screen despite holding a code".
 */
import { useState, type SubmitEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { ActionButton } from '../components/ActionButton'
import { PasswordField } from '../components/PasswordField'
import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families } from '../services/families'
import { invitationSignInPath, readInvitationCode } from '../services/invitationLink'
import { useAuth } from '../store/AuthContext'

/** Maximum length of the in-family name (same as DisplayName MAX_LENGTH). */
const DISPLAY_NAME_MAX_LENGTH = 100

export function RedeemInvitationPage() {
  const { t } = useI18n()
  const { login } = useAuth()
  const navigate = useNavigate()
  const { hash } = useLocation()
  const [code, setCode] = useState(() => readInvitationCode(hash))
  const [displayName, setDisplayName] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  // Carry the typed code past login. Sending an empty one is pointless, so it is not attached.
  const signInPath = invitationSignInPath(code)

  const [submit, submitting] = usePendingAction(async (event: SubmitEvent) => {
    event.preventDefault()
    setError(null)
    try {
      const joined = await families.redeemInvitation(code, username, password, displayName)
      // Right after creation the user is not signed in yet. Sign in with the credentials just set
      await login(joined.username, password)
      void navigate('/')
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
        {/* The name given here is the account's display name (profile). The in-family name is
            held separately (ADR-0010), so if a parent prepared the membership it stays as the
            name the parent gave. The hint does not claim it is "the name shown to the family". */}
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
        {/* Minimum length matches the server. Without it, input bounces with 422 right after. */}
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
