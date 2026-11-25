import { expect, test } from 'vitest'
import { stacksOf } from './stacks.ts'

// A pretend map on which a place's longitude and latitude are its x and y on screen, in pixels.
const map = { project: ([lon, lat]: [number, number]) => ({ x: lon, y: lat }) } as never
const at = (name: string, x: number, y = 0) => ({ name, lon: x, lat: y })
const names = (stacks: { name: string }[][]) => stacks.map((stack) => stack.map((one) => one.name))

test('markers whose places are less than 50 px apart on screen are one stack', () => {
    expect(names(stacksOf([at('a', 0), at('b', 49)], map))).toEqual([['a', 'b']])
    // c is 50 px from a and 58 px from b.
    expect(names(stacksOf([at('a', 0), at('b', 0, 30), at('c', 50)], map))).toEqual([['a', 'b'], ['c']])
})

test('a marker joins a stack when it is near any marker in it, so a row 40 px apart is one stack', () => {
    expect(names(stacksOf([at('a', 0), at('b', 40), at('c', 80), at('d', 120)], map))).toEqual([['a', 'b', 'c', 'd']])
})

test('a marker near two stacks joins them into one, which keeps the order the markers were given in', () => {
    // a and c are 80 px apart until b, between them, arrives.
    expect(names(stacksOf([at('a', 0), at('c', 80), at('b', 40)], map))).toEqual([['a', 'c', 'b']])
    expect(names(stacksOf([at('a', 0), at('far', 500), at('b', 40)], map))).toEqual([['a', 'b'], ['far']])
})
