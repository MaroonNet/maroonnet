import './diagnostics/errorLog.ts'  // first, so errors in the imports below are sent too
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MapProvider } from 'react-map-gl/maplibre'
import '@fontsource-variable/schibsted-grotesk'  // the app's two fonts, shipped with it for offline use
import '@fontsource-variable/geist-mono'
import './index.css'
import App from './App.tsx'
import MissionProvider from './mission/MissionProvider.tsx'
import SearchAreaProvider from './searchArea/SearchAreaProvider.tsx'
import SectorsProvider from './sectors/SectorsProvider.tsx'
import SettingsProvider from './settings/SettingsProvider.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SettingsProvider>
      <MissionProvider>
        {/* The map's shared board: any component can reach the map (useMissionMap). */}
        <MapProvider>
          <SearchAreaProvider>
            <SectorsProvider>
              <App />
            </SectorsProvider>
          </SearchAreaProvider>
        </MapProvider>
      </MissionProvider>
    </SettingsProvider>
  </StrictMode>,
)
