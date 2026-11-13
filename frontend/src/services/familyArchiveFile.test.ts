/**
 * File input/output for backups (ADR-0026).
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from './api'
import type { FamilyArchive } from './families'
import { archiveFileName, readArchive, saveArchive } from './familyArchiveFile'

function archive(overrides: Partial<FamilyArchive> = {}): FamilyArchive {
  return {
    format: 'rewardpointsweb.family',
    version: 1,
    exported_at: '2026-08-09T12:34:56',
    family_name: 'ほその家',
    members: [],
    ...overrides,
  }
}

function fileOf(contents: string): File {
  return new File([contents], 'backup.json', { type: 'application/json' })
}

describe('archiveFileName', () => {
  it('names the file with the family name and export date (repeated exports do not overwrite)', () => {
    expect(archiveFileName(archive())).toBe('ほその家-2026-08-09.json')
  })
})

describe('saveArchive', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('downloads the backup as a file as is', () => {
    const createObjectURL = vi.fn(() => 'blob:archive')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)

    saveArchive(archive())

    expect(click).toHaveBeenCalledOnce()
    // Leaving it open would pile up memory with every export
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:archive')
    vi.unstubAllGlobals()
  })
})

describe('readArchive', () => {
  it('can be read as a backup', async () => {
    await expect(readArchive(fileOf(JSON.stringify(archive())))).resolves.toEqual(archive())
  })

  it('refuses a file that is not even JSON before sending', async () => {
    await expect(readArchive(fileOf('これは写真です'))).rejects.toThrow(ApiError)
  })

  it('refuses JSON from another app before sending', async () => {
    const other = JSON.stringify({ format: 'something.else', members: [] })

    await expect(readArchive(fileOf(other))).rejects.toMatchObject({
      code: 'invalid_family_archive',
    })
  })

  it('refuses a file without the participant list before sending', async () => {
    const broken = JSON.stringify({ format: 'rewardpointsweb.family', version: 1 })

    await expect(readArchive(fileOf(broken))).rejects.toMatchObject({
      code: 'invalid_family_archive',
    })
  })
})
