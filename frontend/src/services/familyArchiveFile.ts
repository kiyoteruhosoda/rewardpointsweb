/**
 * 控え（バックアップ）をファイルとしてやり取りする（ADR-0026）。
 *
 * サーバーが返すのは JSON そのもので、ファイルにするのは画面側の仕事。ダウンロード
 * には認証ヘッダーが要る（URL を開くだけでは取れない）ので、受け取った本文から
 * ブラウザの中で組み立てる。
 *
 * 読み込み側で見るのは「これは控えらしいか」までにする。中身の辻褄はサーバーが
 * 確かめる（同じ検査を 2 か所に書くと、片方だけが古くなる）。ここで弾くのは、
 * 選び間違えたファイルを送ってしまう手前で気付けるようにするため。
 */
import { ApiError } from './api'
import type { FamilyArchive } from './families'

/** サーバーと合わせた印（`ARCHIVE_FORMAT`）。 */
const ARCHIVE_FORMAT = 'rewardpointsweb.family'

/** 控えとして読めないファイルに付けるコード（`error.invalid_family_archive`）。 */
const INVALID_ARCHIVE = 'invalid_family_archive'

/** `ほその家-2026-08-09.json`。同じ家族を何度か書き出しても上書きにならない。 */
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
