/**
 * Issuing invitations.
 *
 * What we check: "right after issuing, the URL containing the code is shown in a shareable form".
 * Back when only the code was shown, recipients had to be told separately which screen to go to and
 * where to type it. The URL, like the one-time code, appears only in the issue response, so if it
 * is not shown here the only option is to issue again.
 *
 * Also guards that it does not get stuck on origins that cannot copy (insecure connections etc.).
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FamilyRole, Invitation, Membership } from '../services/families'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { InvitationPanel } from './InvitationPanel'

const listInvitations = vi.fn<() => Promise<Invitation[]>>()
const issueInvitation =
  vi.fn<(familyId: number, role: FamilyRole, target: number | null) => Promise<Invitation>>()

vi.mock('../services/families', () => ({
  // Same check as the real thing. The server returns times with Z, so appending unconditionally gives `...ZZ`
  parseUtc: (value: string) =>
    new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`),
  families: {
    listInvitations: () => listInvitations(),
    issueInvitation: (familyId: number, role: FamilyRole, target: number | null) =>
      issueInvitation(familyId, role, target),
  },
}))

const ISSUED: Invitation = {
  id: 7,
  role: 'parent',
  target_membership_id: null,
  target_display_name: null,
  expires_at: '2026-08-10T00:00:00',
  code: 'AB+CD',
}

function renderPanel(unlinkedMembers: Membership[] = []) {
  return renderWithProviders(
    <InvitationPanel
      familyId={1}
      unlinkedMembers={unlinkedMembers}
      canInviteParent
      onChanged={() => Promise.resolve()}
    />,
  )
}

/** Where the pressed URL is copied to. Not accessible on insecure origins, so tests replace it each time. */
function stubClipboard(writeText: (text: string) => Promise<void>) {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText },
    configurable: true,
  })
}

describe('InvitationPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listInvitations.mockResolvedValue([])
    issueInvitation.mockResolvedValue(ISSUED)
  })

  it('issuing shows the URL with the code (a parent invite goes to the login screen; ADR-0048)', async () => {
    renderPanel()

    fireEvent.click(screen.getByRole('button', { name: /Invite another parent/ }))

    const expected = `${window.location.origin}/login#code=AB%2BCD`
    const link = await screen.findByRole('link', { name: expected })
    expect(link).toHaveAttribute('href', expected)
    // Also show the code itself for recipients who cannot open the URL.
    expect(screen.getByText('AB+CD')).toBeInTheDocument()
  })

  it('pressing copy passes the URL to the clipboard', async () => {
    const writeText = vi.fn<(text: string) => Promise<void>>().mockResolvedValue(undefined)
    stubClipboard(writeText)
    renderPanel()

    fireEvent.click(screen.getByRole('button', { name: /Invite another parent/ }))
    fireEvent.click(await screen.findByRole('button', { name: /Copy the link/ }))

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/login#code=AB%2BCD`)
    })
    expect(await screen.findByText('The link was copied.')).toBeInTheDocument()
  })

  it('on origins that cannot copy, says to copy by hand and keeps the URL shown', async () => {
    stubClipboard(() => Promise.reject(new Error('not allowed')))
    renderPanel()

    fireEvent.click(screen.getByRole('button', { name: /Invite another parent/ }))
    fireEvent.click(await screen.findByRole('button', { name: /Copy the link/ }))

    expect(
      await screen.findByText('The link could not be copied. Select it and copy it by hand.'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: `${window.location.origin}/login#code=AB%2BCD` }),
    ).toBeInTheDocument()
  })
})
