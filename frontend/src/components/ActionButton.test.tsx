/**
 * Button while an action is running (ADR-0023).
 *
 * Checks three things: "after a press, a spinner shows and the button is disabled until it
 * finishes", "it returns to normal when done", and "pressing again while running does not run a
 * second time". The spinning look itself is CSS's job, so it is not checked here.
 *
 * Also guards that the label stays as an element while running (= the button width does not change).
 * Hiding it is CSS's job, but going back to an implementation that swaps the label would move the width.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { usePendingAction } from '../hooks/usePendingAction'
import { I18nProvider } from '../i18n'
import type { UiSettings } from '../services/uiSettings'
import { ActionButton } from './ActionButton'

const SETTINGS: UiSettings = {
  languages: ['en'],
  default_locale: 'en',
  default_theme: 'light',
}

/** Minimal screen combined with `usePendingAction`, the way it is actually used. */
function Subject({ action }: { action: () => Promise<void> }) {
  const [run, pending] = usePendingAction(action)
  return (
    <ActionButton type="button" pending={pending} onClick={run}>
      Save
    </ActionButton>
  )
}

function renderSubject(action: () => Promise<void>) {
  render(
    <I18nProvider settings={SETTINGS}>
      <Subject action={action} />
    </I18nProvider>,
  )
  return screen.getByRole('button', { name: /Save/ })
}

describe('ActionButton', () => {
  it('shows a spinner and disables while running, and returns to normal when done', async () => {
    let finish = (): void => undefined
    const action = () =>
      new Promise<void>((resolve) => {
        finish = resolve
      })
    const button = renderSubject(action)

    expect(button).not.toHaveAttribute('aria-busy', 'true')
    expect(screen.queryByText('Processing...')).not.toBeInTheDocument()

    fireEvent.click(button)

    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(button).toBeDisabled()
    expect(screen.getByText('Processing...')).toBeInTheDocument()
    // The label stays as a placeholder (swapping it would change the button width).
    expect(screen.getByText('Save')).toBeInTheDocument()

    finish()

    await waitFor(() => {
      expect(button).not.toBeDisabled()
    })
    expect(screen.queryByText('Processing...')).not.toBeInTheDocument()
  })

  it('does not run a second time when pressed again while running', async () => {
    let finish = (): void => undefined
    const action = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          finish = resolve
        }),
    )
    const button = renderSubject(action)

    fireEvent.click(button)
    // `disabled` waits for rendering, so check that presses in the same frame are also stopped.
    fireEvent.click(button)
    expect(action).toHaveBeenCalledTimes(1)

    finish()
    await waitFor(() => {
      expect(button).not.toBeDisabled()
    })

    fireEvent.click(button)
    expect(action).toHaveBeenCalledTimes(2)
  })
})
