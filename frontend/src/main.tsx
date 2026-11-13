import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import { AppUpdatePrompt } from './components/AppUpdatePrompt'
import { ToastProvider } from './components/ToastNotification'
import { I18nProvider } from './i18n'
import './index.css'
import { watchForUpdate } from './services/appUpdate'
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

// Fetch the language and theme defaults before rendering. Switching after the fetch
// briefly shows the wrong language/colors on first paint. Render with defaults if the fetch fails.
void loadUiSettings().then(render)
