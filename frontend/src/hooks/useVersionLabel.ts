import { useEffect, useState } from 'react'

interface Info {
  version: string
  git_sha: string
}

/**
 * Version label. A main build's version is the short SHA itself (`695ff03`), so when it equals the SHA show it only once.
 * No `v` prefix (so `v695ff03` does not look like a version number).
 */
function versionLabel(info: Info): string {
  return info.version === info.git_sha ? info.version : `${info.version} (${info.git_sha})`
}

/** The running version label (from `/info`; empty when unavailable). Used by the footer and the display screen (task #498). */
export function useVersionLabel(): string {
  const [info, setInfo] = useState<Info | null>(null)

  useEffect(() => {
    fetch('/info')
      .then((r) => (r.ok ? r.json() : null))
      .then(setInfo)
      .catch(() => {
        setInfo(null)
      })
  }, [])

  return info ? versionLabel(info) : ''
}
