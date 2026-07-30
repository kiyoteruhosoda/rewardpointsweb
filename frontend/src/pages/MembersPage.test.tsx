/** メンバー一覧: scope による操作の出し分けと、残高の表示。 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { MemberSummary } from '../services/rewardPoints'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { MembersPage } from './MembersPage'

const listMembers = vi.fn<() => Promise<MemberSummary[]>>()
const createMember = vi.fn<(name: string, email: string | null) => Promise<unknown>>()
const deleteMember = vi.fn<(memberId: number) => Promise<void>>()

vi.mock('../services/rewardPoints', () => ({
  rewardPoints: {
    listMembers: () => listMembers(),
    createMember: (name: string, email: string | null) => createMember(name, email),
    deleteMember: (memberId: number) => deleteMember(memberId),
  },
}))

function member(overrides: Partial<MemberSummary> = {}): MemberSummary {
  return {
    id: 1,
    name: 'ハナ',
    balance: 70,
    access_level: 'manage',
    is_self: false,
    is_owner: true,
    has_linked_user: false,
    ...overrides,
  }
}

const MANAGER_SCOPES = ['member:view', 'member:manage']

describe('MembersPage', () => {
  beforeEach(() => {
    listMembers.mockReset()
    createMember.mockReset()
    deleteMember.mockReset()
    listMembers.mockResolvedValue([member()])
  })

  it('残高つきでメンバーを並べる', async () => {
    renderWithProviders(<MembersPage />, { scopes: ['member:view'] })

    expect(await screen.findByRole('link', { name: 'ハナ' })).toBeInTheDocument()
    expect(screen.getByText('70 pt')).toBeInTheDocument()
  })

  it('member:manage が無ければ登録フォームも削除も出さない', async () => {
    renderWithProviders(<MembersPage />, { scopes: ['member:view'] })
    await screen.findByRole('link', { name: 'ハナ' })

    expect(screen.queryByRole('button', { name: 'Add member' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
  })

  it('member:manage があれば登録できる', async () => {
    createMember.mockResolvedValue(member({ id: 2, name: 'タロウ' }))
    renderWithProviders(<MembersPage />, { scopes: MANAGER_SCOPES })
    await screen.findByRole('link', { name: 'ハナ' })

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'タロウ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add member' }))

    await waitFor(() => {
      expect(createMember).toHaveBeenCalledWith('タロウ', null)
    })
    expect(listMembers).toHaveBeenCalledTimes(2) // 登録後に読み直す
  })

  it('本人のログインアカウントを紐付けて登録できる', async () => {
    createMember.mockResolvedValue(member({ id: 2 }))
    renderWithProviders(<MembersPage />, { scopes: MANAGER_SCOPES })
    await screen.findByRole('link', { name: 'ハナ' })

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'タロウ' } })
    fireEvent.change(screen.getByLabelText(/sign-in email/), {
      target: { value: 'kid@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add member' }))

    await waitFor(() => {
      expect(createMember).toHaveBeenCalledWith('タロウ', 'kid@example.com')
    })
  })

  it('共有されただけのメンバーには削除を出さない（manage でも所有者ではない）', async () => {
    listMembers.mockResolvedValue([member({ access_level: 'manage', is_owner: false })])
    renderWithProviders(<MembersPage />, { scopes: MANAGER_SCOPES })
    await screen.findByRole('link', { name: 'ハナ' })

    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
  })

  it('自分自身のメンバーには目印を付ける', async () => {
    listMembers.mockResolvedValue([
      member({ is_self: true, access_level: 'view', is_owner: false }),
    ])
    renderWithProviders(<MembersPage />, { scopes: ['member:view'] })

    expect(await screen.findByText(/\(you\)/)).toBeInTheDocument()
  })

  it('メンバーがいなければ空の案内を出す', async () => {
    listMembers.mockResolvedValue([])
    renderWithProviders(<MembersPage />, { scopes: ['member:view'] })

    expect(await screen.findByText('No members yet.')).toBeInTheDocument()
  })

  it('削除は確認してから呼ぶ', async () => {
    deleteMember.mockResolvedValue(undefined)
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderWithProviders(<MembersPage />, { scopes: MANAGER_SCOPES })
    await screen.findByRole('link', { name: 'ハナ' })

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(deleteMember).not.toHaveBeenCalled()

    confirm.mockReturnValue(true)
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    await waitFor(() => {
      expect(deleteMember).toHaveBeenCalledWith(1)
    })
    confirm.mockRestore()
  })

  it('読み込みに失敗しても画面は壊さない', async () => {
    listMembers.mockRejectedValue(new Error('offline'))
    renderWithProviders(<MembersPage />, { scopes: ['member:view'] })

    expect(await screen.findByText('No members yet.')).toBeInTheDocument()
  })
})
