/**
 * Button that shows a spinner and cannot be pressed while running (ADR-0023).
 *
 * Operations that query the server do not change the screen until the result comes back. If users
 * cannot tell whether the press registered they press again, so always show a marker right away.
 *
 * Looks the same as a plain `<button>` (uses the `index.css` rules as is). The spinner is
 * overlaid on the label, and the label is hidden while keeping its space. If the button width changed
 * on press, neighbouring buttons would shift and cause mis-taps (see the `.action-button` rules).
 */
import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { useI18n } from '../i18n'

interface ActionButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Running. Shows a spinner and disables the button. */
  pending: boolean
  children: ReactNode
}

export function ActionButton({
  pending,
  disabled,
  className,
  children,
  ...buttonProps
}: ActionButtonProps) {
  const { t } = useI18n()

  return (
    <button
      {...buttonProps}
      className={className === undefined ? 'action-button' : `action-button ${className}`}
      disabled={pending || (disabled ?? false)}
      aria-busy={pending}
    >
      <span className="action-button-label">{children}</span>
      {pending && (
        <>
          <span className="spinner action-button-spinner" aria-hidden="true" />
          {/* The spinner is only visible to the eye, so provide separate text for screen readers. */}
          <span className="visually-hidden">{t('common.processing')}</span>
        </>
      )}
    </button>
  )
}
