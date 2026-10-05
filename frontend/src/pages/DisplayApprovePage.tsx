/**
 * 表示端末を承認する（運用管理者。`display:approve`。ADR-0047）。
 *
 * 表示端末の QR コードから開くと、確認コードが URL の `#` の後ろに載って入力済みになる
 * （ADR-0025 と同じく、コードをサーバーのログ・Referer に載せない）。ログインして
 * いなければ、ログインの後にこの画面へ戻ってくる（`RequireAuth` が行き先を覚える）。
 */
import { useEffect, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { ActionButton } from '../components/ActionButton'
import { useToast } from '../components/ToastNotification'
import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import {
  approvePairing,
  listDisplayableFamilies,
  userCodeFromHash,
  type DisplayableFamily,
} from '../services/display'

const LIST_PATH = '/admin/displays'

export function DisplayApprovePage() {
  const { t } = useI18n()
  const { notify } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const [code, setCode] = useState(() => userCodeFromHash(location.hash))
  const [familyId, setFamilyId] = useState('')
  const [name, setName] = useState('')
  const [choices, setChoices] = useState<DisplayableFamily[] | null>(null)

  useEffect(() => {
    listDisplayableFamilies()
      .then((loaded) => {
        setChoices(loaded)
        // 1 家族しか無ければ選ばせない
        const only = loaded.length === 1 ? loaded[0] : undefined
        if (only) setFamilyId(String(only.id))
      })
      .catch((err: unknown) => {
        notify('error', t(errorMessageKey(err)))
      })
  }, [notify, t])

  const [approve, approving] = usePendingAction(async (e: FormEvent) => {
    e.preventDefault()
    try {
      const approved = await approvePairing({
        user_code: code,
        family_id: Number(familyId),
        name: name.trim(),
      })
      notify('success', t('displays.approved', { name: approved.name }))
      navigate(LIST_PATH)
    } catch (err) {
      notify('error', t(errorMessageKey(err)))
    }
  })

  return (
    <div>
      <h1>{t('displays.approveTitle')}</h1>
      <p>{t('displays.approveLead')}</p>
      {choices !== null && choices.length === 0 ? (
        <p>{t('displays.noFamilies')}</p>
      ) : (
        <form className="card" onSubmit={approve}>
          <label>
            {t('displays.code')}
            <input
              value={code}
              onChange={(e) => {
                setCode(e.target.value)
              }}
              autoCapitalize="characters"
              autoComplete="off"
              spellCheck={false}
              required
            />
          </label>
          <label>
            {t('displays.family')}
            <select
              value={familyId}
              onChange={(e) => {
                setFamilyId(e.target.value)
              }}
              required
            >
              <option value="">{t('displays.chooseFamily')}</option>
              {(choices ?? []).map((family) => (
                <option key={family.id} value={family.id}>
                  {family.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t('displays.name')}
            <input
              value={name}
              onChange={(e) => {
                setName(e.target.value)
              }}
              placeholder={t('displays.namePlaceholder')}
              maxLength={100}
              required
            />
          </label>
          <div className="form-actions">
            <ActionButton type="submit" pending={approving}>
              {t('displays.approve')}
            </ActionButton>
            <button
              type="button"
              onClick={() => {
                navigate(LIST_PATH)
              }}
            >
              {t('common.cancel')}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
