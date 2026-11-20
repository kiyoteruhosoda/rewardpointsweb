import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import { AppUpdatePrompt } from './components/AppUpdatePrompt'
import { MaintenanceGate } from './components/MaintenanceScreen'
import { ToastProvider } from './components/ToastNotification'
import { I18nProvider } from './i18n'
import './index.css'
import { watchForUpdate } from './services/appUpdate'
import {
  checkService,
  currentOutage,
  subscribeOutage,
  watchLazyLoadFailures,
} from './services/maintenance'
import { loadUiSettings, type UiSettings } from './services/uiSettings'
import { AuthProvider } from './store/AuthContext'
import { ThemeProvider } from './theme'

function render(settings: UiSettings) {
  const container = document.getElementById('root')
  if (!container) throw new Error('#root not found in index.html')

  createRoot(container).render(
    <StrictMode>
      <I18nProvider settings={settings}>
        <ThemeProvider settings={settings}>
          <AuthProvider>
            <ToastProvider>
              {/* Show the new-version notice at the very top of every screen (ADR-0059).
                  Place it before the screens so the bar sits above the header. */}
              <AppUpdatePrompt watch={watchForUpdate} />
              <BrowserRouter>
                <App />
              </BrowserRouter>
            </ToastProvider>
          </AuthProvider>
        </ThemeProvider>
      </I18nProvider>
    </StrictMode>,
  )
}

/**
 * Maintenance / outage screen (ADR-0064).
 *
 * WARNING: **Rendered in a root separate from the app**, so it can still be shown when a lazily
 * loaded chunk is missing and the app tree fails. The app screen is hidden, not removed, so on
 * return it comes back as it was, including half-typed input. The root is created the first time
 * it closes (rendered in the language at that moment).
 */
function watchOutage(settings: UiSettings) {
  const app = document.getElementById('root')
  let mounted = false
  const sync = () => {
    const closed = currentOutage() !== null
    if (app) app.hidden = closed
    if (!closed || mounted) return
    mounted = true
    const container = document.createElement('div')
    container.id = 'maintenance-root'
    document.body.append(container)
    createRoot(container).render(
      <StrictMode>
        <I18nProvider settings={settings}>
          <MaintenanceGate check={checkService} />
        </I18nProvider>
      </StrictMode>,
    )
  }
  subscribeOutage(sync)
  sync()
}

watchLazyLoadFailures()

// Fetch the language and theme defaults before rendering. Switching after the fetch
// briefly shows the wrong language/colors on first paint. Render with defaults if the fetch fails.
void loadUiSettings().then((settings) => {
  watchOutage(settings)
  render(settings)
})
