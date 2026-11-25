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
import MeasureTool from './measure/MeasureTool.tsx'
import { useMission } from './mission/mission.ts'
import AreaPanel from './searchArea/AreaPanel.tsx'
import DrawSearchArea from './searchArea/DrawSearchArea.tsx'
import SearchAreaOutline from './searchArea/SearchAreaOutline.tsx'
import { useMapOverSearchArea, useSearchArea } from './searchArea/searchArea.ts'
import type { SectorShape } from './map/drawSector.ts'
import DrawSector from './sectors/DrawSector.tsx'
import EditSectorShape from './sectors/EditSectorShape.tsx'
import SectorCard from './sectors/SectorCard.tsx'
import SectorsPanel from './sectors/SectorsPanel.tsx'
import SectorsOnMap from './sectors/SectorsOnMap.tsx'
import SettingsPanel from './settings/SettingsPanel.tsx'

// The tools that are greyed, and why: a search area belongs to a mission, and a sector is
// drawn inside the search area.
function greyedTools(missionOpen: boolean, hasArea: boolean): Partial<Record<ToolId, string>> | undefined {
  if (!missionOpen) return NO_MISSION
  if (!hasArea) return NO_AREA
  return undefined
}
const NO_MISSION = { 'search-area': 'Open a mission first', sector: 'Open a mission first' }
const NO_AREA = { sector: 'Draw a search area first' }

// The whole screen: the rail down the left edge, the panel its buttons open, and the map
// filling the rest, with the toolbar over its top left corner.
function App() {
  const [openPanel, setOpenPanel] = useState<PanelId | null>(null)  // one panel is open at a time
  const [tool, setTool] = useState<ToolId>('select')  // the picked map tool
  const [sectorShape, setSectorShape] = useState<SectorShape>('rectangle')  // what Draw Sector draws; kept until changed
  // The Layers panel changes these two lists and the map draws from them. They are held here
  // so the choices are kept while the panel is closed.
  const [hidden, setHidden] = useState<string[]>([])  // the layer groups the user has hidden
  const [pickedUses, setPickedUses] = useState<string[]>([])  // the trail uses ticked; none: all trails
  // The spot under the toolbar where the tool in use draws its hint line, and the spot at the
  // toolbar's end where it puts buttons of its own. They are kept as state so the tool is
  // drawn again once the spots exist.
  const [hintSlot, setHintSlot] = useState<HTMLElement | null>(null)
  const [toolSlot, setToolSlot] = useState<HTMLElement | null>(null)
  const { mission } = useMission()
  const { area } = useSearchArea()

  useMapOverSearchArea(openPanel !== null)

  // If the picked tool becomes greyed, as when the mission is closed while it is in use, the
  // toolbar goes back to Select.
  const greyed = greyedTools(mission !== null, area !== null)
  if (greyed?.[tool]) setTool('select')

  // The selected sector, picked on the map or in the Sectors panel. Its card shows while no
  // drawing tool has a card of its own up.
  const [selectedSector, setSelectedSector] = useState<number | null>(null)
  const drawing = tool === 'sector' || tool === 'search-area'
  // The sector whose shape is being edited, from its card's Edit Shape. Picking another
  // tool ends the editing without saving.
  const [editingSector, setEditingSector] = useState<number | null>(null)
  if (editingSector !== null && tool !== 'select') setEditingSector(null)

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
      {openPanel === 'sectors' && (
        <Panel title="Sectors" onClose={() => setOpenPanel(null)}>
          <SectorsPanel selected={selectedSector} onPick={setSelectedSector} />
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
          <SectorsOnMap
            selected={selectedSector}
            onPick={tool === 'select' && editingSector === null ? setSelectedSector : undefined}
            hidden={editingSector}
          />
          {tool === 'measure' && <MeasureTool hintSlot={hintSlot} />}
        </MissionMap>
        {/* What floats over the map's top left corner. It moves right when a panel opens,
            so the panel does not cover it. */}
        <div className={`absolute top-3.5 left-3.5 z-10 flex flex-col items-start gap-2 ${openPanel ? 'translate-x-panel' : ''}`}>
          <Toolbar tool={tool} onPick={setTool} greyed={greyed} sectorShape={sectorShape} onPickShape={setSectorShape}>
            {/* "contents": the spot takes no room of its own; what is put in it sits in the row. */}
            <div ref={setToolSlot} className="contents" />
          </Toolbar>
          <div ref={setHintSlot} />
        </div>
        {tool === 'search-area' && <DrawSearchArea hintSlot={hintSlot} onDone={() => setTool('select')} />}
        {editingSector !== null ? (
          <EditSectorShape id={editingSector} hintSlot={hintSlot} onClose={() => setEditingSector(null)} />
        ) : selectedSector !== null && !drawing && (
          <SectorCard id={selectedSector} onClose={() => setSelectedSector(null)} onEdit={setEditingSector} />
        )}
        {/* key: picking the other shape starts the tool afresh. */}
        {tool === 'sector' && (
          <DrawSector key={sectorShape} shape={sectorShape} hintSlot={hintSlot} toolSlot={toolSlot} onDone={() => setTool('select')} />
        )}
        <MapControls />
      </main>
      <StillRunningBox />
    </div>
  )
}

export default App
