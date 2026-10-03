/**
 * 長い一覧をページに分けて送る（前へ・次へ）。
 *
 * 1 ページしか無いときは何も出さない。ページの数え方（何件ずつか）は呼び出し側が
 * `usePaged` で決め、この部品は送るボタンと「いま何ページ目か」だけを受け持つ。
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
