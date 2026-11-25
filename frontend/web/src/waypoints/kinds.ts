import {
    IconAlertTriangle, IconAntenna, IconEye, IconHelicopterLanding, IconHome, IconMapPin, IconMapPinQuestion,
    IconUserCheck, IconUsers, IconZoomExclamation, type Icon,
} from '@tabler/icons-react'

// The kinds of waypoint, and how each looks: a marker in the kind's color with its icon
// inside (KindMarker draws it). Two pairs share a color and differ by icon.
export type Kind = {
    code: string        // the database's word for it (waypoint_type.type_code)
    label: string       // its name on screen
    icon: Icon
    color: string
    darkIcon: boolean   // the color is light, so the icon is drawn dark
}

const BLACK = '#201e18', WHITE = '#fffdf6'
const RED = 'oklch(0.55 0.19 27)', ORANGE = 'oklch(0.70 0.17 55)', YELLOW = 'oklch(0.87 0.16 95)'
const GREEN = 'oklch(0.56 0.14 150)', BLUE = 'oklch(0.52 0.15 250)', PURPLE = 'oklch(0.50 0.16 305)'

export const COMMAND_POST = 'command_post'

// In the order the form and the legend list them.
export const KINDS: Kind[] = [
    { code: COMMAND_POST, label: 'Command post', icon: IconHome, color: BLACK, darkIcon: false },
    { code: 'last_known_position', label: 'Last known position', icon: IconMapPinQuestion, color: PURPLE, darkIcon: false },
    { code: 'point_last_seen', label: 'Point last seen', icon: IconEye, color: PURPLE, darkIcon: false },
    { code: 'evidence', label: 'Evidence', icon: IconZoomExclamation, color: RED, darkIcon: false },
    { code: 'hazard', label: 'Hazard', icon: IconAlertTriangle, color: YELLOW, darkIcon: true },
    { code: 'landing_zone', label: 'Landing zone', icon: IconHelicopterLanding, color: BLUE, darkIcon: false },
    { code: 'find', label: 'Find', icon: IconUserCheck, color: GREEN, darkIcon: false },
    { code: 'relay', label: 'Relay', icon: IconAntenna, color: ORANGE, darkIcon: true },
    { code: 'meeting_point', label: 'Meeting point', icon: IconUsers, color: BLUE, darkIcon: false },
    { code: 'other', label: 'Other', icon: IconMapPin, color: WHITE, darkIcon: true },
]

const OTHER = KINDS[KINDS.length - 1]

// The kind with this code. A mission file can hold a kind the app does not know; it is
// shown as Other is, under the file's own word for it.
export function kindOf(code: string): Kind {
    return KINDS.find((kind) => kind.code === code) ?? { ...OTHER, code, label: code }
}
