import { kindOf } from './kinds.ts'

type Props = {
    kind: string        // the kind's code
    pin?: boolean       // drawn as a pin, for the map; otherwise a circle, for a list or a card
    small?: boolean     // the circle's size in a list; otherwise its size on a card
    ringed?: boolean    // drawn with a ring around it: the selected waypoint
}

const INK = '#201e18', LIGHT = '#fffdf6'  // --color-ink and --color-field in index.css

// The pin: a round head HEAD across, with a short point below it whose tip is at the bottom
// edge, so the tip is the spot on the map. The rest follows from HEAD: the pin is 1.3 times
// as tall as the head is wide, the icon 0.6 of the head, and the point leaves the head 27
// degrees either side of straight down. EDGE is the white border's width.
const HEAD = 24, EDGE = 1.5
const TALL = Math.round(HEAD * 1.3), ICON = Math.round(HEAD * 0.6)
const RADIUS = (HEAD - EDGE) / 2, MIDDLE = HEAD / 2
const SIDE = (RADIUS * Math.sin(27 * Math.PI / 180)).toFixed(2)
const JOIN = (MIDDLE + RADIUS * Math.cos(27 * Math.PI / 180)).toFixed(2)
const PIN = `M${MIDDLE} ${TALL - EDGE / 2} L${MIDDLE + +SIDE} ${JOIN} A${RADIUS} ${RADIUS} 0 1 0 ${MIDDLE - +SIDE} ${JOIN} Z`

// A waypoint's marker in its kind's color with the kind's icon inside, edged in white. On the
// map it is a pin; in the legend and on the cards it is a circle.
function KindMarker({ kind, pin = false, small = false, ringed = false }: Props) {
    const { icon: KindIcon, color, darkIcon } = kindOf(kind)
    const iconColor = darkIcon ? INK : LIGHT
    if (pin) return (
        <span aria-hidden style={{ width: HEAD, height: TALL }} className="relative flex flex-none">
            {ringed && <span style={{ width: HEAD, height: HEAD }} className="absolute top-0 left-0 rounded-full outline-[3px] outline-offset-2 outline-ink" />}
            <svg data-outline width={HEAD} height={TALL} viewBox={`0 0 ${HEAD} ${TALL}`} className="absolute inset-0 drop-shadow-[0_1px_2px_rgb(0_0_0/0.35)]">
                <path d={PIN} fill={color} stroke={LIGHT} strokeWidth={EDGE} strokeLinejoin="round" />
            </svg>
            <span style={{ width: HEAD, height: HEAD }} className="absolute top-0 left-0 flex items-center justify-center">
                <KindIcon size={ICON} stroke={2} color={iconColor} />
            </span>
        </span>
    )
    return (
        <span
            aria-hidden
            style={{ background: color }}
            className={`inline-flex flex-none items-center justify-center rounded-full border-[1.5px] border-field shadow-[0_1px_2px_rgb(0_0_0/0.35)] ${small ? 'size-5.5' : 'size-7.5'} ${ringed ? 'outline-[3px] outline-offset-2 outline-ink' : ''}`}
        >
            <KindIcon size={small ? 13 : 18} stroke={2} color={iconColor} />
        </span>
    )
}

export default KindMarker
