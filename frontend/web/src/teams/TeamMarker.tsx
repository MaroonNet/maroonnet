import { groupColor, groupMapName, mapName, teamColor } from './teamWords.ts'
import type { Radio } from './teams.ts'

type Props = {
    radio: Radio        // the team's radio
    ringed?: boolean    // drawn with a ring around it: the selected team
}

const EDGE = 'border-field shadow-[0_1px_2px_rgb(0_0_0/0.35)]'  // the white border and the shadow

// A team's marker: a dot in its group's color, grey for a team in no group, edged in white.
// On the map it is on the team's position, with its pill beside it; it also starts the
// team's row in a list.
function TeamMarker({ radio, ringed = false }: Props) {
    return (
        <span
            aria-hidden
            style={{ background: teamColor(radio.group_id) }}
            className={`inline-flex size-3.5 flex-none rounded-full border-2 ${EDGE} ${ringed ? 'outline-[3px] outline-offset-2 outline-ink' : ''}`}
        />
    )
}

// A team's pill on the map: its group on the group's color, then its radio, "G2 R3". A team
// in no group has the radio part only, "R4".
export function TeamPill({ radio }: { radio: Radio }) {
    return (
        <span aria-hidden className={`flex overflow-hidden rounded-full border-[1.5px] font-sans text-[11px] leading-none font-bold whitespace-nowrap ${EDGE}`}>
            {radio.group_id !== null && (
                <span style={{ background: groupColor(radio.group_id) }} className="px-1.5 py-[3px] text-field">{groupMapName(radio.group_id)}</span>
            )}
            <span className="bg-field px-1.5 py-[3px] text-ink">{mapName(radio.id)}</span>
        </span>
    )
}

export default TeamMarker
