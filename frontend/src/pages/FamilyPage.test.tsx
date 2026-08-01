/**
 * 家族の詳細: サーバーが返す可否による操作の出し分けと、外す 2 通り（卒業・削除）。
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FamilyDetail, Membership } from '../services/families'
import { familyOf, member } from '../test-support/familyFixtures'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { FamilyPage } from './FamilyPage'

const listInvitations = vi.fn<() => Promise<never[]>>()
const proposeIndependence = vi.fn<(familyId: number, membershipId: number) => Promise<Membership>>()
const revokeIndependenceProposal =
  vi.fn<(familyId: number, membershipId: number) => Promise<void>>()
const removeMembership = vi.fn<(familyId: number, membershipId: number) => Promise<void>>()
const reorderMembers = vi.fn<(familyId: number, ids: number[]) => Promise<FamilyDetail>>()
const leave = vi.fn<(familyId: number) => Promise<void>>()

vi.mock('../services/families', () => ({
  parseUtc: (value: string) => new Date(`${value}Z`),
  families: {
    listInvitations: () => listInvitations(),
    proposeIndependence: (familyId: number, membershipId: number) =>
      proposeIndependence(familyId, membershipId),
    revokeIndependenceProposal: (familyId: number, membershipId: number) =>
      revokeIndependenceProposal(familyId, membershipId),
    removeMembership: (familyId: number, membershipId: number) =>
      removeMembership(familyId, membershipId),
    reorderMembers: (familyId: number, ids: number[]) => reorderMembers(familyId, ids),
    leave: (familyId: number) => leave(familyId),
  },
}))

function renderPage(family: FamilyDetail, reloadFamily = () => Promise.resolve()) {
  return renderWithProviders(<FamilyPage />, {
    scopes: ['family:view'],
    route: '/families/1',
    path: '/families/:familyId',
    family,
    reloadFamily,
  })
}

describe('FamilyPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listInvitations.mockResolvedValue([])
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('参加者と、見える範囲の残高を出す', () => {
    renderPage(familyOf('owner', [member()]))

    expect(screen.getByText('70 pt')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'History' })).toHaveAttribute(
      'href',
      '/families/1/ledgers/20',
    )
  })

  it('見えない台帳は残高も入り口も出さない（兄弟の残高）', () => {
    renderPage(
      familyOf('child', [
        member({ is_me: true, can_reset_password: false, can_graduate: false }),
        member({
          id: 3,
          display_name: 'タロウ',
          ledger_id: null,
          balance: null,
          can_reset_password: false,
          can_graduate: false,
        }),
      ]),
    )

    expect(screen.getByText('70 pt')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'History' })).toHaveLength(1)
  })

  it('今の所属と違う家族の URL では中身を出さない', () => {
    renderWithProviders(<FamilyPage />, {
      scopes: ['family:view'],
      route: '/families/9',
      path: '/families/:familyId',
      family: familyOf('owner', [member()]),
    })

    expect(screen.getByText('This family could not be loaded.')).toBeInTheDocument()
  })

  it('子には子の追加・招待を出さない', () => {
    renderPage(
      familyOf('child', [member({ is_me: true, can_reset_password: false, can_graduate: false })]),
    )

    expect(screen.queryByRole('button', { name: 'Add a child' })).not.toBeInTheDocument()
    expect(screen.queryByText('Invitations')).not.toBeInTheDocument()
  })

  it('親には子の追加を出す', () => {
    renderPage(familyOf('parent', [member()]))

    expect(screen.getByRole('button', { name: 'Add a child' })).toBeInTheDocument()
  })

  it('owner には招待を出し、parent には出さない', () => {
    renderPage(familyOf('parent', [member()]))
    expect(screen.queryByText('Invitations')).not.toBeInTheDocument()

    renderPage(familyOf('owner', [member()]))
    expect(screen.getByText('Invitations')).toBeInTheDocument()
  })

  it('一時パスワードは can_reset_password のときだけ出す', () => {
    renderPage(familyOf('owner', [member({ is_linked: false, can_reset_password: false })]))

    expect(screen.getByText(/no sign-in yet/)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Issue a temporary password' }),
    ).not.toBeInTheDocument()
  })

  it('卒業は can_graduate のときだけ出す（できない相手には出さない）', () => {
    renderPage(
      familyOf('parent', [
        member(),
        member({ id: 3, display_name: 'タロウ', is_linked: false, can_graduate: false }),
      ]),
    )

    expect(screen.getAllByRole('button', { name: 'Graduate this child' })).toHaveLength(1)
  })

  it('卒業を指示すると、確認のうえサーバーへ送る', () => {
    renderPage(familyOf('parent', [member()]))

    fireEvent.click(screen.getByRole('button', { name: 'Graduate this child' }))
    expect(proposeIndependence).toHaveBeenCalledWith(1, 2)
  })

  it('予定済みの子には取り消しと目印を出す', () => {
    renderPage(familyOf('parent', [member({ independence_proposed: true })]))

    expect(screen.getByText('graduating')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel the graduation' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Graduate this child' })).not.toBeInTheDocument()
  })

  it('削除は can_remove のときだけ出す（記録の残る子には出さない）', () => {
    renderPage(
      familyOf('owner', [
        member({ can_remove: false }),
        member({ id: 3, display_name: 'タロウ', balance: 0, can_remove: true }),
      ]),
    )

    const remove = screen.getAllByRole('button', { name: 'Delete' })
    expect(remove).toHaveLength(1)

    fireEvent.click(remove[0] as HTMLElement)
    expect(removeMembership).toHaveBeenCalledWith(1, 3)
  })

  it('予定を受けた子本人には卒業の承認を出す', () => {
    renderPage(
      familyOf('child', [
        member({
          is_me: true,
          independence_proposed: true,
          can_reset_password: false,
          can_graduate: false,
        }),
      ]),
    )

    expect(screen.getByRole('button', { name: 'Graduate' })).toBeInTheDocument()
  })

  it('予定が無ければ子に承認を出さない', () => {
    renderPage(
      familyOf('child', [member({ is_me: true, can_reset_password: false, can_graduate: false })]),
    )

    expect(screen.queryByRole('button', { name: 'Graduate' })).not.toBeInTheDocument()
  })

  it('owner には改名・脱退・解散を出す', () => {
    renderPage(familyOf('owner', [member()]))

    expect(screen.getByRole('button', { name: 'Rename' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Leave this family' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Dissolve this family' })).toBeInTheDocument()
  })

  it('parent には脱退だけを出す（改名・解散は owner の役目）', () => {
    renderPage(familyOf('parent', [member()]))

    expect(screen.getByRole('button', { name: 'Leave this family' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Rename' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Dissolve this family' })).not.toBeInTheDocument()
  })

  it('子には家族の設定を出さない（子は自分では抜けられない）', () => {
    renderPage(
      familyOf('child', [member({ is_me: true, can_reset_password: false, can_graduate: false })]),
    )

    expect(screen.queryByText('Family settings')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Leave this family' })).not.toBeInTheDocument()
  })

  it('子が 1 人だけなら並べ替えは出さない', () => {
    renderPage(familyOf('owner', [member()]))

    expect(screen.queryByRole('button', { name: 'Move ハナ down' })).not.toBeInTheDocument()
  })

  it('並べ替えると、入れ替えた順を送る', () => {
    reorderMembers.mockResolvedValue(familyOf('owner', []))
    renderPage(familyOf('owner', [member(), member({ id: 3, display_name: 'タロウ' })]))

    fireEvent.click(screen.getByRole('button', { name: 'Move タロウ up' }))
    expect(reorderMembers).toHaveBeenCalledWith(1, [3, 2])
  })

  it('脱退したら家族を読み直してから入口へ戻る（消えた家族へ送り返さない）', async () => {
    leave.mockResolvedValue()
    const reloadFamily = vi.fn<() => Promise<void>>().mockResolvedValue()
    renderPage(familyOf('parent', [member()]), reloadFamily)

    fireEvent.click(screen.getByRole('button', { name: 'Leave this family' }))

    await waitFor(() => {
      expect(reloadFamily).toHaveBeenCalled()
    })
  })

  it('端の子は動かせない（上下の行き先が無い）', () => {
    renderPage(familyOf('owner', [member(), member({ id: 3, display_name: 'タロウ' })]))

    expect(screen.getByRole('button', { name: 'Move ハナ up' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Move タロウ down' })).toBeDisabled()
  })
})
