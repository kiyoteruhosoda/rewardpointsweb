/** 家族の一覧: 作成の入口の出し分けと、保護者へ昇格したときの再ログイン誘導。 */
import { fireEvent, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FamilyDetail, FamilySummary, RedeemedInvitation } from '../services/families'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { FamiliesPage } from './FamiliesPage'

const list = vi.fn<() => Promise<FamilySummary[]>>()
const create = vi.fn<(name: string) => Promise<FamilyDetail>>()
const acceptInvitation = vi.fn<(code: string) => Promise<RedeemedInvitation>>()

vi.mock('../services/families', () => ({
  families: {
    list: () => list(),
    create: (name: string) => create(name),
    acceptInvitation: (code: string) => acceptInvitation(code),
  },
}))

function created(): FamilyDetail {
  return { id: 1, name: 'しんじんの家', my_membership_id: 1, my_role: 'owner', memberships: [] }
}

describe('FamiliesPage', () => {
  beforeEach(() => {
    list.mockReset()
    create.mockReset()
    acceptInvitation.mockReset()
    list.mockResolvedValue([])
  })

  it('family:view しか持たない member にも「作る」を出す', async () => {
    renderWithProviders(<FamiliesPage />, { scopes: ['family:view'] })

    expect(await screen.findByRole('button', { name: 'Create a family' })).toBeInTheDocument()
  })

  it('member が作ると owner へ昇格するので、再ログインを促す', async () => {
    create.mockResolvedValue(created())
    const logout = vi.fn()
    renderWithProviders(<FamiliesPage />, { scopes: ['family:view'], logout })

    fireEvent.change(await screen.findByLabelText('Name'), { target: { value: 'しんじんの家' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create a family' }))

    expect(await screen.findByText(/sign in again/)).toBeInTheDocument()
    expect(logout).toHaveBeenCalled()
  })

  it('family:manage を持つ人が作っても、そのまま使い続けられる', async () => {
    create.mockResolvedValue(created())
    const logout = vi.fn()
    renderWithProviders(<FamiliesPage />, { scopes: ['family:view', 'family:manage'], logout })

    fireEvent.change(await screen.findByLabelText('Name'), { target: { value: 'ほその家' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create a family' }))

    expect(await screen.findByText('Saved.')).toBeInTheDocument()
    expect(logout).not.toHaveBeenCalled()
  })

  it('親として招待を受けたときも再ログインを促す', async () => {
    acceptInvitation.mockResolvedValue({
      family_id: 1,
      family_name: 'ほその家',
      membership_id: 2,
      role: 'parent',
      username: 'aunt',
    })
    const logout = vi.fn()
    renderWithProviders(<FamiliesPage />, { scopes: ['family:view'], logout })

    fireEvent.change(await screen.findByLabelText('Invitation code'), {
      target: { value: 'CODE1234' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Join with a code' }))

    expect(await screen.findByText(/sign in again/)).toBeInTheDocument()
    expect(logout).toHaveBeenCalled()
  })
})
