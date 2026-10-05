/**
 * 表示端末の一覧（運用管理者。`display:approve`。ADR-0047）。
 *
 * どの家族をどの端末に映しているかを並べ、外せるようにする。外すと端末の資格情報が
 * 消え、端末は 5 分以内（手元のトークンの寿命）にコードの画面へ戻る。
 */
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { ActionButton } from '../components/ActionButton'
import { useToast } from '../components/ToastNotification'
import { usePendingRows } from '../hooks/usePendingRows'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import {
  APPROVE_PATH,
  listDisplayDevices,
  removeDisplayDevice,
  type DisplayDevice,
} from '../services/display'
import { parseUtc } from '../services/families'

export function DisplaysPage() {
  const { t, locale } = useI18n()
  const { notify } = useToast()
  const [devices, setDevices] = useState<DisplayDevice[] | null>(null)
  const { pendingActionOf, runForRow } = usePendingRows<'removal'>()

  const reload = useCallback(async () => {
    try {
      setDevices(await listDisplayDevices())
    } catch (err) {
      notify('error', t(errorMessageKey(err)))
    }
  }, [notify, t])

  useEffect(() => {
    void reload()
  }, [reload])

  const remove = (device: DisplayDevice) => {
    if (
      !window.confirm(
        t('displays.confirmRemove', { name: device.name, family: device.family_name }),
      )
    ) {
      return
    }
    void runForRow(device.account_id, 'removal', async () => {
      try {
        await removeDisplayDevice(device.account_id)
        notify('success', t('displays.removed', { name: device.name }))
        await reload()
      } catch (err) {
        notify('error', t(errorMessageKey(err)))
      }
    })
  }

  const when = (value: string | null) =>
    value === null ? t('displays.neverUsed') : parseUtc(value).toLocaleString(locale)

  return (
    <div>
      <h1>{t('displays.title')}</h1>
      <p>{t('displays.lead')}</p>
      <p>
        <Link className="link-button" to={APPROVE_PATH}>
          {t('displays.add')}
        </Link>
      </p>
      {devices !== null && devices.length === 0 && <p>{t('displays.empty')}</p>}
      {devices !== null && devices.length > 0 && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t('displays.name')}</th>
                <th>{t('displays.family')}</th>
                <th>{t('displays.addedAt')}</th>
                <th>{t('displays.lastUsed')}</th>
                <th>{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {devices.map((device) => (
                <tr key={device.account_id}>
                  <td>{device.name}</td>
                  <td>{device.family_name}</td>
                  <td>{when(device.created_at)}</td>
                  <td>{when(device.last_used_at)}</td>
                  <td>
                    <ActionButton
                      type="button"
                      className="danger"
                      pending={pendingActionOf(device.account_id) === 'removal'}
                      onClick={() => {
                        remove(device)
                      }}
                    >
                      {t('displays.remove')}
                    </ActionButton>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
