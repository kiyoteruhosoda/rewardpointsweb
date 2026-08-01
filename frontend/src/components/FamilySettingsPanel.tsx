/**
 * 家族の設定（並び順・改名・脱退・解散）。
 *
 * 出し分けは立場で決める: 改名と解散は owner、脱退と並べ替えは親（owner / parent）。
 * 「他に親が残っているか」「自分以外の参加者がいないか」といった成立条件は
 * サーバーが検証するので（ADR-0013）、ここではエラーコードの文言を出すだけ。
 *
 * 並び順は家族に 1 つで、左のナビゲーションとダッシュボードの両方に効く。
 * 上下に 1 つずつ動かす形にしているのは、指でも掴める操作にするため
 * （ドラッグはキーボードと支援技術から扱いにくい）。
 */
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families, type FamilyDetail } from '../services/families'
import { useToast } from './ToastNotification'

interface Props {
  family: FamilyDetail
  onChanged: () => Promise<void>
}

export function FamilySettingsPanel({ family, onChanged }: Props) {
  const { t } = useI18n()
  const { notify } = useToast()
  const navigate = useNavigate()
  const [name, setName] = useState(family.name)

  const isOwner = family.my_role === 'owner'
  const children = family.memberships.filter((member) => member.role === 'child')

  const fail = (error: unknown) => {
    notify('error', t(errorMessageKey(error)))
  }

  const rename = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await families.rename(family.id, name)
      await onChanged()
      notify('success', t('common.saved'))
    } catch (error) {
      fail(error)
    }
  }

  /** *index* の子を 1 つ上（-1）／下（+1）へ動かす。 */
  const move = async (index: number, delta: number) => {
    const ids = children.map((child) => child.id)
    const here = ids[index]
    const there = ids[index + delta]
    if (here === undefined || there === undefined) return
    ids[index] = there
    ids[index + delta] = here
    try {
      await families.reorderMembers(family.id, ids)
      await onChanged()
    } catch (error) {
      fail(error)
    }
  }

  /** 家族から離れる（脱退・解散）。読み直してから送らないと、消えた家族へ戻される。 */
  const depart = async (leaving: () => Promise<void>, message: string) => {
    try {
      await leaving()
      await onChanged()
      notify('success', t(message))
      navigate('/families')
    } catch (error) {
      fail(error)
    }
  }

  const leave = async () => {
    if (!window.confirm(t('families.confirmLeave', { name: family.name }))) return
    await depart(() => families.leave(family.id), 'families.left')
  }

  const dissolve = async () => {
    if (!window.confirm(t('families.confirmDissolve', { name: family.name }))) return
    await depart(() => families.dissolve(family.id), 'families.dissolved')
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

      {children.length > 1 && (
        <div className="card-inset order-editor">
          <p>{t('families.orderHint')}</p>
          <ul className="order-list">
            {children.map((child, index) => (
              <li key={child.id}>
                <span className="order-list-name">{child.display_name}</span>
                <button
                  type="button"
                  aria-label={t('families.moveUp', { name: child.display_name })}
                  disabled={index === 0}
                  onClick={() => {
                    void move(index, -1)
                  }}
                >
                  ↑
                </button>
                <button
                  type="button"
                  aria-label={t('families.moveDown', { name: child.display_name })}
                  disabled={index === children.length - 1}
                  onClick={() => {
                    void move(index, 1)
                  }}
                >
                  ↓
                </button>
              </li>
            ))}
          </ul>
        </div>
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
            className="danger"
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
