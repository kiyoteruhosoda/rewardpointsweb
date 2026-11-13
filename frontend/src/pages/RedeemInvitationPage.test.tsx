/**
 * Account creation with an invitation code.
 *
 * Input min/max match the server schema. If missing, the mismatch is not noticed until
 * submission bounces with 422 (`InvitationRedeemRequest`).
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '../services/api'
import type { RedeemedInvitation } from '../services/families'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { RedeemInvitationPage } from './RedeemInvitationPage'

const redeemInvitation =
  vi.fn<
    (
      code: string,
      username: string,
      password: string,
      displayName: string,
    ) => Promise<RedeemedInvitation>
  >()

vi.mock('../services/families', () => ({
  families: {
    redeemInvitation: (code: string, username: string, password: string, displayName: string) =>
      redeemInvitation(code, username, password, displayName),
  },
}))

describe('RedeemInvitationPage', () => {
  it('password is at least 8 characters (same as the server min_length)', () => {
    renderWithProviders(<RedeemInvitationPage />)
    expect(screen.getByLabelText('Password')).toHaveAttribute('minlength', '8')
  })

  it('username is 3–255 characters (same as the Username value object)', () => {
    renderWithProviders(<RedeemInvitationPage />)
    const username = screen.getByLabelText('Username')
    expect(username).toHaveAttribute('minlength', '3')
    expect(username).toHaveAttribute('maxlength', '255')
  })

  it('invitation code is at most 64 characters (same as CodeStr)', () => {
    renderWithProviders(<RedeemInvitationPage />)
    expect(screen.getByLabelText('Invitation code')).toHaveAttribute('maxlength', '64')
  })

  it('name is at most 100 characters (same as DisplayName MAX_LENGTH)', () => {
    renderWithProviders(<RedeemInvitationPage />)
    expect(screen.getByLabelText('Name')).toHaveAttribute('maxlength', '100')
  })

  it('sends the entered name as is', async () => {
    redeemInvitation.mockReset()
    redeemInvitation.mockResolvedValue({
      family_id: 1,
      family_name: 'ほその家',
      membership_id: 2,
      role: 'child',
      username: 'taro',
    })
    renderWithProviders(<RedeemInvitationPage />)

    fireEvent.change(screen.getByLabelText('Invitation code'), { target: { value: 'CODE1234' } })
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'たろう' } })
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'taro' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create my account' }))

    await waitFor(() => {
      expect(redeemInvitation).toHaveBeenCalledWith('CODE1234', 'taro', 'password123', 'たろう')
    })
  })

  it('sends people who already have an account to login, carrying the entered code', () => {
    renderWithProviders(<RedeemInvitationPage />)

    fireEvent.change(screen.getByLabelText('Invitation code'), { target: { value: 'CODE 1234' } })

    expect(screen.getByRole('link', { name: 'Sign in and join' })).toHaveAttribute(
      'href',
      '/login#code=CODE%201234',
    )
  })

  it('when a parent invitation is refused, says to sign in and join (ADR-0048)', async () => {
    redeemInvitation.mockReset()
    redeemInvitation.mockRejectedValue(new ApiError(400, 'guardian_invitation_requires_sign_in'))
    renderWithProviders(<RedeemInvitationPage />, { route: '/join#code=CODE1234' })

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'はなこ' } })
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'hanako' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create my account' }))

    expect(
      await screen.findByText(
        'A parent invitation cannot create a new account here. Use "Sign in and join" below.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign in and join' })).toHaveAttribute(
      'href',
      '/login#code=CODE1234',
    )
  })

  it('does not attach the code to the login link when it is empty', () => {
    renderWithProviders(<RedeemInvitationPage />)

    expect(screen.getByRole('link', { name: 'Sign in and join' })).toHaveAttribute('href', '/login')
  })

  it('prefills the code passed in the URL (when coming back from login)', () => {
    renderWithProviders(<RedeemInvitationPage />, { route: '/join#code=CODE1234' })
    expect(screen.getByLabelText('Invitation code')).toHaveValue('CODE1234')
  })
})
