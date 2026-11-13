// Isolated proposed v3 shapes. These are not the accepted 2.1 wire contract.
export const DAY_COLORS = ['blue', 'teal', 'green', 'amber', 'rose'] as const
export type DayColor = typeof DAY_COLORS[number]
export interface DraftStars { weekSeed: string; count: number; positions: string }
export interface DraftMine {
  myStarIndex: number
  mine: { constellationId: string; day: number; colorId: DayColor; starIndices: number[] }[]
  secondDegree: { constellationId: string; viaStarIndex: number; starIndices: number[] }[]
}

function assert(ok: unknown, message: string): asserts ok {
  if (!ok) throw new Error(message)
}
function record(value: unknown, keys: string[]): Record<string, unknown> {
  assert(value !== null && typeof value === 'object' && !Array.isArray(value), 'Expected object')
  const item = value as Record<string, unknown>
  assert(Object.keys(item).length === keys.length && keys.every(key => Object.hasOwn(item, key)), 'Unexpected or missing field')
  return item
}
function integer(value: unknown, min: number, max: number): asserts value is number {
  assert(typeof value === 'number' && Number.isInteger(value) && value >= min && value <= max, 'Integer outside bounds')
}
function opaque(value: unknown): asserts value is string {
  assert(typeof value === 'string' && /^[a-zA-Z0-9_-]{1,80}$/.test(value), 'Invalid opaque token')
}
function indices(value: unknown, count: number): asserts value is number[] {
  assert(Array.isArray(value) && value.length > 0 && value.length <= count, 'Invalid star list')
  value.forEach(index => integer(index, 0, count - 1))
  assert(new Set(value).size === value.length, 'Duplicate index')
}

export function validateStars(value: unknown): { stars: DraftStars; points: Int16Array } {
  const item = record(value, ['weekSeed', 'count', 'positions'])
  opaque(item.weekSeed)
  integer(item.count, 1, 10000)
  assert(typeof item.positions === 'string' && item.positions.length <= 53336, 'Invalid encoded positions')
  assert(/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(item.positions), 'Invalid base64')
  const bytes = atob(item.positions)
  assert(bytes.length === item.count * 4, 'Positions byte length must equal count * 4')
  const points = new Int16Array(item.count * 2)
  for (let i = 0; i < points.length; i++) {
    const word = bytes.charCodeAt(i * 2) | (bytes.charCodeAt(i * 2 + 1) << 8)
    assert(word <= 32767, 'Position outside 0..32767')
    points[i] = word
  }
  return { stars: item as unknown as DraftStars, points }
}

export function validateMine(value: unknown, count: number): DraftMine {
  integer(count, 1, 10000)
  const item = record(value, ['myStarIndex', 'mine', 'secondDegree'])
  integer(item.myStarIndex, 0, count - 1)
  assert(Array.isArray(item.mine) && item.mine.length <= 15, 'Invalid own constellations')
  const neighbors = new Set<number>()
  const ownIds = new Set<string>()
  for (const entry of item.mine) {
    const own = record(entry, ['constellationId', 'day', 'colorId', 'starIndices'])
    opaque(own.constellationId)
    assert(!ownIds.has(own.constellationId), 'Duplicate constellation')
    ownIds.add(own.constellationId)
    integer(own.day, 1, 5)
    assert(own.colorId === DAY_COLORS[own.day - 1], 'Day/color mismatch')
    indices(own.starIndices, count)
    assert(own.starIndices.includes(item.myStarIndex), 'Own constellation must include viewer')
    own.starIndices.forEach(index => { if (index !== item.myStarIndex) neighbors.add(index) })
  }
  assert(Array.isArray(item.secondDegree) && item.secondDegree.length <= 40, 'Invalid second degree')
  const seen = new Set<string>()
  const perNeighbor = new Map<number, number>()
  let total = 0
  for (const entry of item.secondDegree) {
    const other = record(entry, ['constellationId', 'viaStarIndex', 'starIndices'])
    opaque(other.constellationId)
    assert(!ownIds.has(other.constellationId) && !seen.has(other.constellationId), 'Duplicate or own second degree')
    seen.add(other.constellationId)
    integer(other.viaStarIndex, 0, count - 1)
    assert(neighbors.has(other.viaStarIndex), 'Second degree must hang from an own neighbor')
    indices(other.starIndices, count)
    assert(other.starIndices.includes(other.viaStarIndex) && !other.starIndices.includes(item.myStarIndex), 'Invalid second-degree membership')
    const viaCount = (perNeighbor.get(other.viaStarIndex) ?? 0) + 1
    assert(viaCount <= 2, 'At most two sets per neighbor')
    perNeighbor.set(other.viaStarIndex, viaCount)
    total += other.starIndices.length
  }
  assert(total <= 3000, 'Second-degree star cap exceeded')
  return item as unknown as DraftMine
}
