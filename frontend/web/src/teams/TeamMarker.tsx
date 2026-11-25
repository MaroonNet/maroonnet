import { mapName, teamColor } from './teamWords.ts'
import type { Radio } from './teams.ts'

type Props = {
    radio: Radio        // the team's radio
    small?: boolean     // the size used in a list; otherwise the size used on the map
    ringed?: boolean    // drawn with a ring around it: the selected team
}

// A team's marker: a filled circle in its group's color, grey for a team in no group, with
// the team's short name inside. The same picture is used on the map and on the cards.
function TeamMarker({ radio, small = false, ringed = false }: Props) {
    return (
        <span
            aria-hidden
            style={{ background: teamColor(radio.group_id) }}
            className={`inline-flex flex-none items-center justify-center rounded-full border-[1.5px] border-ink/85 font-sans leading-none font-bold text-field shadow-[0_1px_2px_rgb(0_0_0/0.35)] ${small ? 'size-5.5 text-[9px]' : 'size-7.5 text-[11px]'} ${ringed ? 'outline-[3px] outline-offset-2 outline-ink' : ''}`}
        >
            {mapName(radio.id)}
        </span>
    )
}

export default TeamMarker
