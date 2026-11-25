import type { FilterSpecification, LayerSpecification, StyleSpecification } from 'maplibre-gl'

// Copies of the map style changed by the user's choices in the layer panel. The map is given the
// copy, and MapLibre compares it with the style it is drawing and changes only what differs.

// What the backend lists in the style's metadata (backend/maps/style.py).
export type LayerGroup = { id: string, label: string }  // metadata.groups
export type TrailUse = { id: string, label: string, filter: FilterSpecification }  // metadata.trail_uses
export type StyleMetadata = { groups: LayerGroup[], trail_uses: TrailUse[] }

// A copy of the style with the hidden groups' layers set to not show.
export function hideGroups(style: StyleSpecification, hidden: string[]): StyleSpecification {
    return {
        ...style,
        layers: style.layers.map((layer) => {
            const group = groupOf(layer)
            if (!group || !hidden.includes(group)) return layer
            return { ...layer, layout: { ...layer.layout, visibility: 'none' } } as LayerSpecification
        }),
    }
}

// A copy of the style whose trail layers draw only the trails that also pass the given filter.
// Each layer keeps its own filter, so a trail must pass both.
export function narrowTrails(style: StyleSpecification, filter: FilterSpecification | undefined): StyleSpecification {
    if (!filter) return style
    return {
        ...style,
        layers: style.layers.map((layer) => {
            if (groupOf(layer) !== 'trails') return layer
            const own = (layer as { filter?: FilterSpecification }).filter
            return { ...layer, filter: own ? ['all', own, filter] : filter } as LayerSpecification
        }),
    }
}

// The next style, with everything that was added to the map after it loaded put back on
// top: the shapes a drawing tool is drawing, and the mission's own layers. Without this,
// MapLibre takes away every layer the next style does not list. base is the backend's
// style, and previous is what the map is drawing now; whatever previous has that base does
// not was added.
export function keepAdded(
    base: StyleSpecification, previous: StyleSpecification | undefined, next: StyleSpecification,
): StyleSpecification {
    if (!previous) return next
    const baseLayers = new Set(base.layers.map((layer) => layer.id))
    const addedLayers = previous.layers.filter((layer) => !baseLayers.has(layer.id))
    const addedSources = Object.entries(previous.sources).filter(([id]) => !(id in base.sources))
    if (!addedLayers.length && !addedSources.length) return next
    return {
        ...next,
        sources: { ...next.sources, ...Object.fromEntries(addedSources) },
        layers: [...next.layers, ...addedLayers],
    }
}

function groupOf(layer: LayerSpecification): string | undefined {
    return (layer.metadata as { group?: string } | undefined)?.group
}
