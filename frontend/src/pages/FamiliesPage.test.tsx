/**
 * 家族への入口: すでに所属していれば詳細へ送り、していなければ作成・参加だけを出す。
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FamilyDetail, RedeemedInvitation } from '../services/families'
import { familyOf, member } from '../test-support/familyFixtures'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { FamiliesPage } from './FamiliesPage'

const create = vi.fn<(name: string) => Promise<FamilyDetail>>()
const acceptInvitation = vi.fn<(code: string) => Promise<RedeemedInvitation>>()

vi.mock('../services/families', () => ({
  families: {
    create: (name: string) => create(name),
    acceptInvitation: (code: string) => acceptInvitation(code),
  },
}))

const PARENT_SCOPES = ['family:view', 'family:manage', 'point:view', 'point:manage']

describe('FamiliesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('親（family:manage）には「作る」を出す', () => {
    renderWithProviders(<FamiliesPage />, { scopes: PARENT_SCOPES })

    expect(screen.getByRole('button', { name: 'Create a family' })).toBeInTheDocument()
  })

  it('子（family:view のみ）には「作る」を出さず、招待コードの入口だけ出す', () => {
    renderWithProviders(<FamiliesPage />, { scopes: ['family:view', 'point:view'] })

    expect(screen.getByRole('button', { name: 'Join with a code' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Create a family' })).not.toBeInTheDocument()
  })

  it('すでに家族に参加していれば、作成も参加も出さずに詳細へ送る', () => {
    renderWithProviders(<FamiliesPage />, {
      scopes: PARENT_SCOPES,
      family: familyOf('parent', [member()]),
      path: '/families',
      route: '/families',
    })

    expect(screen.queryByRole('button', { name: 'Create a family' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Join with a code' })).not.toBeInTheDocument()
  })

  it('作ったらその家族の詳細へ移る', async () => {
    create.mockResolvedValue(familyOf('owner', []))
    const reloadFamily = vi.fn<() => Promise<void>>().mockResolvedValue()
    renderWithProviders(<FamiliesPage />, { scopes: PARENT_SCOPES, reloadFamily })

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'ほその家' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create a family' }))

    await waitFor(() => {
      expect(create).toHaveBeenCalledWith('ほその家')
    })
    // 詳細へ送る前に読み直す（左のナビゲーションも同時に新しい家族へ変わる）
    await waitFor(() => {
      expect(reloadFamily).toHaveBeenCalled()
    })
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

    fireEvent.change(screen.getByLabelText('Invitation code'), { target: { value: 'CODE1234' } })
    fireEvent.click(screen.getByRole('button', { name: 'Join with a code' }))

    expect(await screen.findByText('You joined the family.')).toBeInTheDocument()
  })
})
