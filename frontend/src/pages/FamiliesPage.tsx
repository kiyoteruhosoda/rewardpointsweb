/**
 * 家族への入口。まだどこにも所属していない人だけがここに留まる。
 *
 * 所属できる家族は 1 つまで（ADR-0013）なので、すでに家族があるなら一覧を見せる
 * 意味がない。その場合はそのまま詳細（家族設定）へ送る。作成・参加を出したままに
 * すると、押した先で必ず `already_belongs_to_family` に落ちる。
 *
 * 家族を作れるのは親（member ロール — 保護者の scope 一式）だけで、作った人が
 * owner になる（ADR-0018）。子（guest）は招待コードで加わるので、この画面に
 * 「作る」は出ない。親の招待コードを子が使うとサーバーが断る
 * （guardian_account_required）。
 */
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { useToast } from '../components/ToastNotification'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families } from '../services/families'
import { useAuth } from '../store/AuthContext'
import { useFamily } from '../store/FamilyContext'

export function FamiliesPage() {
  const { t } = useI18n()
  const { hasScope } = useAuth()
  const { notify } = useToast()
  const { family, loading, reload } = useFamily()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [code, setCode] = useState('')

  // 作成は保護者の scope 一式が要る（サーバーの入口と同じ条件 — ADR-0018）
  const canCreate = hasScope('family:view', 'family:manage', 'point:view', 'point:manage')

  const enter = async (familyId: number) => {
    // 先に読み直してから送る。左のナビゲーションと詳細が同時に新しい家族へ変わる。
    await reload()
    navigate(`/families/${String(familyId)}`)
  }

  const create = async (event: FormEvent) => {
    event.preventDefault()
    try {
      const created = await families.create(name)
      setName('')
      await enter(created.id)
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  const join = async (event: FormEvent) => {
    event.preventDefault()
    try {
      const joined = await families.acceptInvitation(code, null)
      setCode('')
      notify('success', t('families.joined'))
      await enter(joined.family_id)
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  if (loading) return <p className="loading">{t('common.loading')}</p>
  if (family) return <Navigate to={`/families/${String(family.id)}`} replace />

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{t('families.setUp')}</h1>
        <p className="page-subtitle">{t('families.empty')}</p>
      </div>

      {canCreate && (
        <section className="card">
          <h2>{t('families.create')}</h2>
          <form
            className="inline-form"
            onSubmit={(event) => {
              void create(event)
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
            <button type="submit">{t('families.create')}</button>
          </form>
        </section>
      )}

      <section className="card">
        <h2>{t('families.join')}</h2>
        <p>{t('families.joinHint')}</p>
        <form
          className="inline-form"
          onSubmit={(event) => {
            void join(event)
          }}
        >
          <label>
            {t('families.code')}
            <input
              value={code}
              onChange={(event) => {
                setCode(event.target.value)
              }}
              required
            />
          </label>
          <button type="submit">{t('families.join')}</button>
        </form>
      </section>
    </div>
  )
}
