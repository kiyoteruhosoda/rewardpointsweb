/**
 * Relay screen right after returning from the IdP (ADR-0029).
 *
 * The URL carries only a one-time exchange ticket, not a token. Here it is
 * exchanged for tokens and the user is sent to the screen where SSO started. The ticket works only once,
 * so re-renders (including StrictMode in development) must not send it a second time.
 *
 * Someone who went to SSO holding an invitation code lost the URL fragment while passing
 * through the IdP screens. Pick up the code that the login screen stashed (ADR-0025).
 */
import { useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { useI18n } from '../i18n'
import { ApiError } from '../services/api'
import { invitationAcceptPath, takeRememberedInvitationCode } from '../services/invitationLink'
import { useAuth } from '../store/AuthContext'

export function SsoCallbackPage() {
  const { t } = useI18n()
  const { loginWithSsoTicket } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const ticket = searchParams.get('ticket')
  const exchanged = useRef(false)

  useEffect(() => {
    if (exchanged.current) return
    exchanged.current = true

    if (!ticket) {
      void navigate('/login?sso_error=sso_ticket_invalid', { replace: true })
      return
    }
    loginWithSsoTicket(ticket)
      .then((redirectTo) => {
        // The invitation code was lost with the fragment on the IdP round trip. Reattach the stashed one
        // (it cannot ride on the server-side ``redirect_to``; ADR-0025)
        const code = takeRememberedInvitationCode()
        // Keep it out of history ("Back" must not return to the used ticket)
        void navigate(code ? invitationAcceptPath(code) : redirectTo, { replace: true })
      })
      .catch((error: unknown) => {
        // Failures are also reported on the login screen (this screen is only a relay and leaves right away)
        const code = error instanceof ApiError ? error.code : 'sso_error'
        void navigate(`/login?sso_error=${encodeURIComponent(code)}`, { replace: true })
      })
  }, [ticket, navigate, loginWithSsoTicket])

  return <p className="loading">{t('sso.signingIn')}</p>
}
