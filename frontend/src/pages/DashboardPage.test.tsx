/** ダッシュボード: 家族の残高一覧。システム運用の情報は出さない。 */
import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { MemberSummary } from '../services/rewardPoints'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { DashboardPage } from './DashboardPage'

const listMembers = vi.fn<() => Promise<MemberSummary[]>>()

vi.mock('../services/rewardPoints', () => ({
  rewardPoints: {
    listMembers: () => listMembers(),
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

describe('DashboardPage', () => {
  beforeEach(() => {
    listMembers.mockReset()
  })

  it('挨拶と、メンバーごとの残高カードを出す', async () => {
    listMembers.mockResolvedValue([member(), member({ id: 2, name: 'タロウ', balance: 30 })])
    renderWithProviders(<DashboardPage />, { scopes: ['member:view'] })

    expect(await screen.findByText('70 pt')).toBeInTheDocument()
    expect(screen.getByText('30 pt')).toBeInTheDocument()
    expect(screen.getByText('Hello, manager')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /ハナ/ })).toHaveAttribute('href', '/members/1')
  })

  it('自分自身のメンバーには目印を付ける', async () => {
    listMembers.mockResolvedValue([member({ is_self: true })])
    renderWithProviders(<DashboardPage />, { scopes: ['member:view'] })

    expect(await screen.findByText(/\(you\)/)).toBeInTheDocument()
  })

  it('システム運用の情報（API ドキュメント）は出さない', async () => {
    listMembers.mockResolvedValue([member()])
    renderWithProviders(<DashboardPage />, { scopes: ['member:view'] })
    await screen.findByText('70 pt')

    expect(screen.queryByRole('link', { name: '/docs' })).not.toBeInTheDocument()
    expect(screen.queryByText(/openapi/i)).not.toBeInTheDocument()
  })

  it('メンバーがいなければポイント画面への案内を出す', async () => {
    listMembers.mockResolvedValue([])
    renderWithProviders(<DashboardPage />, { scopes: ['member:view'] })

    expect(await screen.findByRole('link', { name: 'Add members' })).toHaveAttribute(
      'href',
      '/members',
    )
  })

  it('読み込みに失敗しても画面は壊さない', async () => {
    listMembers.mockRejectedValue(new Error('offline'))
    renderWithProviders(<DashboardPage />, { scopes: ['member:view'] })

    expect(
      await screen.findByText('No members yet. Add them from the Points page.'),
    ).toBeInTheDocument()
  })

  it('member:view が無ければ一覧を取得せず、空の案内も出さない（guest 等）', async () => {
    renderWithProviders(<DashboardPage />, { scopes: ['dashboard:view'] })

    expect(await screen.findByText('Hello, manager')).toBeInTheDocument()
    expect(listMembers).not.toHaveBeenCalled()
    expect(
      screen.queryByText('No members yet. Add them from the Points page.'),
    ).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Add members' })).not.toBeInTheDocument()
  })
})
