import { useState } from 'react'
import MapControls from './frame/MapControls.tsx'
import Panel from './frame/Panel.tsx'
import Rail, { type PanelId } from './frame/Rail.tsx'
import Toolbar, { type ToolId } from './frame/Toolbar.tsx'
import LayersPanel from './layers/LayersPanel.tsx'
import MissionMap from './map/MissionMap.tsx'
import { style } from './map/mapStyle.ts'
import type { StyleMetadata } from './map/styleChoices.ts'
import MissionPanel from './mission/MissionPanel.tsx'
import StillRunningBox from './mission/StillRunningBox.tsx'
import { useMission } from './mission/mission.ts'
import AreaPanel from './searchArea/AreaPanel.tsx'
import DrawSearchArea from './searchArea/DrawSearchArea.tsx'
import SearchAreaOutline from './searchArea/SearchAreaOutline.tsx'
import { useMapOverSearchArea } from './searchArea/searchArea.ts'
import SettingsPanel from './settings/SettingsPanel.tsx'

// The tools that are greyed while no mission is open.
const NEEDS_MISSION = { 'search-area': 'Open a mission first' }

// The whole screen: the rail down the left edge, the panel its buttons open, and the map
// filling the rest, with the toolbar over its top left corner.
function App() {
  const [openPanel, setOpenPanel] = useState<PanelId | null>(null)  // one panel is open at a time
  const [tool, setTool] = useState<ToolId>('select')  // the picked map tool
  // The Layers panel changes these two lists and the map draws from them. They are held here
  // so the choices are kept while the panel is closed.
  const [hidden, setHidden] = useState<string[]>([])  // the layer groups the user has hidden
  const [pickedUses, setPickedUses] = useState<string[]>([])  // the trail uses ticked; none: all trails
  // The spot under the toolbar where the tool in use draws its hint line. It is kept as
  // state so the tool is drawn again once the spot exists.
  const [hintSlot, setHintSlot] = useState<HTMLElement | null>(null)
  const { mission } = useMission()

  useMapOverSearchArea(openPanel !== null)

  // A search area belongs to a mission, so its tool needs one open. If the mission is closed
  // while the tool is picked, the toolbar goes back to Select.
  if (!mission && tool === 'search-area') setTool('select')

  // Pressing the open panel's button closes it; pressing another opens that one in its place.
  function pressRailButton(id: PanelId) {
    setOpenPanel(openPanel === id ? null : id)
  }

  const layerLists = style?.metadata as StyleMetadata | undefined  // missing when the style failed to load

  return (
    <div className="relative flex h-full font-sans text-body leading-snug font-semibold text-ink">
      <Rail openPanel={openPanel} onPress={pressRailButton} />
      {openPanel === 'mission' && (
        <Panel title="Mission" onClose={() => setOpenPanel(null)}>
          <MissionPanel />
        </Panel>
      )}
      {openPanel === 'area' && (
        <Panel title="Search Area" onClose={() => setOpenPanel(null)}>
          <AreaPanel />
        </Panel>
      )}
      {openPanel === 'layers' && (
        <Panel title="Map Layers" onClose={() => setOpenPanel(null)}>
          {layerLists ? (
            <LayersPanel
              groups={layerLists.groups}
              hidden={hidden}
              setHidden={setHidden}
              trailUses={layerLists.trail_uses}
              pickedUses={pickedUses}
              setPickedUses={setPickedUses}
            />
          ) : (
            <p className="px-4 py-3 font-medium text-muted">The map's layers could not be loaded.</p>
          )}
        </Panel>
      )}
      {openPanel === 'settings' && (
        <Panel title="Settings" onClose={() => setOpenPanel(null)}>
          <SettingsPanel />
        </Panel>
      )}
      <main className="relative z-0 min-w-0 flex-1">
        <MissionMap hidden={hidden} pickedUses={pickedUses}>
          <SearchAreaOutline />
        </MissionMap>
        {/* What floats over the map's top left corner. It moves right when a panel opens,
            so the panel does not cover it. */}
        <div className={`absolute top-3.5 left-3.5 z-10 flex flex-col items-start gap-2 ${openPanel ? 'translate-x-panel' : ''}`}>
          <Toolbar tool={tool} onPick={setTool} greyed={mission ? undefined : NEEDS_MISSION} />
          <div ref={setHintSlot} />
        </div>
        {tool === 'search-area' && <DrawSearchArea hintSlot={hintSlot} onDone={() => setTool('select')} />}
        <MapControls />
      </main>
      <StillRunningBox />
    </div>
  )
}

export default App
