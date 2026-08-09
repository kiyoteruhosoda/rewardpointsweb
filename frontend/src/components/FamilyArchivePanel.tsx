/**
 * 家族まるごとの控えを書き出す（バックアップ。ADR-0025）。
 *
 * 出るのは親（owner / parent）の画面だけ。控えには家族全員の台帳が載るので、
 * 自分の台帳しか見られない子には渡さない（サーバーも同じ条件で断る）。
 *
 * 押すと 1 つの JSON ファイルが落ちてくる。戻すのは家族に所属していない状態から
 * （`FamilyImportPanel`）なので、この画面には取り込みを置かない — 今の家族へ
 * 上書きできると誤解させないため。
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
