/** The one Facebook Space constellation. SpaceIcon (sidebar), SpaceTabIcon (top and bottom tabs) and
 *  ConstellationsMark (post header) all draw from these points so the logo is identical everywhere. */
export const SPACE_STARS: ReadonlyArray<readonly [number, number, number]> = [
  [9.5, 22.5, 2.2],
  [15.5, 12, 2.8],
  [24, 15.5, 2.2],
  [27, 25, 1.9],
  [18, 26.5, 1.9],
];
export const SPACE_LINES: ReadonlyArray<readonly [number, number]> = [
  [0, 1],
  [1, 2],
  [2, 3],
  [0, 4],
];
