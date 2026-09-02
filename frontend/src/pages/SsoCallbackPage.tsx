/**
 * IdP から戻ってきた直後の中継画面（ADR-0029）。
 *
 * URL に載っているのは 1 回限りの引き換え券だけで、トークンではない。ここで
 * トークンへ換え、SSO を始めた画面へ送る。券は 1 回しか使えないため、
 * 再描画（開発時の StrictMode を含む）で 2 回目を投げないようにする。
 *
 * 招待コードを持ったまま SSO へ回った人は、IdP の画面を挟んだぶん URL の断片を
 * 失っている。ログイン画面が預けたコードをここで拾い直す（ADR-0025）。
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
      navigate('/login?sso_error=sso_ticket_invalid', { replace: true })
      return
    }
    loginWithSsoTicket(ticket)
      .then((redirectTo) => {
        // 招待コードは IdP への往復で断片ごと消えている。預けたものを付け直す
        // （サーバーを通す ``redirect_to`` には載せられない。ADR-0025）
        const code = takeRememberedInvitationCode()
        // 履歴に残さない（「戻る」で使用済みの券へ戻らないようにする）
        navigate(code ? invitationAcceptPath(code) : redirectTo, { replace: true })
      })
      .catch((error: unknown) => {
        // 失敗もログイン画面で伝える（この画面は中継で、そのまま抜ける）
        const code = error instanceof ApiError ? error.code : 'sso_error'
        navigate(`/login?sso_error=${encodeURIComponent(code)}`, { replace: true })
      })
  }, [ticket, navigate, loginWithSsoTicket])

  return <p className="loading">{t('sso.signingIn')}</p>
}
