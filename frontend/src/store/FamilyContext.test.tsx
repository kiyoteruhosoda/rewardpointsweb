/**
 * 所属する家族の共有状態: 取得のきっかけと、失敗したときに何を残すか。
 *
 * 画面の側は `FamilyContext` を差し替えて描けるので（`test-support`）、ここでは
 * 状態を作る `FamilyProvider` そのものを見る。
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FamilyDetail, FamilySummary } from '../services/families'
import { AuthContext, type AuthValue } from './AuthContext'
import { FamilyProvider, useFamily } from './FamilyContext'

const list = vi.fn<() => Promise<FamilySummary[]>>()
const view = vi.fn<() => Promise<FamilyDetail>>()

vi.mock('../services/families', () => ({
  families: {
    list: () => list(),
    view: () => view(),
  },
}))

const SUMMARY: FamilySummary = {
  id: 1,
  name: 'ほその家',
  my_membership_id: 1,
  my_role: 'owner',
  member_count: 2,
}

const DETAIL: FamilyDetail = {
  id: 1,
  name: 'ほその家',
  my_membership_id: 1,
  my_role: 'owner',
  memberships: [],
}

function authValueOf(scopes: string[]): AuthValue {
  return {
    user: {
      user_id: 1,
      username: 'manager',
      display_name: 'manager',
      email: null,
      scopes,
      must_change_password: false,
    },
    loading: false,
    login: () => Promise.resolve(),
    loginWithPasskey: () => Promise.resolve(),
    logout: () => undefined,
    refreshMe: () => Promise.resolve(),
    hasScope: (...codes: string[]) => codes.every((code) => scopes.includes(code)),
  }
}

/** 状態をそのまま文字にして出す（描き分けは各画面の責務なのでここでは見ない）。 */
function Probe() {
  const { family, failed, loading } = useFamily()
  if (loading) return <p>loading</p>
  return <p>{failed ? 'failed' : (family?.name ?? 'none')}</p>
}

function renderProvider(scopes = ['family:view']) {
  return render(
    <AuthContext.Provider value={authValueOf(scopes)}>
      <FamilyProvider>
        <Probe />
      </FamilyProvider>
    </AuthContext.Provider>,
  )
}

describe('FamilyProvider', () => {
  beforeEach(() => {
    list.mockReset()
    view.mockReset()
  })

  it('所属する家族を読む', async () => {
    list.mockResolvedValue([SUMMARY])
    view.mockResolvedValue(DETAIL)
    renderProvider()

    expect(await screen.findByText('ほその家')).toBeInTheDocument()
  })

  it('family:view を持たない人には引きに行かない', async () => {
    renderProvider([])

    expect(await screen.findByText('none')).toBeInTheDocument()
    expect(list).not.toHaveBeenCalled()
  })

  it('最初の取得に失敗したら、読めなかったと伝える（「所属していない」ではない）', async () => {
    list.mockRejectedValue(new Error('offline'))
    renderProvider()

    expect(await screen.findByText('failed')).toBeInTheDocument()
  })

  it('手元に戻ってきたら読み直す', async () => {
    list.mockResolvedValue([SUMMARY])
    view.mockResolvedValueOnce(DETAIL).mockResolvedValue({ ...DETAIL, name: 'ほその家（改名）' })
    renderProvider()

    await screen.findByText('ほその家')
    fireEvent(document, new Event('visibilitychange'))

    expect(await screen.findByText('ほその家（改名）')).toBeInTheDocument()
  })

  it('読み直しに失敗しても、読めている家族は捨てない', async () => {
    list.mockResolvedValueOnce([SUMMARY]).mockRejectedValue(new Error('offline'))
    view.mockResolvedValue(DETAIL)
    renderProvider()

    await screen.findByText('ほその家')
    fireEvent(document, new Event('visibilitychange'))

    await waitFor(() => {
      expect(list).toHaveBeenCalledTimes(2)
    })
    // 残高も子への入口も、この家族から組み立てられる。消すと家族から外された
    // ようにしか見えない
    expect(screen.getByText('ほその家')).toBeInTheDocument()
  })
})
