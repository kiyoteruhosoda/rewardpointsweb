/**
 * 控え（バックアップ）のファイル入出力（ADR-0025）。
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
  it('家族の名前と書き出した日を付ける（何度書き出しても上書きにならない）', () => {
    expect(archiveFileName(archive())).toBe('ほその家-2026-08-09.json')
  })
})

describe('saveArchive', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('控えをそのままファイルとして落とす', () => {
    const createObjectURL = vi.fn(() => 'blob:archive')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)

    saveArchive(archive())

    expect(click).toHaveBeenCalledOnce()
    // 開きっぱなしにすると、書き出すたびにメモリが積み上がる
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:archive')
    vi.unstubAllGlobals()
  })
})

describe('readArchive', () => {
  it('控えとして読める', async () => {
    await expect(readArchive(fileOf(JSON.stringify(archive())))).resolves.toEqual(archive())
  })

  it('JSON ですらないファイルは、送る前に断る', async () => {
    await expect(readArchive(fileOf('これは写真です'))).rejects.toThrow(ApiError)
  })

  it('別のアプリの JSON は、送る前に断る', async () => {
    const other = JSON.stringify({ format: 'something.else', members: [] })

    await expect(readArchive(fileOf(other))).rejects.toMatchObject({
      code: 'invalid_family_archive',
    })
  })

  it('参加者の並びが無いファイルは、送る前に断る', async () => {
    const broken = JSON.stringify({ format: 'rewardpointsweb.family', version: 1 })

    await expect(readArchive(fileOf(broken))).rejects.toMatchObject({
      code: 'invalid_family_archive',
    })
  })
})
