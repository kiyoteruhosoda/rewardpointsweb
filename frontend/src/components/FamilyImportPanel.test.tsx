/**
 * Restoring from a backup (ADR-0026).
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FamilyArchive, ImportedFamily } from '../services/families'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { FamilyImportPanel } from './FamilyImportPanel'

const importArchive = vi.fn<(archive: FamilyArchive) => Promise<ImportedFamily>>()

vi.mock('../services/families', () => ({
  families: {
    importArchive: (archive: FamilyArchive) => importArchive(archive),
  },
}))

const ARCHIVE: FamilyArchive = {
  format: 'rewardpointsweb.family',
  version: 1,
  exported_at: '2026-08-09T12:34:56',
  family_name: 'ほその家',
  members: [{ ref: 'm1', display_name: 'おとうさん', role: 'owner', ledger: null }],
}

function choose(contents: string): void {
  const input = screen.getByLabelText('Backup file')
  const file = new File([contents], 'backup.json', { type: 'application/json' })
  fireEvent.change(input, { target: { files: [file] } })
}

describe('FamilyImportPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('sends the chosen file and enters the created family', async () => {
    importArchive.mockResolvedValue({
      family_id: 7,
      name: 'ほその家',
      member_count: 3,
      transaction_count: 12,
    })
    const onImported = vi.fn<(familyId: number) => Promise<void>>().mockResolvedValue()
    renderWithProviders(<FamilyImportPanel onImported={onImported} />)

    choose(JSON.stringify(ARCHIVE))
    fireEvent.click(screen.getByRole('button', { name: 'Restore' }))

    await waitFor(() => {
      expect(importArchive).toHaveBeenCalledWith(ARCHIVE)
    })
    expect(onImported).toHaveBeenCalledWith(7)
  })

  it('reports how much was restored', async () => {
    importArchive.mockResolvedValue({
      family_id: 7,
      name: 'ほその家',
      member_count: 3,
      transaction_count: 12,
    })
    renderWithProviders(<FamilyImportPanel onImported={() => Promise.resolve()} />)

    choose(JSON.stringify(ARCHIVE))
    fireEvent.click(screen.getByRole('button', { name: 'Restore' }))

    expect(await screen.findByText('Restored 3 members and 12 point records.')).toBeInTheDocument()
  })

  it('refuses a file that is not a backup without sending it', async () => {
    renderWithProviders(<FamilyImportPanel onImported={() => Promise.resolve()} />)

    choose('これは写真です')
    fireEvent.click(screen.getByRole('button', { name: 'Restore' }))

    expect(
      await screen.findByText(
        'This file cannot be read as a backup of a family. Check that you picked the right file.',
      ),
    ).toBeInTheDocument()
    expect(importArchive).not.toHaveBeenCalled()
  })

  it('cannot be pressed until a file is chosen', () => {
    renderWithProviders(<FamilyImportPanel onImported={() => Promise.resolve()} />)

    expect(screen.getByRole('button', { name: 'Restore' })).toBeDisabled()

    choose(JSON.stringify(ARCHIVE))

    expect(screen.getByRole('button', { name: 'Restore' })).toBeEnabled()
  })
})
