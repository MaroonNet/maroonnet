import { useMission } from './mission.ts'
import MissionList from './MissionList.tsx'
import OpenMissionView from './OpenMissionView.tsx'

// The contents of the Mission panel: the open mission, or with none open, the list of
// missions and the New Mission form.
function MissionPanel() {
    const { mission } = useMission()
    return mission ? <OpenMissionView mission={mission} /> : <MissionList />
}

export default MissionPanel
