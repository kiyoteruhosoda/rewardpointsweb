/**
 * 家族の設定（改名・脱退・解散）。
 *
 * 出し分けは立場で決める: 改名と解散は owner、脱退は親（owner / parent）。
 * 「他に親が残っているか」「自分以外の参加者がいないか」といった成立条件は
 * サーバーが検証するので（ADR-0013）、ここではエラーコードの文言を出すだけ。
 */
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families, type FamilyDetail } from '../services/families'
import { useToast } from './ToastNotification'

interface Props {
  family: FamilyDetail
  onRenamed: () => Promise<void>
}

export function FamilySettingsPanel({ family, onRenamed }: Props) {
  const { t } = useI18n()
  const { notify } = useToast()
  const navigate = useNavigate()
  const [name, setName] = useState(family.name)

  const isOwner = family.my_role === 'owner'

  const rename = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await families.rename(family.id, name)
      await onRenamed()
      notify('success', t('common.saved'))
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  const leave = async () => {
    if (!window.confirm(t('families.confirmLeave', { name: family.name }))) return
    try {
      await families.leave(family.id)
      notify('success', t('families.left'))
      navigate('/families')
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  const dissolve = async () => {
    if (!window.confirm(t('families.confirmDissolve', { name: family.name }))) return
    try {
      await families.dissolve(family.id)
      notify('success', t('families.dissolved'))
      navigate('/families')
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  return (
    <section className="card">
      <h2>{t('families.settings')}</h2>

      {isOwner && (
        <form
          className="inline-form"
          onSubmit={(event) => {
            void rename(event)
          }}
        >
          <label>
            {t('families.name')}
            <input
              value={name}
              onChange={(event) => {
                setName(event.target.value)
              }}
              required
            />
          </label>
          <button type="submit">{t('families.rename')}</button>
        </form>
      )}

      <p>{t('families.leaveHint')}</p>
      <button
        type="button"
        onClick={() => {
          void leave()
        }}
      >
        {t('families.leave')}
      </button>

      {isOwner && (
        <>
          <p>{t('families.dissolveHint')}</p>
          <button
            type="button"
            onClick={() => {
              void dissolve()
            }}
          >
            {t('families.dissolve')}
          </button>
        </>
      )}
    </section>
  )
}
