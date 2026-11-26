import { HEADING } from '../mission/MissionList.tsx'
import { useMission } from '../mission/mission.ts'
import { usePeople } from '../people/people.ts'
import { groupLabel, radioLabel } from '../people/peopleWords.ts'
import type { Radio } from './teams.ts'
import { carriedBy, KIND_LABELS, lastPosition } from './teamWords.ts'

const NOTE = 'px-4 pt-3 font-medium text-muted'  // a line said in place of the lists

// What the Mesh panel shows: every radio of the open mission, in two sets. The command post
// radio and the relays come first, since they are in no team list; the searcher radios
// follow. Each row gives the radio's label, kind and node number, then who carries it, its
// group and the time of its newest position. It only lists: radio health (last heard,
// battery) comes with the radios themselves.
function MeshPanel() {
    const { mission } = useMission()
    const { radios } = usePeople()

    if (!mission) return <p className={NOTE}>No mission is open.</p>
    if (!radios.length) {
        return (
            <>
                <p className="px-4 pt-3">This mission has no radios.</p>
                <p className="px-4 pt-1 font-medium text-muted">A new mission starts with the radios listed in radios.json, in the app data folder.</p>
            </>
        )
    }
    const searchers = radios.filter((radio) => radio.kind === 'searcher')
    // The command post radio first, then the rest by number.
    const others = radios.filter((radio) => radio.kind !== 'searcher')
        .sort((a, b) => Number(b.kind === 'command_post') - Number(a.kind === 'command_post') || a.id - b.id)

    const set = (title: string, shown: Radio[]) => shown.length > 0 && (
        <section className="pb-1.5">
            <h3 className={HEADING}>{title} · {shown.length}</h3>
            <ul aria-label={title}>
                {shown.map((radio) => (
                    <li key={radio.id} className="px-4 py-1.5">
                        <div className="flex items-baseline gap-2">
                            <span className="text-input">{radioLabel(radio.id)}</span>
                            <span className="flex-1 font-mono text-label tracking-widest text-muted uppercase">{KIND_LABELS[radio.kind]}</span>
                            <span className="tabular-nums text-muted" title="Node number">{radio.node_num}</span>
                        </div>
                        {/* Each fact breaks onto the next line whole, never in its middle. */}
                        <div className="font-medium text-muted">
                            {carriedBy(radio, 2)} · <span className="whitespace-nowrap">{groupLabel(radio.group_id)}</span>
                            {' · '}<span className="whitespace-nowrap">{lastPosition(radio, mission.time_zone)}</span>
                        </div>
                    </li>
                ))}
            </ul>
        </section>
    )
    return (
        <div className="pb-3">
            {set('Command post and relays', others)}
            {set('Searcher radios', searchers)}
        </div>
    )
}

export default MeshPanel
