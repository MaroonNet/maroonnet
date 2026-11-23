import { useState } from 'react'
import Panel from './frame/Panel.tsx'
import Rail, { type PanelId } from './frame/Rail.tsx'
import MissionMap from './map/MissionMap.tsx'

// The whole screen: the rail down the left edge, the panel its buttons open, and the map
// filling the rest.
function App() {
  const [openPanel, setOpenPanel] = useState<PanelId | null>(null)  // one panel is open at a time

  // Pressing the open panel's button closes it; pressing another opens that one in its place.
  function pressRailButton(id: PanelId) {
    setOpenPanel(openPanel === id ? null : id)
  }

  return (
    <div className="relative flex h-full font-sans text-body leading-snug font-semibold text-ink">
      <Rail openPanel={openPanel} onPress={pressRailButton} />
      {openPanel === 'layers' && <Panel title="Map Layers" onClose={() => setOpenPanel(null)} />}
      <main className="relative z-0 min-w-0 flex-1">
        <MissionMap />
      </main>
    </div>
  )
}

export default App
