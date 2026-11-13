/**
 * Exports a copy of the whole family (backup; ADR-0026).
 *
 * Shown only on parents' (owner / parent) screens. The copy contains every family member's ledger,
 * so it is not given to children who can only see their own (the server refuses on the same condition).
 *
 * Pressing downloads a single JSON file. Restoring is done from a state with no family
 * (`FamilyImportPanel`), so import is not placed on this screen — to avoid suggesting it could
 * overwrite the current family.
 */
import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families } from '../services/families'
import { saveArchive } from '../services/familyArchiveFile'
import { ActionButton } from './ActionButton'
import { useToast } from './ToastNotification'

interface Props {
  familyId: number
}

export function FamilyArchivePanel({ familyId }: Props) {
  const { t } = useI18n()
  const { notify } = useToast()

  const [save, saving] = usePendingAction(async () => {
    try {
      saveArchive(await families.exportArchive(familyId))
      notify('success', t('families.archive.exported'))
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  })

  return (
    <section className="card">
      <h2>{t('families.archive.title')}</h2>
      <p>{t('families.archive.hint')}</p>
      <p>{t('families.archive.privacyHint')}</p>
      <ActionButton type="button" pending={saving} onClick={save}>
        {t('families.archive.export')}
      </ActionButton>
    </section>
  )
}
