/**
 * Splits a long list into pages (previous / next).
 *
 * Shows nothing when there is only one page. How pages are counted (how many items each) is decided
 * by the caller via `usePaged`; this component only handles the buttons and "which page we are on".
 */
import { useI18n } from '../i18n'

interface Props {
  page: number
  pageCount: number
  onChange: (page: number) => void
}

export function Pager({ page, pageCount, onChange }: Props) {
  const { t } = useI18n()
  if (pageCount <= 1) return null

  return (
    <nav className="pager" aria-label={t('pager.label')}>
      <button
        type="button"
        disabled={page <= 1}
        onClick={() => {
          onChange(page - 1)
        }}
      >
        {t('pager.previous')}
      </button>
      <span className="pager-position" aria-live="polite">
        {t('pager.position', { page, count: pageCount })}
      </span>
      <button
        type="button"
        disabled={page >= pageCount}
        onClick={() => {
          onChange(page + 1)
        }}
      >
        {t('pager.next')}
      </button>
    </nav>
  )
}
