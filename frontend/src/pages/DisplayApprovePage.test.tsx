/**
 * 表示端末の承認（運用管理者。ADR-0047）: QR コードから開くとコードが入っていて、家族と名前を選んで承認する。
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type * as DisplayModule from '../services/display'
import type { DisplayableFamily, DisplayDevice } from '../services/display'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { DisplayApprovePage } from './DisplayApprovePage'

const approvePairing =
  vi.fn<(body: { user_code: string; family_id: number; name: string }) => Promise<DisplayDevice>>()
const listDisplayableFamilies = vi.fn<() => Promise<DisplayableFamily[]>>()

vi.mock('../services/display', async (importOriginal) => ({
  ...(await importOriginal<typeof DisplayModule>()),
  approvePairing: (body: { user_code: string; family_id: number; name: string }) =>
    approvePairing(body),
  listDisplayableFamilies: () => listDisplayableFamilies(),
}))

const APPROVED: DisplayDevice = {
  account_id: 7,
  family_id: 1,
  family_name: 'ほその家',
  name: 'リビング',
  created_at: '2026-10-05T00:00:00Z',
  last_used_at: null,
}

describe('DisplayApprovePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listDisplayableFamilies.mockResolvedValue([{ id: 1, name: 'ほその家' }])
    approvePairing.mockResolvedValue(APPROVED)
  })

  it('QR コードから開くと確認コードが入っていて、1 家族なら選ばずに承認できる', async () => {
    renderWithProviders(<DisplayApprovePage />, {
      route: '/admin/displays/approve#KQ7M-3XPA',
      scopes: ['display:approve'],
    })

    expect(screen.getByRole('textbox', { name: 'Code' })).toHaveValue('KQ7M-3XPA')
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: 'Family to show' })).toHaveValue('1')
    })
    fireEvent.change(screen.getByRole('textbox', { name: 'Name' }), {
      target: { value: 'リビング' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))

    await waitFor(() => {
      expect(approvePairing).toHaveBeenCalledWith({
        user_code: 'KQ7M-3XPA',
        family_id: 1,
        name: 'リビング',
      })
    })
  })

  it('「キャンセル」では承認しない', () => {
    renderWithProviders(<DisplayApprovePage />, { route: '/admin/displays/approve#KQ7M-3XPA' })

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(approvePairing).not.toHaveBeenCalled()
  })
})
