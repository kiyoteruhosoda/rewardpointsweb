/** 家族の一覧: 作成の入口の出し分け（親だけ）と、招待コードでの参加。 */
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

const PARENT_SCOPES = ['family:view', 'family:manage', 'point:view', 'point:manage']

describe('FamiliesPage', () => {
  beforeEach(() => {
    list.mockReset()
    create.mockReset()
    acceptInvitation.mockReset()
    list.mockResolvedValue([])
  })

  it('親（family:manage）には「作る」を出す', async () => {
    renderWithProviders(<FamiliesPage />, { scopes: PARENT_SCOPES })

    expect(await screen.findByRole('button', { name: 'Create a family' })).toBeInTheDocument()
  })

  it('子（family:view のみ）には「作る」を出さず、招待コードの入口だけ出す', async () => {
    renderWithProviders(<FamiliesPage />, { scopes: ['family:view', 'point:view'] })

    expect(await screen.findByRole('button', { name: 'Join with a code' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Create a family' })).not.toBeInTheDocument()
  })

  it('親が作るとそのまま一覧を更新する', async () => {
    create.mockResolvedValue({
      id: 1,
      name: 'ほその家',
      my_membership_id: 1,
      my_role: 'owner',
      memberships: [],
    })
    renderWithProviders(<FamiliesPage />, { scopes: PARENT_SCOPES })

    fireEvent.change(await screen.findByLabelText('Name'), { target: { value: 'ほその家' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create a family' }))

    expect(await screen.findByText('Saved.')).toBeInTheDocument()
    expect(create).toHaveBeenCalledWith('ほその家')
  })

  it('招待コードで参加できる', async () => {
    acceptInvitation.mockResolvedValue({
      family_id: 1,
      family_name: 'ほその家',
      membership_id: 2,
      role: 'parent',
      username: 'mom',
    })
    renderWithProviders(<FamiliesPage />, { scopes: PARENT_SCOPES })

    fireEvent.change(await screen.findByLabelText('Invitation code'), {
      target: { value: 'CODE1234' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Join with a code' }))

    expect(await screen.findByText('You joined the family.')).toBeInTheDocument()
  })
})
