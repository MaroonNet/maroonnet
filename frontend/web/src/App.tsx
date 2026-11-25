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
import PeoplePanel from './people/PeoplePanel.tsx'
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
import MeshPanel from './teams/MeshPanel.tsx'
import TeamCard from './teams/TeamCard.tsx'
import TeamsPanel from './teams/TeamsPanel.tsx'
import PlaceWaypoint from './waypoints/PlaceWaypoint.tsx'
import WaypointCard from './waypoints/WaypointCard.tsx'
import WaypointsOnMap from './waypoints/WaypointsOnMap.tsx'
import { useWaypoints, type Waypoint } from './waypoints/waypoints.ts'

// The tools that are greyed, and why: a search area and a waypoint belong to a mission, and
// a sector is drawn inside the search area.
function greyedTools(missionOpen: boolean, hasArea: boolean): Partial<Record<ToolId, string>> | undefined {
  if (!missionOpen) return NO_MISSION
  if (!hasArea) return NO_AREA
  return undefined
}
const NO_MISSION = { 'search-area': 'Open a mission first', sector: 'Open a mission first', waypoint: 'Open a mission first' }
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

  // What is selected: a sector, picked on the map or in the Sectors panel; a team, picked
  // in the Groups & Teams panel; or what one click on the map's waypoints picked, which is
  // several when they sit on the same spot. One thing is selected at a time, and its card
  // shows while no drawing tool has a card of its own up.
  const [selectedSector, setSelectedSector] = useState<number | null>(null)
  const [selectedTeam, setSelectedTeam] = useState<number | null>(null)  // the team's radio
  const [selectedWaypoints, setSelectedWaypoints] = useState<number[]>([])
  function pickSector(id: number | null) {
    setSelectedSector(id)
    setSelectedTeam(null)
    setSelectedWaypoints([])
  }
  function pickTeam(id: number) {
    setSelectedTeam(id)
    setSelectedSector(null)
    setSelectedWaypoints([])
  }
  function pickWaypoints(ids: number[]) {
    setSelectedWaypoints(ids)
    setSelectedSector(null)
    setSelectedTeam(null)
  }
  const drawing = tool === 'sector' || tool === 'search-area' || tool === 'waypoint'
  // The sector whose shape is being edited, from its card's Edit Shape, or the waypoint
  // being edited, from its card's Edit. Picking another tool ends the editing without saving.
  const [editingSector, setEditingSector] = useState<number | null>(null)
  if (editingSector !== null && tool !== 'select') setEditingSector(null)
  const [editingWaypointId, setEditingWaypointId] = useState<number | null>(null)
  if (editingWaypointId !== null && tool !== 'select') setEditingWaypointId(null)
  const editingWaypoint = useWaypoints().waypoints.find((waypoint) => waypoint.id === editingWaypointId)
  const editing = editingSector !== null || editingWaypoint !== undefined
  // A saved change gives the waypoint a new id, so the one that took its place is selected.
  function doneEditingWaypoint(saved?: Waypoint) {
    setEditingWaypointId(null)
    if (saved) setSelectedWaypoints([saved.id])
  }

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
      {openPanel === 'teams' && (
        <Panel title="Groups & Teams" onClose={() => setOpenPanel(null)}>
          <TeamsPanel selected={selectedTeam} onPick={pickTeam} />
        </Panel>
      )}
      {openPanel === 'people' && (
        <Panel title="People" onClose={() => setOpenPanel(null)}>
          <PeoplePanel />
        </Panel>
      )}
      {openPanel === 'sectors' && (
        <Panel title="Sectors" onClose={() => setOpenPanel(null)}>
          <SectorsPanel selected={selectedSector} onPick={pickSector} />
        </Panel>
      )}
      {openPanel === 'area' && (
        <Panel title="Search Area" onClose={() => setOpenPanel(null)}>
          <AreaPanel />
        </Panel>
      )}
      {openPanel === 'mesh' && (
        <Panel title="Mesh" onClose={() => setOpenPanel(null)}>
          <MeshPanel />
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
            onPick={tool === 'select' && !editing ? pickSector : undefined}
            hidden={editingSector}
          />
          <WaypointsOnMap
            selected={selectedWaypoints}
            onPick={tool === 'select' && !editing ? pickWaypoints : undefined}
            hidden={editingWaypointId}
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
          <SectorCard key={selectedSector} id={selectedSector} onClose={() => setSelectedSector(null)} onEdit={setEditingSector} />
        )}
        {selectedTeam !== null && !editing && !drawing && (
          <TeamCard id={selectedTeam} onClose={() => setSelectedTeam(null)} />
        )}
        {/* key: each waypoint edited, and each use of the tool, starts with its own form. */}
        {editingWaypoint ? (
          <PlaceWaypoint key={editingWaypoint.id} editing={editingWaypoint} hintSlot={hintSlot} onDone={doneEditingWaypoint} />
        ) : selectedWaypoints.length > 0 && !drawing && (
          <WaypointCard ids={selectedWaypoints} onPick={pickWaypoints} onClose={() => setSelectedWaypoints([])} onEdit={setEditingWaypointId} />
        )}
        {tool === 'waypoint' && <PlaceWaypoint hintSlot={hintSlot} onDone={() => setTool('select')} />}
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
