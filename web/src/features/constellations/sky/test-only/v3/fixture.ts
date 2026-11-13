import { DAY_COLORS, validateMine, validateStars } from './draft'
import type { DraftMine } from './draft'

export function syntheticFixture() {
  let state = 20261112
  const random = () => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 4294967296 }
  const coordinates = Array.from({ length: 20000 }, () => Math.floor(random() * 32768))
  // Place the viewer and neighbors in a legible central arrangement.
  const central = [[16384, 16384], [10200, 9300], [20400, 7800], [24300, 14800], [21100, 22700], [11300, 23200], [6400, 15700], [15300, 5600], [27200, 21100], [6500, 6500], [17300, 27000]]
  central.forEach(([x, y], index) => { coordinates[index * 2] = x; coordinates[index * 2 + 1] = y })
  let binary = ''
  for (const value of coordinates) binary += String.fromCharCode(value & 255, value >> 8)
  const rawStars = { weekSeed: 'synthetic-week', count: 10000, positions: btoa(binary) }
  const rawMine: DraftMine = {
    myStarIndex: 0,
    mine: DAY_COLORS.map((colorId, i) => ({ constellationId: `demo-own-${i}`, day: i + 1, colorId, starIndices: [0, i + 1, i + 6] })),
    secondDegree: Array.from({ length: 10 }, (_, i) => ({ constellationId: `demo-second-${i}`, viaStarIndex: i + 1, starIndices: [i + 1, i + 20, i + 40, i + 60] })),
  }
  return { ...validateStars(rawStars), mine: validateMine(rawMine, rawStars.count), rawStars, rawMine }
}
