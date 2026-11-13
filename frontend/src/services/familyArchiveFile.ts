/**
 * Exchanges archives (backups) as files (ADR-0026).
 *
 * The server returns plain JSON; turning it into a file is the client's job. Downloading
 * needs an auth header (opening the URL alone does not work), so the file is assembled
 * in the browser from the received body.
 *
 * On import, only check "does this look like an archive". The server checks that the contents
 * are consistent (writing the same check in two places lets one of them go stale). Rejecting here
 * is so the user notices a wrongly chosen file before sending it.
 */
import { ApiError } from './api'
import type { FamilyArchive } from './families'

/** Marker shared with the server (`ARCHIVE_FORMAT`). */
const ARCHIVE_FORMAT = 'rewardpointsweb.family'

/** Code for a file that cannot be read as an archive (`error.invalid_family_archive`). */
const INVALID_ARCHIVE = 'invalid_family_archive'

/** `ほその家-2026-08-09.json`. Exporting the same family several times does not overwrite. */
export function archiveFileName(archive: FamilyArchive): string {
  return `${archive.family_name}-${archive.exported_at.slice(0, 10)}.json`
}

export function saveArchive(archive: FamilyArchive): void {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(archive, null, 2)], { type: 'application/json' }),
  )
  const link = document.createElement('a')
  link.href = url
  link.download = archiveFileName(archive)
  link.click()
  URL.revokeObjectURL(url)
}

export async function readArchive(file: File): Promise<FamilyArchive> {
  let parsed: unknown
  try {
    parsed = JSON.parse(await file.text())
  } catch {
    throw new ApiError(400, INVALID_ARCHIVE)
  }
  if (!looksLikeArchive(parsed)) throw new ApiError(400, INVALID_ARCHIVE)
  return parsed
}

function looksLikeArchive(value: unknown): value is FamilyArchive {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Partial<FamilyArchive>
  return candidate.format === ARCHIVE_FORMAT && Array.isArray(candidate.members)
}
