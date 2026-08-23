/** 設定画面の警告: いま開いている URL からパスキーを使えるか。 */
import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { PasskeyDomainNotice } from './PasskeyDomainNotice'

const LOCATION = {
  hostname: 'app.example.com',
  origin: 'https://app.example.com',
  protocol: 'https:',
}

describe('PasskeyDomainNotice', () => {
  it('噛み合っていれば何も出さない', () => {
    renderWithProviders(
      <PasskeyDomainNotice
        settings={{ rpId: 'app.example.com', origin: 'https://app.example.com' }}
        envLocked={false}
        location={LOCATION}
        onApply={vi.fn()}
      />,
    )
    expect(screen.queryByText(/Passkeys cannot be used/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('食い違っていれば、現在の値と開いている URL を出す', () => {
    renderWithProviders(
      <PasskeyDomainNotice
        settings={{ rpId: 'localhost', origin: 'http://localhost:5173' }}
        envLocked={false}
        location={LOCATION}
        onApply={vi.fn()}
      />,
    )
    const notice = screen.getByText(/Passkeys cannot be used/)
    expect(notice).toHaveTextContent('https://app.example.com')
    expect(notice).toHaveTextContent('localhost')
    expect(notice).toHaveTextContent('http://localhost:5173')
  })

  it('「合わせる」は開いている URL の値を返す（保存はしない）', () => {
    const onApply = vi.fn()
    renderWithProviders(
      <PasskeyDomainNotice
        settings={{ rpId: 'localhost', origin: 'http://localhost:5173' }}
        envLocked={false}
        location={LOCATION}
        onApply={onApply}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /Match the URL/ }))
    expect(onApply).toHaveBeenCalledWith({
      rpId: 'app.example.com',
      origin: 'https://app.example.com',
    })
  })

  it('環境変数で固定されていれば、直し方だけを出す（ボタンは出さない）', () => {
    renderWithProviders(
      <PasskeyDomainNotice
        settings={{ rpId: 'localhost', origin: 'http://localhost:5173' }}
        envLocked
        location={LOCATION}
        onApply={vi.fn()}
      />,
    )
    expect(screen.getByText(/environment variables/)).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('IP アドレスで開いていれば、合わせるボタンではなく開き直し方を出す', () => {
    // その URL に合わせた値は保存できない（RP ID にドメイン名しか使えない）
    renderWithProviders(
      <PasskeyDomainNotice
        settings={{ rpId: 'localhost', origin: 'http://localhost:5173' }}
        envLocked={false}
        location={{ hostname: '192.168.1.5', origin: 'http://192.168.1.5', protocol: 'http:' }}
        onApply={vi.fn()}
      />,
    )
    expect(screen.getByText(/cannot be used from this URL at all/)).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('値が噛み合っていても、その URL でパスキーが動かなければ出す', () => {
    // http のドメイン名は安全な文脈ではなく、サーバーもこのオリジンを弾く。
    // 噛み合わせだけを見て黙ると、失敗するのは利用者の「パスキーを追加」になる。
    renderWithProviders(
      <PasskeyDomainNotice
        settings={{ rpId: 'nas.local', origin: 'http://nas.local' }}
        envLocked
        location={{ hostname: 'nas.local', origin: 'http://nas.local', protocol: 'http:' }}
        onApply={vi.fn()}
      />,
    )
    expect(screen.getByText(/cannot be used from this URL at all/)).toBeInTheDocument()
  })

  it('既定ポートが書かれているだけの設定は食い違いにしない', () => {
    // サーバーは RP を組み立てるときに `:443` を落とす。この設定は動く。
    renderWithProviders(
      <PasskeyDomainNotice
        settings={{ rpId: 'app.example.com', origin: 'https://app.example.com:443' }}
        envLocked={false}
        location={LOCATION}
        onApply={vi.fn()}
      />,
    )
    expect(screen.queryByText(/Passkeys cannot be used/)).not.toBeInTheDocument()
  })

  it('未設定でも空白ではなく分かる形で出す', () => {
    renderWithProviders(
      <PasskeyDomainNotice
        settings={{ rpId: '', origin: '' }}
        envLocked={false}
        location={LOCATION}
        onApply={vi.fn()}
      />,
    )
    expect(screen.getByText(/“—”/)).toBeInTheDocument()
  })
})
