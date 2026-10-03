import { useEffect, useState } from 'react'

interface Info {
  version: string
  git_sha: string
}

/**
 * 版の表示。main の版は短い SHA そのもの（`695ff03`）なので、SHA と同じなら 1 度だけ出す。
 * 前に `v` は付けない（`v695ff03` のように版の番号に見せない）。
 */
function versionLabel(info: Info): string {
  return info.version === info.git_sha ? info.version : `${info.version} (${info.git_sha})`
}

export function Footer() {
  const [info, setInfo] = useState<Info | null>(null)

  useEffect(() => {
    fetch('/info')
      .then((r) => (r.ok ? r.json() : null))
      .then(setInfo)
      .catch(() => {
        setInfo(null)
      })
  }, [])

  return <footer className="footer">{info ? versionLabel(info) : ''}</footer>
}
