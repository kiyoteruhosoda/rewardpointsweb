/**
 * 控えから家族を作り直す（復元。ADR-0025）。
 *
 * 出るのは、まだどの家族にも所属していない親の画面だけ。取り込みは必ず **新しい
 * 家族** を作るので、所属したままでは押せてもサーバーが断る（ADR-0013）。
 *
 * ファイルを選んだ時点では何もしない。JSON として読めるかだけを送信の直前に見て、
 * 中身の辻褄はサーバーへ任せる（同じ検査を 2 か所に置かない）。
 *
 * 復元しても、他の参加者のアカウントは戻らない — 控えに入っていないため。子ども
 * には招待コードを配り直す。取り込みの案内でそこまで言う。
 */
import { useState, type FormEvent } from 'react'

import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families } from '../services/families'
import { readArchive } from '../services/familyArchiveFile'
import { ActionButton } from './ActionButton'
import { useToast } from './ToastNotification'

interface Props {
  /** 取り込めた家族へ入る（読み直してから移る）。 */
  onImported: (familyId: number) => Promise<void>
}

export function FamilyImportPanel({ onImported }: Props) {
  const { t } = useI18n()
  const { notify } = useToast()
  const [file, setFile] = useState<File | null>(null)

  const [restore, restoring] = usePendingAction(async (event: FormEvent) => {
    event.preventDefault()
    if (!file) return
    try {
      const imported = await families.importArchive(await readArchive(file))
      notify(
        'success',
        t('families.import.done', {
          members: imported.member_count,
          entries: imported.transaction_count,
        }),
      )
      await onImported(imported.family_id)
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  })

  return (
    <section className="card">
      <h2>{t('families.import.title')}</h2>
      <p>{t('families.import.hint')}</p>
      <p>{t('families.import.accountHint')}</p>
      <form className="inline-form" onSubmit={restore}>
        <label>
          {t('families.import.file')}
          <input
            type="file"
            accept="application/json,.json"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null)
            }}
          />
        </label>
        {/* 選ぶまでは押せない。押してから「ファイルがありません」と言うより、
            何が足りないかが先に分かる */}
        <ActionButton type="submit" pending={restoring} disabled={file === null}>
          {t('families.import.submit')}
        </ActionButton>
      </form>
    </section>
  )
}
