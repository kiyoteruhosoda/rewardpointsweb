/**
 * Password input. Has a toggle to temporarily reveal the masked content.
 *
 * The downside of masking is that typos go unnoticed, so an eye button sits at the right edge of the
 * input and toggles show/hide "on each press" rather than while held (no need to keep holding on a
 * one-handed device). The visible state lives only inside this component and always returns to
 * masked when leaving the screen.
 *
 * The caption is passed either as `label` (stacked forms) or `placeholder` (inline forms).
 * The button sits outside the `<label>`; inside it, pressing would make the input react.
 */
import { useId, useState } from 'react'

import { useI18n } from '../i18n'

interface Props {
  /** Caption shown above the input. Inline forms use `placeholder` instead. */
  label?: string
  /** Alternative text when no caption can be placed. */
  placeholder?: string
  value: string
  onChange: (value: string) => void
  /** Tells the browser / password managers the purpose (`current-password` etc.). */
  autoComplete?: string
  minLength?: number
  required?: boolean
}

/** The eye shape. A slash is overlaid while masked. */
function EyeIcon({ crossed }: { crossed: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M1.8 12S5.6 5.8 12 5.8 22.2 12 22.2 12 18.4 18.2 12 18.2 1.8 12 1.8 12Z" />
      <circle cx="12" cy="12" r="3.1" />
      {crossed && <path d="M4 20 20 4" />}
    </svg>
  )
}

export function PasswordField({
  label,
  placeholder,
  value,
  onChange,
  autoComplete,
  minLength,
  required,
}: Props) {
  const { t } = useI18n()
  const [visible, setVisible] = useState(false)
  const [previous, setPrevious] = useState(value)
  const id = useId()

  // A screen that submitted successfully clears the input (the component stays mounted). If left
  // visible, the next password typed would be visible from the start, so re-mask once the value becomes empty.
  // Look only at "the moment it became empty". Checking whether it is empty would make it impossible
  // to switch to visible first on an untouched input.
  if (previous !== value) {
    setPrevious(value)
    if (value === '') setVisible(false)
  }

  return (
    <div className="password-field">
      {label !== undefined && <label htmlFor={id}>{label}</label>}
      <div className="password-field-control">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(e) => {
            onChange(e.target.value)
          }}
          placeholder={placeholder}
          autoComplete={autoComplete}
          minLength={minLength}
          required={required}
        />
        <button
          type="button"
          className="password-field-toggle"
          /* Announce what pressing will do, not the result of pressing. */
          aria-label={visible ? t('common.hidePassword') : t('common.showPassword')}
          aria-controls={id}
          onClick={() => {
            setVisible((prev) => !prev)
          }}
        >
          <EyeIcon crossed={visible} />
        </button>
      </div>
    </div>
  )
}
