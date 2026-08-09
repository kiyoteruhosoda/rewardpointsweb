/**
 * 家族まるごとの書き出し（ADR-0025）。
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../services/api'
import type { FamilyArchive } from '../services/families'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { FamilyArchivePanel } from './FamilyArchivePanel'

const exportArchive = vi.fn<(familyId: number) => Promise<FamilyArchive>>()
const saveArchive = vi.fn<(archive: FamilyArchive) => void>()

vi.mock('../services/families', () => ({
  families: {
    exportArchive: (familyId: number) => exportArchive(familyId),
  },
}))

vi.mock('../services/familyArchiveFile', () => ({
  saveArchive: (archive: FamilyArchive) => {
    saveArchive(archive)
  },
}))

const ARCHIVE: FamilyArchive = {
  format: 'rewardpointsweb.family',
  version: 1,
  exported_at: '2026-08-09T12:34:56',
  family_name: 'ほその家',
  members: [],
}

describe('FamilyArchivePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('受け取った控えをそのままファイルにする', async () => {
    exportArchive.mockResolvedValue(ARCHIVE)
    renderWithProviders(<FamilyArchivePanel familyId={4} />)

    fireEvent.click(screen.getByRole('button', { name: 'Save a backup' }))

    await waitFor(() => {
      expect(saveArchive).toHaveBeenCalledWith(ARCHIVE)
    })
    expect(exportArchive).toHaveBeenCalledWith(4)
  })

  it('取れなかったらファイルを作らず、理由を出す', async () => {
    exportArchive.mockRejectedValue(new ApiError(403, 'family_access_denied'))
    renderWithProviders(<FamilyArchivePanel familyId={4} />)

    fireEvent.click(screen.getByRole('button', { name: 'Save a backup' }))

    expect(await screen.findByText('You do not have that role in this family.')).toBeInTheDocument()
    expect(saveArchive).not.toHaveBeenCalled()
  })
})
