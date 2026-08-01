/**
 * 家族の一覧。1 つのアカウントが複数の家族に所属できる（ADR-0009）。
 *
 * 家族を作れるのは `family:manage` を持つ人だけ。作った人がその家族の owner に
 * なる。子どもは招待コードで加わるので、この画面には「作る」しか無い。
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
  const { hasScope } = useAuth()
  const { notify } = useToast()
  const [list, setList] = useState<FamilySummary[] | null>(null)
  const [name, setName] = useState('')
  const [code, setCode] = useState('')

  const canCreate = hasScope('family:manage')

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
      await reload()
      notify('success', t('common.saved'))
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  const join = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await families.acceptInvitation(code, null)
      setCode('')
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
