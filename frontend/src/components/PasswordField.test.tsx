/** Password input: toggling the mask, and linking the caption to the input. */
import { fireEvent, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { PasswordField } from './PasswordField'

const SHOW_LABEL = 'Show password'
const HIDE_LABEL = 'Hide password'

/** An input with a caption can be found with `getByLabelText` (same even when type changes). */
function field(): HTMLInputElement {
  return screen.getByLabelText('Password')
}

/** Real usage where the parent holds the value. "clear" corresponds to cleanup after a successful submit. */
function Controlled({ initial }: { initial: string }) {
  const [value, setValue] = useState(initial)
  return (
    <>
      <PasswordField label="Password" value={value} onChange={setValue} />
      <button
        type="button"
        onClick={() => {
          setValue('')
        }}
      >
        clear
      </button>
    </>
  )
}

describe('PasswordField', () => {
  it('starts masked', () => {
    renderWithProviders(<PasswordField label="Password" value="s3cret" onChange={vi.fn()} />)

    expect(field()).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: SHOW_LABEL })).toBeInTheDocument()
  })

  it('reveals on press and masks again on a second press', () => {
    renderWithProviders(<PasswordField label="Password" value="s3cret" onChange={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: SHOW_LABEL }))
    expect(field()).toHaveAttribute('type', 'text')

    fireEvent.click(screen.getByRole('button', { name: HIDE_LABEL }))
    expect(field()).toHaveAttribute('type', 'password')
  })

  it('the toggle button does not submit the form (type=button)', () => {
    const onSubmit = vi.fn()
    renderWithProviders(
      <form onSubmit={onSubmit}>
        <PasswordField label="Password" value="" onChange={vi.fn()} />
      </form>,
    )

    fireEvent.click(screen.getByRole('button', { name: SHOW_LABEL }))
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('passes typed characters to the parent', () => {
    const onChange = vi.fn()
    renderWithProviders(<PasswordField label="Password" value="" onChange={onChange} />)

    fireEvent.change(field(), { target: { value: 'typed' } })
    expect(onChange).toHaveBeenCalledWith('typed')
  })

  it('is readable via placeholder instead of a caption (inline form)', () => {
    renderWithProviders(<PasswordField placeholder="Password" value="" onChange={vi.fn()} />)

    expect(screen.getByPlaceholderText('Password')).toHaveAttribute('type', 'password')
  })

  it("uses a separate id per input (captions don't mix with two on the same screen)", () => {
    renderWithProviders(
      <>
        <PasswordField label="Current password" value="" onChange={vi.fn()} />
        <PasswordField label="New password" value="" onChange={vi.fn()} />
      </>,
    )

    const current = screen.getByLabelText('Current password')
    const next = screen.getByLabelText('New password')
    expect(current.id).not.toBe(next.id)
  })

  it('keeps its own input masked when the neighbouring one is revealed', () => {
    renderWithProviders(
      <>
        <PasswordField label="Current password" value="" onChange={vi.fn()} />
        <PasswordField label="New password" value="" onChange={vi.fn()} />
      </>,
    )

    const [first] = screen.getAllByRole('button', { name: SHOW_LABEL })
    fireEvent.click(first as HTMLElement)

    expect(screen.getByLabelText('Current password')).toHaveAttribute('type', 'text')
    expect(screen.getByLabelText('New password')).toHaveAttribute('type', 'password')
  })

  it('re-masks when the parent clears the value (the next input does not stay visible after submit)', () => {
    renderWithProviders(<Controlled initial="s3cret" />)
    fireEvent.click(screen.getByRole('button', { name: SHOW_LABEL }))
    expect(field()).toHaveAttribute('type', 'text')

    // Behaviour of a screen after a successful submit. The component stays mounted; only the value is cleared.
    fireEvent.click(screen.getByRole('button', { name: 'clear' }))
    expect(field()).toHaveAttribute('type', 'password')

    // Characters typed next stay masked too
    fireEvent.change(field(), { target: { value: 'next' } })
    expect(field()).toHaveAttribute('type', 'password')
  })

  it('can switch to visible first on an input with nothing typed', () => {
    renderWithProviders(<Controlled initial="" />)

    fireEvent.click(screen.getByRole('button', { name: SHOW_LABEL }))
    expect(field()).toHaveAttribute('type', 'text')

    // Stays visible after typing starts (not re-masked just because it was empty)
    fireEvent.change(field(), { target: { value: 's' } })
    expect(field()).toHaveAttribute('type', 'text')
  })

  it('re-masks when the screen is rebuilt (visibility is not carried over)', () => {
    function Toggleable() {
      const [mounted, setMounted] = useState(true)
      return (
        <>
          <button
            type="button"
            onClick={() => {
              setMounted((prev) => !prev)
            }}
          >
            remount
          </button>
          {mounted && <PasswordField label="Password" value="" onChange={vi.fn()} />}
        </>
      )
    }

    renderWithProviders(<Toggleable />)
    fireEvent.click(screen.getByRole('button', { name: SHOW_LABEL }))
    expect(field()).toHaveAttribute('type', 'text')

    fireEvent.click(screen.getByRole('button', { name: 'remount' }))
    fireEvent.click(screen.getByRole('button', { name: 'remount' }))
    expect(field()).toHaveAttribute('type', 'password')
  })
})
