/**
 * 家族の一覧。1 つのアカウントが複数の家族に所属できる（ADR-0009）。
 *
 * 家族は所属していない人なら誰でも作れる（`family:view` — ADR-0017）。作った人が
 * その家族の owner になり、保護者の権限へ昇格する。scope はトークンに焼き込まれて
 * いるため、昇格が起きたときは再ログインを促す（ADR-0014 の独立と同じ扱い）。
 */
import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { useToast } from '../components/ToastNotification'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families, type FamilySummary } from '../services/families'
import { useAuth } from '../store/AuthContext'

export function FamiliesPage() {
  const { t } = useI18n()
  const { hasScope, logout } = useAuth()
  const { notify } = useToast()
  const [list, setList] = useState<FamilySummary[] | null>(null)
  const [name, setName] = useState('')
  const [code, setCode] = useState('')

  const canCreate = hasScope('family:view')
  // 保護者に必要な scope の全部（バックエンドの昇格スキップ条件と対）。
  // どれかが欠けていれば、作成・親としての参加でロールが昇格している
  const isGuardian = hasScope('family:view', 'family:manage', 'point:view', 'point:manage')

  const reload = () => families.list().then(setList)

  useEffect(() => {
    void reload().catch(() => {
      setList([])
    })
  }, [])

  const create = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await families.create(name)
      setName('')
      if (!isGuardian) {
        // owner へ昇格したが、いまのトークンには古い scope しか無い
        notify('success', t('families.createdRelogin'))
        logout()
        return
      }
      await reload()
      notify('success', t('common.saved'))
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  const join = async (event: FormEvent) => {
    event.preventDefault()
    try {
      const joined = await families.acceptInvitation(code, null)
      setCode('')
      if (joined.role !== 'child' && !isGuardian) {
        // 親として加わり保護者へ昇格した。新しい scope は再ログインで有効になる
        notify('success', t('families.joinedRelogin'))
        logout()
        return
      }
      await reload()
      notify('success', t('families.joined'))
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  if (list === null) return <p className="loading">{t('common.loading')}</p>

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{t('families.title')}</h1>
      </div>

      <section className="card">
        {list.length === 0 ? (
          <p>{t('families.empty')}</p>
        ) : (
          <div className="link-list">
            {list.map((family) => (
              <Link key={family.id} to={`/families/${family.id}`}>
                {family.name} — {t(`families.role.${family.my_role}`)} (
                {t('families.memberCount', { count: family.member_count })})
              </Link>
            ))}
          </div>
        )}
      </section>

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
