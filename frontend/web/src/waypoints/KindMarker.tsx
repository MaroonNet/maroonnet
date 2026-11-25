import { kindOf } from './kinds.ts'

type Props = {
    kind: string        // the kind's code
    small?: boolean     // the size used in a list; otherwise the size used on the map
    ringed?: boolean    // drawn with a ring around it: the selected waypoint
}

const INK = '#201e18', LIGHT = '#fffdf6'  // --color-ink and --color-field in index.css

// A waypoint's marker: a filled circle in its kind's color with the kind's icon inside. The
// same picture is used on the map, in the legend and on the cards.
function KindMarker({ kind, small = false, ringed = false }: Props) {
    const { icon: KindIcon, color, darkIcon } = kindOf(kind)
    return (
        <span
            aria-hidden
            style={{ background: color }}
            className={`inline-flex flex-none items-center justify-center rounded-full border-[1.5px] border-ink/85 shadow-[0_1px_2px_rgb(0_0_0/0.35)] ${small ? 'size-5.5' : 'size-7.5'} ${ringed ? 'outline-[3px] outline-offset-2 outline-ink' : ''}`}
        >
            <KindIcon size={small ? 13 : 18} stroke={2} color={darkIcon ? INK : LIGHT} />
        </span>
    )
}

export default KindMarker
