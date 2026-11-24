import './diagnostics/errorLog.ts'  // first, so errors in the imports below are sent too
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/schibsted-grotesk'  // the app's two fonts, shipped with it for offline use
import '@fontsource-variable/geist-mono'
import './index.css'
import App from './App.tsx'
import MissionProvider from './mission/MissionProvider.tsx'
import SettingsProvider from './settings/SettingsProvider.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SettingsProvider>
      <MissionProvider>
        <App />
      </MissionProvider>
    </SettingsProvider>
  </StrictMode>,
)
