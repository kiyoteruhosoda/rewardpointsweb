/**
 * Family settings (rules, order, rename, leave, disband).
 *
 * What is shown depends on role: rename and disband for owner; rules, leave and reordering for parents
 * (owner / parent).
 * Preconditions such as "is another parent left" or "are there no participants besides me" are
 * validated by the server (ADR-0013), so here we only show the text for the error code.
 *
 * There is one order per family, and it applies to both the left navigation and the dashboard.
 * Moving one step up/down at a time is chosen so it can be done with a finger too
 * (dragging is hard to use from the keyboard and assistive technology).
 *
 * Rules (family agreements; ADR-0027) are also one per family. This is the only place to write them;
 * the same text appears read-only on the children's ledgers.
 */
import { useState, type SubmitEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families, type FamilyDetail } from '../services/families'
import { useAuth } from '../store/AuthContext'
import { ActionButton } from './ActionButton'
import { useToast } from './ToastNotification'

interface Props {
  family: FamilyDetail
  onChanged: () => Promise<void>
}

export function FamilySettingsPanel({ family, onChanged }: Props) {
  const { t } = useI18n()
  const { notify } = useToast()
  const { hasScope } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState(family.name)
  const [rules, setRules] = useState(family.rules ?? '')
  // Child and direction being reordered. Up/down arrows point at the same child, so to mark only the
  // pressed one we also need to keep "which way it is moving".
  const [moving, setMoving] = useState<{ childId: number; delta: number } | null>(null)

  const isOwner = family.my_role === 'owner'
  const children = family.memberships.filter((member) => member.role === 'child')

  const fail = (error: unknown) => {
    notify('error', t(errorMessageKey(error)))
  }

  const [rename, renaming] = usePendingAction(async (event: SubmitEvent) => {
    event.preventDefault()
    try {
      await families.rename(family.id, name)
      await onChanged()
      notify('success', t('common.saved'))
    } catch (error) {
      fail(error)
    }
  })

  const [saveRules, savingRules] = usePendingAction(async (event: SubmitEvent) => {
    event.preventDefault()
    try {
      await families.setRules(family.id, rules)
      await onChanged()
      notify('success', t('common.saved'))
    } catch (error) {
      fail(error)
    }
  })

  /** Moves the child at *index* one step up (-1) / down (+1). */
  const move = async (index: number, delta: number) => {
    const ids = children.map((child) => child.id)
    const here = ids[index]
    const there = ids[index + delta]
    if (here === undefined || there === undefined) return
    if (moving !== null) return
    ids[index] = there
    ids[index + delta] = here
    setMoving({ childId: here, delta })
    try {
      await families.reorderMembers(family.id, ids)
      await onChanged()
    } catch (error) {
      fail(error)
    } finally {
      setMoving(null)
    }
  }

  /** Whether the pressed arrow (child x direction) is running. */
  const isMoving = (childId: number, delta: number) =>
    moving !== null && moving.childId === childId && moving.delta === delta

  /** Leaves the family (leave/disband). Without reloading before sending, you'd be sent back to a deleted family. */
  const depart = async (leaving: () => Promise<void>, message: string) => {
    try {
      await leaving()
      await onChanged()
      notify('success', t(message))
      void navigate('/families')
    } catch (error) {
      fail(error)
    }
  }

  const [leave, leaving] = usePendingAction(async () => {
    if (!window.confirm(t('families.confirmLeave', { name: family.name }))) return
    await depart(() => families.leave(family.id), 'families.left')
  })

  const [dissolve, dissolving] = usePendingAction(async () => {
    if (!window.confirm(t('families.confirmDissolve', { name: family.name }))) return
    await depart(() => families.dissolve(family.id), 'families.dissolved')
  })

  return (
    <section className="card">
      <h2>{t('families.settings')}</h2>

      {isOwner && (
        <form className="inline-form" onSubmit={rename}>
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
          <ActionButton type="submit" pending={renaming}>
            {t('families.rename')}
          </ActionButton>
        </form>
      )}

      {/* Family agreements (ADR-0027). Parents can write them (not limited to owner, unlike
          rename). The same text appears on children's ledgers, so this is the single source.
          Check scope in addition to role — so that after an operator edits a role's permissions, no
          input remains that would always 403 when pressed (same idea as ADR-0019) */}
      {hasScope('family:manage') && (
        <form className="card-inset family-rules-form" onSubmit={saveRules}>
          <label>
            {t('families.rules')}
            <textarea
              rows={5}
              value={rules}
              placeholder={t('families.rulesPlaceholder')}
              onChange={(event) => {
                setRules(event.target.value)
              }}
            />
          </label>
          <p className="field-hint">{t('families.rulesHint')}</p>
          <ActionButton type="submit" pending={savingRules}>
            {t('common.save')}
          </ActionButton>
        </form>
      )}

      {children.length > 1 && (
        <div className="card-inset order-editor">
          <p>{t('families.orderHint')}</p>
          <ul className="order-list">
            {children.map((child, index) => (
              <li key={child.id}>
                <span className="order-list-name">{child.display_name}</span>
                <ActionButton
                  type="button"
                  aria-label={t('families.moveUp', { name: child.display_name })}
                  pending={isMoving(child.id, -1)}
                  disabled={index === 0 || moving !== null}
                  onClick={() => {
                    void move(index, -1)
                  }}
                >
                  ↑
                </ActionButton>
                <ActionButton
                  type="button"
                  aria-label={t('families.moveDown', { name: child.display_name })}
                  pending={isMoving(child.id, 1)}
                  disabled={index === children.length - 1 || moving !== null}
                  onClick={() => {
                    void move(index, 1)
                  }}
                >
                  ↓
                </ActionButton>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p>{t('families.leaveHint')}</p>
      <ActionButton type="button" pending={leaving} onClick={leave}>
        {t('families.leave')}
      </ActionButton>

      {isOwner && (
        <>
          <p>{t('families.dissolveHint')}</p>
          <ActionButton type="button" className="danger" pending={dissolving} onClick={dissolve}>
            {t('families.dissolve')}
          </ActionButton>
        </>
      )}
    </section>
  )
}
