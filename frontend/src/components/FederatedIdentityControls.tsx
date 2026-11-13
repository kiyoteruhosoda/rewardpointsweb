/**
 * Linking with the IdP (SSO). Shown in the "linking" section of the security screen (ADR-0036).
 *
 * Starting a link navigates the whole page to the IdP, and on return this screen has
 * `?sso_link=linked` or `?sso_link_error=<code>` attached.
 *
 * The heading and section frame belong to the caller (SecurityPage); this draws only the contents.
 */
import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { api, errorMessageKey } from '../services/api'
import { ActionButton } from './ActionButton'
import { useToast } from './ToastNotification'

interface FederatedLink {
  available: boolean
  display_name: string
  linked: boolean
  linked_at: string | null
  can_unlink: boolean
}

/** Error codes attached on link return -> text keys. */
const LINK_ERRORS: Record<string, string> = {
  sso_identity_taken: 'security.linkTaken',
  sso_already_linked: 'security.linkAlreadyLinked',
  sso_link_session_mismatch: 'security.linkSessionMismatch',
}

export function FederatedIdentityControls() {
  const { t, locale } = useI18n()
  const { notify } = useToast()
  const [link, setLink] = useState<FederatedLink | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [params, setParams] = useSearchParams()

  const reload = useCallback(
    () =>
      api
        .get<FederatedLink>('/api/auth/sso/link')
        .then(setLink)
        .catch(() => {
          setLink(null)
        }),
    [],
  )

  useEffect(() => {
    void reload()
  }, [reload])

  // Only once, right after returning from the IdP, report the result and clean up the query.
  // If left in place, the same message appears every time the page is reloaded.
  useEffect(() => {
    const linked = params.get('sso_link')
    const failed = params.get('sso_link_error')
    if (!linked && !failed) return
    if (linked) notify('success', t('security.linkDone'))
    if (failed) setError(LINK_ERRORS[failed] ?? 'security.linkFailed')
    params.delete('sso_link')
    params.delete('sso_link_error')
    setParams(params, { replace: true })
  }, [params, setParams, notify, t])

  const [startLink, starting] = usePendingAction(async () => {
    setError(null)
    try {
      const started = await api.post<{ authorization_url: string }>('/api/auth/sso/link/start')
      // ⚠ The server does not return 303. After receiving the round-trip state cookie,
      //   the screen navigates to the IdP itself (so an expired session can be received as 401).
      window.location.assign(started.authorization_url)
    } catch (err) {
      setError(errorMessageKey(err))
    }
  })

  const [removeLink, removing] = usePendingAction(async () => {
    setError(null)
    try {
      await api.delete('/api/auth/sso/link')
      await reload()
      notify('success', t('security.linkRemoved'))
    } catch (err) {
      setError(errorMessageKey(err))
    }
  })

  if (link === null) return <p className="loading">{t('common.loading')}</p>
  if (!link.available) return null

  return (
    <>
      {error && <p className="error">{t(error)}</p>}
      {link.linked ? (
        <>
          <p>
            {t('security.linkedTo', { provider: link.display_name })}
            {link.linked_at ? ` (${new Date(link.linked_at).toLocaleString(locale)})` : ''}
          </p>
          {link.can_unlink ? (
            <ActionButton type="button" pending={removing} onClick={removeLink}>
              {t('security.unlink')}
            </ActionButton>
          ) : (
            // ⚠ Unlinking would lock them out. Show a reason instead of a disabled button.
            <p className="hint">{t('security.lastEntrance')}</p>
          )}
        </>
      ) : (
        <>
          <p>{t('security.notLinked')}</p>
          <ActionButton type="button" pending={starting} onClick={startLink}>
            {t('security.link', { provider: link.display_name })}
          </ActionButton>
        </>
      )}
    </>
  )
}
