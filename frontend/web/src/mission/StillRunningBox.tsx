import { useState } from 'react'
import ConfirmBox from '../frame/ConfirmBox.tsx'
import { continueSession, endSession, useMission } from './mission.ts'

// The question asked when the app opens and finds the last mission's session still active:
// continue it, or end the session now. It shows until one of the two is chosen.
function StillRunningBox() {
    const { mission, run } = useMission()
    const [failure, setFailure] = useState('')  // why the choice could not be saved

    if (!mission?.asks_to_continue) return null
    return (
        <ConfirmBox
            title={`Session ${mission.session} is still running`}
            choices={[
                { label: 'End Session now', onPress: async () => setFailure(await run(endSession())) },
                { label: 'Continue', main: true, onPress: async () => setFailure(await run(continueSession())) },
            ]}
        >
            {mission.name} was not ended before the app was closed.
            {failure && <p role="alert" className="pt-2 text-red">{failure}</p>}
        </ConfirmBox>
    )
}

export default StillRunningBox
