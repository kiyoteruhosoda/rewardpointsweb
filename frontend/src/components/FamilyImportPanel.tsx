/**
 * Rebuilds a family from a backup (restore; ADR-0026).
 *
 * Shown only on the screen of a parent who does not belong to any family yet. Import always creates a
 * **new family**, so while still a member the server refuses even if it could be pressed (ADR-0013).
 *
 * Nothing happens when the file is chosen. Just before sending, only check that it parses as JSON, and
 * leave the consistency of the content to the server (don't put the same check in two places).
 *
 * Restoring does not bring back other participants' accounts — they are not in the backup. Children
 * get invitation codes again. The import guidance says as much.
 */
import { useState, type SubmitEvent } from 'react'

import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families } from '../services/families'
import { readArchive } from '../services/familyArchiveFile'
import { ActionButton } from './ActionButton'
import { useToast } from './ToastNotification'

interface Props {
  /** Enters the imported family (reloads first, then moves). */
  onImported: (familyId: number) => Promise<void>
}

export function FamilyImportPanel({ onImported }: Props) {
  const { t } = useI18n()
  const { notify } = useToast()
  const [file, setFile] = useState<File | null>(null)

  const [restore, restoring] = usePendingAction(async (event: SubmitEvent) => {
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
        {/* Disabled until a file is chosen. Better to show up front what is missing than to say
            "no file" after pressing */}
        <ActionButton type="submit" pending={restoring} disabled={file === null}>
          {t('families.import.submit')}
        </ActionButton>
      </form>
    </section>
  )
}
