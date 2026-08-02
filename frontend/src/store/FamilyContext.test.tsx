/**
 * 所属する家族の共有状態: 取得のきっかけと、失敗したときに何を残すか。
 *
 * 画面の側は `FamilyContext` を差し替えて描けるので（`test-support`）、ここでは
 * 状態を作る `FamilyProvider` そのものを見る。
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Link, MemoryRouter } from 'react-router-dom'
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

/** 応答の届く順を組み立てるための、外から解決できる約束。 */
interface Deferred {
  promise: Promise<FamilyDetail>
  arrive: (family: FamilyDetail) => void
}

function deferred(): Deferred {
  let resolve: (family: FamilyDetail) => void = () => {
    throw new Error('Promise の実行子がまだ走っていない')
  }
  const promise = new Promise<FamilyDetail>((settle) => {
    resolve = settle
  })
  return {
    promise,
    arrive: (family) => {
      resolve(family)
    },
  }
}

/** 届いた応答の反映まで含めて流し切る。 */
async function flush(arrival: () => void): Promise<void> {
  await act(() => {
    arrival()
    return Promise.resolve()
  })
}

/** 状態をそのまま文字にして出す（描き分けは各画面の責務なのでここでは見ない）。 */
function Probe() {
  const { family, failed, loading } = useFamily()
  if (loading) return <p>loading</p>
  return <p>{failed ? 'failed' : (family?.name ?? 'none')}</p>
}

/** 画面を移るところまで見たいので、行き先へのリンクを添えて描く。 */
function renderProvider(scopes = ['family:view']) {
  return render(
    <AuthContext.Provider value={authValueOf(scopes)}>
      <MemoryRouter initialEntries={['/']}>
        <FamilyProvider>
          <Link to="/families">家族設定へ</Link>
          <Probe />
        </FamilyProvider>
      </MemoryRouter>
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

  it('画面を移るたびに読み直す（1 回きりだと別の端末で足された分が出てこない）', async () => {
    list.mockResolvedValue([SUMMARY])
    view.mockResolvedValueOnce(DETAIL).mockResolvedValue({ ...DETAIL, name: 'ほその家（改名）' })
    renderProvider()

    await screen.findByText('ほその家')
    fireEvent.click(screen.getByRole('link', { name: '家族設定へ' }))

    expect(await screen.findByText('ほその家（改名）')).toBeInTheDocument()
  })

  it('追い越された応答で新しい内容を上書きしない', async () => {
    const late = deferred()
    list.mockResolvedValue([SUMMARY])
    view
      .mockReturnValueOnce(late.promise)
      .mockResolvedValue({ ...DETAIL, name: 'ほその家（改名）' })
    renderProvider()

    // 最初の取得が届かないうちに 2 回目を始め、そちらが先に届く
    fireEvent.click(screen.getByRole('link', { name: '家族設定へ' }))
    await screen.findByText('ほその家（改名）')

    await flush(() => {
      late.arrive(DETAIL)
    })

    expect(screen.getByText('ほその家（改名）')).toBeInTheDocument()
  })

  it('追い越された取得が先に終わっても、読み込み中を解かない', async () => {
    const first = deferred()
    const second = deferred()
    list.mockResolvedValue([SUMMARY])
    view.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    renderProvider()

    await waitFor(() => {
      expect(view).toHaveBeenCalledTimes(1)
    })
    fireEvent.click(screen.getByRole('link', { name: '家族設定へ' }))
    await waitFor(() => {
      expect(view).toHaveBeenCalledTimes(2)
    })

    // 捨てた結果で読み込み中を解くと、まだ何も入っていない状態が
    // 「家族がない・子どもがいない」として画面に出てしまう
    await flush(() => {
      first.arrive(DETAIL)
    })
    expect(screen.getByText('loading')).toBeInTheDocument()

    await flush(() => {
      second.arrive({ ...DETAIL, name: 'ほその家（改名）' })
    })
    expect(screen.getByText('ほその家（改名）')).toBeInTheDocument()
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
