import { useVersionLabel } from '../hooks/useVersionLabel'

export function Footer() {
  return <footer className="footer">{useVersionLabel()}</footer>
}
