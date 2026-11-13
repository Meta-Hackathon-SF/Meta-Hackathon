import { expect, test } from '@playwright/test'
import { syntheticFixture } from './fixture'
import { validateMine, validateStars } from './draft'

test.describe('isolated proposed v3 sky', () => {
  test('accepts fixture and rejects malformed or private projections', () => {
    const { rawStars, rawMine, points } = syntheticFixture()
    const count = 10000
    const emptyMine = { myStarIndex: 0, mine: [], secondDegree: [] }

    expect(points.length).toBe(20000)
    expect(validateMine(emptyMine, count).mine).toEqual([])

    for (const extra of ['playerId', 'score', 'answer', 'museText']) {
      expect(() => validateStars({ ...rawStars, [extra]: 'private' })).toThrow()
      expect(() => validateMine({ ...rawMine, [extra]: 'private' }, count)).toThrow()

      const privateOwn = {
        ...rawMine,
        mine: [{ ...rawMine.mine[0], [extra]: 'private' }],
      }
      expect(() => validateMine(privateOwn, count)).toThrow()

      const privateNeighbor = {
        ...rawMine,
        secondDegree: [{ ...rawMine.secondDegree[0], [extra]: 'private' }],
      }
      expect(() => validateMine(privateNeighbor, count)).toThrow()
    }

    const truncatedPositions = {
      ...rawStars,
      positions: rawStars.positions.slice(4),
    }
    expect(() => validateStars(truncatedPositions)).toThrow(/byte length/)

    const negativePosition = {
      weekSeed: 'fixture',
      count: 1,
      positions: btoa('\xff\xff\x00\x00'),
    }
    expect(() => validateStars(negativePosition)).toThrow(/Position outside/)
    expect(() => validateStars({ ...rawStars, positions: 'not base64' })).toThrow()
    expect(() => validateMine({ ...rawMine, myStarIndex: count }, count)).toThrow()

    const negativeIndex = {
      ...rawMine,
      mine: [{ ...rawMine.mine[0], starIndices: [0, -1] }],
    }
    expect(() => validateMine(negativeIndex, count)).toThrow()

    const mismatchedColor = {
      ...rawMine,
      mine: [{ ...rawMine.mine[0], colorId: 'rose' }],
    }
    expect(() => validateMine(mismatchedColor, count)).toThrow()

    const unrelatedNeighbor = {
      ...rawMine,
      secondDegree: [{ ...rawMine.secondDegree[0], viaStarIndex: 999 }],
    }
    expect(() => validateMine(unrelatedNeighbor, count)).toThrow()

    const excessiveSets = {
      ...rawMine,
      secondDegree: Array(41).fill(rawMine.secondDegree[0]),
    }
    expect(() => validateMine(excessiveSets, count)).toThrow()

    const ownSecondDegree = {
      ...rawMine,
      secondDegree: [{ ...rawMine.secondDegree[0], starIndices: [1, 0] }],
    }
    expect(() => validateMine(ownSecondDegree, count)).toThrow()
  })

  test('renders fixed 10,000-star sky, controls, honest visualization and mobile layout', async ({ page }, testInfo) => {
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto('/')

    const truthLabel = page.getByText(
      'TEST-ONLY · Proposed v3 · Synthetic player · Demo timing',
    )
    await expect(truthLabel).toBeVisible()

    const sky = page.getByRole('img')
    await expect(sky).toHaveAttribute('data-rendered-stars', '10000')
    await expect(sky).toHaveAttribute('data-second-degree-opacity', '0.25')

    const originalSize = await sky.boundingBox()
    await sky.hover()
    await page.mouse.wheel(0, -250)
    expect(await sky.boundingBox()).toEqual(originalSize)

    const wednesdayButton = page.getByRole('button', {
      name: 'Wednesday',
      exact: true,
    })
    await wednesdayButton.click()
    await expect(wednesdayButton).toHaveAttribute('aria-pressed', 'true')

    const nearbyToggle = page.getByRole('checkbox')
    await nearbyToggle.uncheck()
    await expect(sky).toHaveAttribute('data-second-degree-opacity', '0')
    await nearbyToggle.check()
    await page.getByRole('button', { name: 'Whole week', exact: true }).click()
    await page.screenshot({
      path: testInfo.outputPath('saturday-desktop.png'),
      fullPage: true,
    })

    await page.getByRole('button', { name: 'Forming', exact: true }).click()
    await expect(page.getByText('Illustrative formation visualization')).toBeVisible()
    await expect(page.getByRole('progressbar')).toHaveAttribute('value', '0')
    await expect(page.getByRole('progressbar')).not.toHaveAttribute('value', '0')

    await page.getByRole('button', { name: 'Sunday reveal', exact: true }).click()
    await expect(page.getByText('Four synthetic stars · illustrative anchors')).toBeVisible()
    await page.screenshot({
      path: testInfo.outputPath('sunday-desktop.png'),
      fullPage: true,
    })

    await page.setViewportSize({ width: 390, height: 844 })
    await page.getByRole('button', { name: 'Saturday sky', exact: true }).click()
    await expect(sky).toHaveAttribute('data-rendered-stars', '10000')
    const fitsMobileViewport = await page.evaluate(() => {
      return document.documentElement.scrollWidth <= window.innerWidth
    })
    expect(fitsMobileViewport).toBe(true)
    await page.screenshot({
      path: testInfo.outputPath('saturday-mobile.png'),
      fullPage: true,
    })

    expect(errors).toEqual([])
  })
})
