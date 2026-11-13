/**
 * Record input: when submitted empty, the reason-required message appears regardless of which button.
 * Checked from both so that "spend" doesn't slip through back to a "nothing happens on press" state.
 */
import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { PointEntryForm } from './PointEntryForm'

vi.mock('../services/families', () => ({
  newIdempotencyKey: () => 'test-key',
}))

function setUp(): { onSubmit: ReturnType<typeof vi.fn> } {
  const onSubmit = vi.fn<() => Promise<void>>().mockResolvedValue()
  renderWithProviders(<PointEntryForm onSubmit={onSubmit} reasonSuggestions={[]} />)
  return { onSubmit }
}

function typeInto(label: string, value: string): void {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

function press(name: string): void {
  fireEvent.click(screen.getByRole('button', { name }))
}

function reasonField(): HTMLInputElement {
  return screen.getByLabelText('Reason')
}

describe('PointEntryForm', () => {
  it('does not send an add with an empty reason and shows the required message', () => {
    const { onSubmit } = setUp()

    typeInto('Points', '50')
    press('Add points')

    expect(onSubmit).not.toHaveBeenCalled()
    expect(reasonField().validationMessage).toBe('Enter a reason.')
  })

  it('does not send a spend with an empty reason either (does not silently drop it)', () => {
    const { onSubmit } = setUp()

    typeInto('Points', '50')
    press('Use points')

    expect(onSubmit).not.toHaveBeenCalled()
    expect(reasonField().validationMessage).toBe('Enter a reason.')
  })

  it('treats a whitespace-only reason as empty', () => {
    const { onSubmit } = setUp()

    typeInto('Points', '50')
    typeInto('Reason', '   ')
    press('Add points')

    expect(onSubmit).not.toHaveBeenCalled()
    expect(reasonField().validationMessage).toBe('Enter a reason.')
  })

  it('sends when filled in; the sign is decided by the pressed button', () => {
    const { onSubmit } = setUp()

    typeInto('Points', '50')
    typeInto('Reason', 'おてつだい')
    press('Use points')

    expect(onSubmit).toHaveBeenCalledWith(-50, 'おてつだい', 'test-key')
    expect(reasonField().validationMessage).toBe('')
  })
})
