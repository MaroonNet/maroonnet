import { IconHome } from '@tabler/icons-react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { BOX } from '../frame/Legend.tsx'
import { commandPost } from './waypointWords.ts'
import { useWaypoints } from './waypoints.ts'

// The button that moves the map so the command post is in its middle, at the zoom it has.
// Greyed while the mission has no command post.
function CenterOnCommandPost({ map }: { map: MapLibreMap }) {
    const post = commandPost(useWaypoints().waypoints)
    return (
        <button
            type="button"
            aria-label="Center on Command Post"
            aria-disabled={post ? undefined : true}
            title={post ? 'Center on Command Post' : 'No command post is placed'}
            onClick={post ? () => map.easeTo({ center: [post.lon, post.lat] }) : undefined}
            className={`flex size-11 items-center justify-center rounded-box ${BOX} ${post ? 'cursor-pointer hover:bg-strip' : 'opacity-40'}`}
        >
            <IconHome size={20} stroke={1.75} aria-hidden />
        </button>
    )
}

export default CenterOnCommandPost
