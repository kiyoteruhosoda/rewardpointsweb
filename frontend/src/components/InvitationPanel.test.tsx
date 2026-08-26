/**
 * 招待の発行。
 *
 * 見るのは「発行した直後に、コードを載せた URL を渡せる形で出すこと」。コードだけを
 * 出していた頃は、受け取った人がどの画面へ行きどこへ打ち込むかを別に教わる必要が
 * あった。URL は 1 度きりのコードと同じで発行の応答にしか現れないので、ここで出し
 * 損ねると発行し直すしかない。
 *
 * コピーできない出所（安全でない接続など）でも詰まらないことも併せて守る。
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
  // 本物と同じ判定にする。サーバは Z 付きで返すので、無条件に足すと `...ZZ` になる
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

/** 押した URL の写し先。安全でない出所では触れないので、テストでも都度置き換える。 */
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

  it('発行するとコードを載せた URL を出す', async () => {
    renderPanel()

    fireEvent.click(screen.getByRole('button', { name: /Invite another parent/ }))

    const expected = `${window.location.origin}/join#code=AB%2BCD`
    const link = await screen.findByRole('link', { name: expected })
    expect(link).toHaveAttribute('href', expected)
    // URL を開けない相手のために、コードそのものも併せて出す。
    expect(screen.getByText('AB+CD')).toBeInTheDocument()
  })

  it('コピーを押すと URL をクリップボードへ渡す', async () => {
    const writeText = vi.fn<(text: string) => Promise<void>>().mockResolvedValue(undefined)
    stubClipboard(writeText)
    renderPanel()

    fireEvent.click(screen.getByRole('button', { name: /Invite another parent/ }))
    fireEvent.click(await screen.findByRole('button', { name: /Copy the link/ }))

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/join#code=AB%2BCD`)
    })
    expect(await screen.findByText('The link was copied.')).toBeInTheDocument()
  })

  it('コピーできない出所では手で写すよう伝え、URL は出したままにする', async () => {
    stubClipboard(() => Promise.reject(new Error('not allowed')))
    renderPanel()

    fireEvent.click(screen.getByRole('button', { name: /Invite another parent/ }))
    fireEvent.click(await screen.findByRole('button', { name: /Copy the link/ }))

    expect(
      await screen.findByText('The link could not be copied. Select it and copy it by hand.'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: `${window.location.origin}/join#code=AB%2BCD` }),
    ).toBeInTheDocument()
  })
})
