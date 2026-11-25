import {
    IconAccessPoint, IconAlertTriangle, IconMap, IconMarquee2, IconPolygon, IconReport,
    IconSettings, IconStack2, IconUser, IconUsersGroup, type Icon,
} from '@tabler/icons-react'
import { dayAndSession, STATUS_LABELS, useMission } from '../mission/mission.ts'

// The panels a rail button can open.
export type PanelId = 'mission' | 'teams' | 'people' | 'sectors' | 'area' | 'alerts' | 'mesh' | 'layers' | 'maps' | 'aar' | 'settings'

// built: the button's panel exists. The rest are greyed out until their panel is built.
const BUTTONS: { id: PanelId, label: string, icon: Icon, built: boolean }[] = [
    { id: 'teams', label: 'Groups & Teams', icon: IconUsersGroup, built: false },
    { id: 'people', label: 'People', icon: IconUser, built: false },
    { id: 'sectors', label: 'Sectors', icon: IconPolygon, built: false },
    { id: 'area', label: 'Area', icon: IconMarquee2, built: true },
    { id: 'alerts', label: 'Alerts', icon: IconAlertTriangle, built: false },
    { id: 'mesh', label: 'Mesh', icon: IconAccessPoint, built: false },
    { id: 'layers', label: 'Layers', icon: IconStack2, built: true },
    { id: 'maps', label: 'Maps', icon: IconMap, built: false },
    { id: 'aar', label: 'AAR', icon: IconReport, built: false },
]

// A button that cannot be pressed yet: its look, and what it says to a pointer and a screen reader.
const GREYED = 'opacity-40'
const NOT_YET = { 'aria-disabled': true, title: 'Not available yet' } as const

type Props = {
    openPanel: PanelId | null           // the panel that is open, if any
    onPress: (id: PanelId) => void      // a built button was pressed
}

// The strip down the left edge: the logo, the Mission block, a button for each panel,
// the Day/Night switch and Settings.
function Rail({ openPanel, onPress }: Props) {
    return (
        <nav className="z-10 flex w-rail flex-none flex-col overflow-y-auto border-r border-ink bg-panel">
            <div className="flex h-header flex-none flex-col items-center justify-center bg-ink text-panel">
                <div className="text-figure font-bold tracking-widest">MN</div>
                <div className="font-mono text-label font-medium tracking-widest">COMMAND</div>
            </div>
            <MissionBlock open={openPanel === 'mission'} onPress={() => onPress('mission')} />
            {BUTTONS.map((button) => (
                <RailButton
                    key={button.id}
                    label={button.label}
                    icon={button.icon}
                    open={openPanel === button.id}
                    onPress={button.built ? () => onPress(button.id) : undefined}
                />
            ))}
            <div className="flex-1" />
            <div className="flex flex-none flex-col border-t border-ink">
                <div className={`mx-2 mt-2.5 mb-2 flex overflow-hidden rounded-control border border-ink ${GREYED}`}>
                    <button type="button" {...NOT_YET} className="flex-1 bg-ink py-1 font-mono text-label tracking-wider text-panel">DAY</button>
                    <button type="button" {...NOT_YET} className="flex-1 py-1 font-mono text-label tracking-wider text-muted">NIGHT</button>
                </div>
                <RailButton
                    label="Settings"
                    icon={IconSettings}
                    open={openPanel === 'settings'}
                    onPress={() => onPress('settings')}
                    short
                />
            </div>
        </nav>
    )
}

// The block under the logo. It names the open mission with its day and session, or its
// status while it is in planning, and reads "Mission + New" with none open. Pressing it
// opens the Mission panel.
function MissionBlock({ open, onPress }: { open: boolean, onPress: () => void }) {
    const { mission } = useMission()
    const line = !mission ? '+ New' : mission.status === 'planning' ? STATUS_LABELS.planning : dayAndSession(mission)
    return (
        <button
            type="button"
            aria-pressed={open}
            aria-label={mission ? `Mission: ${mission.name}, ${line}` : undefined}
            onClick={onPress}
            className={`flex-none cursor-pointer border-b border-ink px-2 py-2.5 text-center ${open ? 'bg-ink text-panel' : 'hover:bg-strip'}`}
        >
            <div className="font-bold wrap-break-word">{mission ? mission.name : 'Mission'}</div>
            <div className="mt-1 font-mono text-label">{line}</div>
        </button>
    )
}

type RailButtonProps = {
    label: string
    icon: Icon
    open?: boolean          // its panel is the open one
    onPress?: () => void    // left out: the button is greyed out
    short?: boolean         // the icon beside the label, for the last row of the rail
}

// One rail button: an icon over a label.
function RailButton({ label, icon: ButtonIcon, open = false, onPress, short = false }: RailButtonProps) {
    const look = !onPress ? GREYED : open ? 'cursor-pointer bg-ink text-panel' : 'cursor-pointer hover:bg-strip'
    const layout = short
        ? 'justify-center gap-1.5 border-t border-ink/20 py-2.5'
        : 'flex-col gap-1 border-b border-ink/20 px-1 pt-3 pb-2.5'
    return (
        <button
            type="button"
            aria-pressed={onPress ? open : undefined}
            onClick={onPress}
            {...(onPress ? {} : NOT_YET)}
            className={`flex flex-none items-center text-center leading-tight ${layout} ${look}`}
        >
            <ButtonIcon size={16} stroke={1.75} aria-hidden />
            <span>{label}</span>
        </button>
    )
}

export default Rail
