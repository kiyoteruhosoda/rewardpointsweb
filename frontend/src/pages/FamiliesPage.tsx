/**
 * 家族への入口。まだどこにも所属していない人だけがここに留まる。
 *
 * 所属できる家族は 1 つまで（ADR-0013）なので、すでに家族があるなら一覧を見せる
 * 意味がない。その場合はそのまま詳細（家族設定）へ送る。作成・参加を出したままに
 * すると、押した先で必ず `already_belongs_to_family` に落ちる。所属を確かめられ
 * なかったとき（読み込み失敗）も同じ理由で出さない。
 *
 * 家族を作れるのは親（member ロール — 保護者の scope 一式）だけで、作った人が
 * owner になる（ADR-0018）。子（guest）は招待コードで加わるので、この画面に
 * 「作る」は出ない。親の招待コードを子が使うとサーバーが断る
 * （guardian_account_required）。
 *
 * すでにアカウントを持つ人がコードを使う経路はここだけ。アカウント作成の画面から
 * ログインを経て来た場合は `?code=` にコードが載っているので、参加の欄へ入れておく。
 *
 * バックアップからの復元（ADR-0025）もここに置く。復元は新しい家族を作る操作で、
 * 所属していない状態からしか行えない — 作成と同じ条件なので、同じ画面に並ぶ。
 */
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'

import { ActionButton } from '../components/ActionButton'
import { FamilyImportPanel } from '../components/FamilyImportPanel'
import { useToast } from '../components/ToastNotification'
import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families } from '../services/families'
import { useAuth } from '../store/AuthContext'
import { useFamily } from '../store/FamilyContext'

export function FamiliesPage() {
  const { t } = useI18n()
  const { hasScope } = useAuth()
  const { notify } = useToast()
  const { family, failed, loading, reload } = useFamily()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const carriedCode = searchParams.get('code')?.trim() ?? ''
  const [name, setName] = useState('')
  const [code, setCode] = useState(carriedCode)

  // 作成は保護者の scope 一式が要る（サーバーの入口と同じ条件 — ADR-0018）
  const canCreate = hasScope('family:view', 'family:manage', 'point:view', 'point:manage')

  const enter = async (familyId: number) => {
    // 先に読み直してから送る。左のナビゲーションと詳細が同時に新しい家族へ変わる。
    await reload()
    navigate(`/families/${String(familyId)}`)
  }

  const [create, creating] = usePendingAction(async (event: FormEvent) => {
    event.preventDefault()
    try {
      const created = await families.create(name)
      setName('')
      await enter(created.id)
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  })

  const [join, joining] = usePendingAction(async (event: FormEvent) => {
    event.preventDefault()
    try {
      const joined = await families.acceptInvitation(code, null)
      setCode('')
      // 使い終えたコードを URL に残さない（再読み込みで案内だけが蘇る）
      if (carriedCode) setSearchParams({}, { replace: true })
      notify('success', t('families.joined'))
      await enter(joined.family_id)
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  })

  if (loading) return <p className="loading">{t('common.loading')}</p>
  // 読めなかっただけかもしれない。所属していないと決めつけて作成・参加を出すと、
  // 押した先で必ず `already_belongs_to_family` になる。
  if (failed) return <p className="error">{t('families.unavailable')}</p>
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
          <form className="inline-form" onSubmit={create}>
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
            <ActionButton type="submit" pending={creating}>
              {t('families.create')}
            </ActionButton>
          </form>
        </section>
      )}

      {/* 復元も家族を作る操作なので、作成と同じ scope を要求する（ADR-0025） */}
      {canCreate && <FamilyImportPanel onImported={enter} />}

      <section className="card">
        <h2>{t('families.join')}</h2>
        {carriedCode ? (
          <p className="notice">{t('families.joinPending')}</p>
        ) : (
          <p>{t('families.joinHint')}</p>
        )}
        <form className="inline-form" onSubmit={join}>
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
          <ActionButton type="submit" pending={joining}>
            {t('families.join')}
          </ActionButton>
        </form>
      </section>
    </div>
  )
}
