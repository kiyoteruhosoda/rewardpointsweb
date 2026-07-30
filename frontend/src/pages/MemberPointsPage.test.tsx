/**
 * ポイント画面: 変更 UI は「scope を持ち、かつそのメンバーへ manage」のときだけ。
 * メンバー本人（view）には残高と履歴だけを見せる。
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type * as RewardPointsModule from '../services/rewardPoints'
import type { MemberShare, PointLedger } from '../services/rewardPoints'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { MemberPointsPage } from './MemberPointsPage'

const viewPoints = vi.fn<() => Promise<PointLedger>>()
const addPoints = vi.fn<(memberId: number, points: number, reason: string) => Promise<unknown>>()
const consumePoints =
  vi.fn<(memberId: number, points: number, application: string) => Promise<unknown>>()
const deleteEntry = vi.fn<(memberId: number, entryId: number) => Promise<void>>()
const listShares = vi.fn<() => Promise<MemberShare[]>>()
const shareMember = vi.fn<(memberId: number, email: string, level: string) => Promise<unknown>>()
const revokeShare = vi.fn<(memberId: number, userId: number) => Promise<void>>()

vi.mock('../services/rewardPoints', async () => {
  const actual = await vi.importActual<typeof RewardPointsModule>('../services/rewardPoints')
  return {
    parseUtc: actual.parseUtc,
    rewardPoints: {
      viewPoints: () => viewPoints(),
      addPoints: (memberId: number, points: number, reason: string) =>
        addPoints(memberId, points, reason),
      consumePoints: (memberId: number, points: number, application: string) =>
        consumePoints(memberId, points, application),
      deleteEntry: (memberId: number, entryId: number) => deleteEntry(memberId, entryId),
      listShares: () => listShares(),
      shareMember: (memberId: number, email: string, level: string) =>
        shareMember(memberId, email, level),
      revokeShare: (memberId: number, userId: number) => revokeShare(memberId, userId),
    },
  }
})

function ledger(overrides: Partial<PointLedger> = {}): PointLedger {
  return {
    member_id: 1,
    member_name: 'ハナ',
    balance: 70,
    access_level: 'manage',
    entries: [
      {
        id: 9,
        entry_type: 'consumption',
        occurred_at: '2026-07-30T09:00:00',
        points: 30,
        signed_points: -30,
        description: 'おかし',
      },
      {
        id: 8,
        entry_type: 'addition',
        occurred_at: '2026-07-29T09:00:00',
        points: 100,
        signed_points: 100,
        description: 'お手伝い',
      },
    ],
    ...overrides,
  }
}

const MANAGER_SCOPES = ['member:view', 'member:manage', 'point:view', 'point:manage']
const MEMBER_SCOPES = ['member:view', 'point:view']

function renderPage(scopes: string[]) {
  return renderWithProviders(<MemberPointsPage />, {
    scopes,
    route: '/members/1',
    path: '/members/:memberId',
  })
}

describe('MemberPointsPage', () => {
  beforeEach(() => {
    for (const spy of [
      viewPoints,
      addPoints,
      consumePoints,
      deleteEntry,
      listShares,
      shareMember,
      revokeShare,
    ]) {
      spy.mockReset()
    }
    viewPoints.mockResolvedValue(ledger())
    listShares.mockResolvedValue([])
  })

  it('残高と履歴を表示する', async () => {
    renderPage(MANAGER_SCOPES)

    expect(await screen.findByText("ハナ's points")).toBeInTheDocument()
    expect(screen.getByText('70 pt')).toBeInTheDocument()
    expect(screen.getByText('-30 pt')).toBeInTheDocument()
    expect(screen.getByText('+100 pt')).toBeInTheDocument()
    expect(screen.getByText('おかし')).toBeInTheDocument()
  })

  it('加算できる', async () => {
    addPoints.mockResolvedValue(undefined)
    renderPage(MANAGER_SCOPES)
    await screen.findByText('70 pt')

    fireEvent.change(screen.getByLabelText('Add points - Points'), { target: { value: '50' } })
    fireEvent.change(screen.getByLabelText('Add points - Reason'), { target: { value: 'お風呂' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add points' }))

    await waitFor(() => {
      expect(addPoints).toHaveBeenCalledWith(1, 50, 'お風呂')
    })
    expect(viewPoints).toHaveBeenCalledTimes(2) // 記録後に読み直す
  })

  it('消費できる', async () => {
    consumePoints.mockResolvedValue(undefined)
    renderPage(MANAGER_SCOPES)
    await screen.findByText('70 pt')

    fireEvent.change(screen.getByLabelText('Use points - Points'), { target: { value: '20' } })
    fireEvent.change(screen.getByLabelText('Use points - Used for'), {
      target: { value: 'ジュース' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Use points' }))

    await waitFor(() => {
      expect(consumePoints).toHaveBeenCalledWith(1, 20, 'ジュース')
    })
  })

  it('履歴を 1 件取り消せる', async () => {
    deleteEntry.mockResolvedValue(undefined)
    renderPage(MANAGER_SCOPES)
    await screen.findByText('70 pt')

    const [firstDelete] = screen.getAllByRole('button', { name: 'Delete' })
    fireEvent.click(firstDelete as HTMLElement)

    await waitFor(() => {
      expect(deleteEntry).toHaveBeenCalledWith(1, 9)
    })
  })

  it('メンバー本人には閲覧のみを見せる（変更 UI は出さない）', async () => {
    viewPoints.mockResolvedValue(ledger({ access_level: 'view' }))
    renderPage(MEMBER_SCOPES)

    expect(await screen.findByText('70 pt')).toBeInTheDocument()
    expect(screen.getByText('おかし')).toBeInTheDocument() // 履歴は見られる
    expect(screen.getByText(/only the people who manage them/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add points' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Use points' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument()
  })

  it('point:manage を持っていても view で共有されたメンバーは変更できない', async () => {
    viewPoints.mockResolvedValue(ledger({ access_level: 'view' }))
    renderPage(MANAGER_SCOPES)
    await screen.findByText('70 pt')

    expect(screen.queryByRole('button', { name: 'Add points' })).not.toBeInTheDocument()
  })

  it('共有の管理は manage のときだけ出す', async () => {
    viewPoints.mockResolvedValue(ledger({ access_level: 'view' }))
    renderPage(MANAGER_SCOPES)
    await screen.findByText('70 pt')

    expect(screen.queryByText('Sharing')).not.toBeInTheDocument()
    expect(listShares).not.toHaveBeenCalled()
  })

  it('共有を追加できる', async () => {
    listShares.mockResolvedValue([])
    shareMember.mockResolvedValue(undefined)
    renderPage(MANAGER_SCOPES)
    await screen.findByText('Sharing')

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'other@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Access'), { target: { value: 'manage' } })
    fireEvent.click(screen.getByRole('button', { name: 'Share' }))

    await waitFor(() => {
      expect(shareMember).toHaveBeenCalledWith(1, 'other@example.com', 'manage')
    })
  })

  it('共有先を一覧し、解除できる', async () => {
    listShares.mockResolvedValue([
      { user_id: 7, email: 'other@example.com', username: 'other', access_level: 'manage' },
    ])
    revokeShare.mockResolvedValue(undefined)
    renderPage(MANAGER_SCOPES)

    expect(await screen.findByText('other@example.com')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Stop sharing' }))

    await waitFor(() => {
      expect(revokeShare).toHaveBeenCalledWith(1, 7)
    })
  })

  it('読み込めなければ案内を出す', async () => {
    viewPoints.mockRejectedValue(new Error('gone'))
    renderPage(MANAGER_SCOPES)

    expect(await screen.findByText('These points could not be loaded.')).toBeInTheDocument()
  })
})
