/**
 * Gacha setup form (ADR-0060): it checks its own input in the app's language, and a miss may be
 * left unnamed.
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { GachaDesign } from '../services/gacha'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { GachaForm } from './GachaForm'

function renderForm() {
  const onSubmit = vi.fn<(design: GachaDesign) => Promise<void>>(() => Promise.resolve())
  renderWithProviders(<GachaForm onSubmit={onSubmit} />)
  return onSubmit
}

function type(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

describe('GachaForm', () => {
  it('an unnamed miss is saved as "Miss" instead of blocking the form', async () => {
    const onSubmit = renderForm()
    type('Name', 'Snack gacha')
    type('Points per draw', '10')
    type('Prize 1', 'Chocolate')
    fireEvent.click(screen.getByRole('button', { name: 'Add a prize' }))
    fireEvent.click(screen.getAllByLabelText('Miss')[1] as HTMLElement)

    fireEvent.click(screen.getByRole('button', { name: 'Make' }))

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        name: 'Snack gacha',
        price: 10,
        prizes: [
          { name: 'Chocolate', weight: 1, is_miss: false },
          { name: 'Miss', weight: 1, is_miss: true },
        ],
      })
    })
  })

  it('missing input is reported in the app language and the first bad field gets focus', async () => {
    const onSubmit = renderForm()
    type('Prize 1', 'Chocolate')

    fireEvent.click(screen.getByRole('button', { name: 'Make' }))

    expect(await screen.findByText('Enter a name.')).toBeInTheDocument()
    expect(screen.getByText('Enter a whole number of 1 or more.')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByLabelText('Name')).toHaveFocus()
    })
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('a prize that is not a miss still needs a name', async () => {
    const onSubmit = renderForm()
    type('Name', 'Snack gacha')
    type('Points per draw', '10')

    fireEvent.click(screen.getByRole('button', { name: 'Make' }))

    expect(
      await screen.findByText('Enter a prize name (a miss may stay empty).'),
    ).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
