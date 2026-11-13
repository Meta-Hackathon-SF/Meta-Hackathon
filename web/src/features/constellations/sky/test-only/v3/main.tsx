import { StrictMode, useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { syntheticFixture } from './fixture'
import './prototype.css'

const fixture = syntheticFixture()
const colors = ['#71aaff', '#55dbd3', '#a1d58a', '#f2c76f', '#f397bd']
const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
const scenes = ['Saturday sky', 'Forming', 'Sunday reveal'] as const
type Scene = typeof scenes[number]

const sceneCopy: Record<Scene, { heading: string; description: string }> = {
  'Saturday sky': {
    heading: 'A week of small connections.',
    description: 'Follow your colors across the community sky.',
  },
  Forming: {
    heading: 'Finding your people.',
    description: 'Illustrative formation visualization',
  },
  'Sunday reveal': {
    heading: 'A new constellation.',
    description: 'Illustrative Meta-logo arrangement.',
  },
}

export function App() {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [scene, setScene] = useState<Scene>('Saturday sky')
  const [day, setDay] = useState(0)
  const [secondDegree, setSecondDegree] = useState(true)
  const [step, setStep] = useState(0)
  const isSunday = scene === 'Sunday reveal'
  const copy = sceneCopy[scene]

  useEffect(() => {
    if (scene !== 'Forming') return

    const timer = window.setInterval(() => {
      setStep(previous => Math.min(previous + 1, 12))
    }, 650)
    return () => window.clearInterval(timer)
  }, [scene])

  useEffect(() => {
    const element = canvas.current
    if (!element) return

    const draw = () => {
      const rect = element.getBoundingClientRect()
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      element.width = Math.round(rect.width * dpr)
      element.height = Math.round(rect.height * dpr)

      const ctx = element.getContext('2d')!
      ctx.scale(dpr, dpr)
      const width = rect.width
      const height = rect.height
      const point = (index: number): [number, number] => [
        24 + fixture.points[index * 2] / 32767 * (width - 48),
        24 + fixture.points[index * 2 + 1] / 32767 * (height - 48),
      ]

      ctx.fillStyle = '#081120'
      ctx.fillRect(0, 0, width, height)
      for (let index = 0; index < fixture.stars.count; index++) {
        const [x, y] = point(index)
        const size = index % 13 === 0 ? 1.5 : 1
        ctx.globalAlpha = 0.12 + (index % 5) * 0.065
        ctx.fillStyle = '#c1d4ee'
        ctx.fillRect(x, y, size, size)
      }

      const line = (indices: number[], color: string, opacity: number) => {
        ctx.strokeStyle = color
        ctx.globalAlpha = opacity
        ctx.lineWidth = 1.4
        ctx.beginPath()
        indices.forEach((index, offset) => {
          const [x, y] = point(index)
          if (offset === 0) {
            ctx.moveTo(x, y)
          } else {
            ctx.lineTo(x, y)
          }
        })
        ctx.stroke()

        indices.forEach(index => {
          const [x, y] = point(index)
          ctx.fillStyle = color
          ctx.beginPath()
          ctx.arc(x, y, 3, 0, Math.PI * 2)
          ctx.fill()
        })
      }

      if (scene === 'Sunday reveal') {
        // Local illustrative anchors; no API main-constellation response.
        const logo = (t: number): [number, number] => {
          const angle = t * Math.PI * 2
          return [
            width / 2 + Math.cos(angle) * width * 0.29,
            height / 2 + Math.sin(2 * angle) * height * 0.19,
          ]
        }

        ctx.globalAlpha = 1
        ctx.strokeStyle = '#80b7ff'
        ctx.lineWidth = 2.2
        ctx.beginPath()
        for (let index = 0; index <= 200; index++) {
          const [x, y] = logo(index / 200)
          if (index === 0) {
            ctx.moveTo(x, y)
          } else {
            ctx.lineTo(x, y)
          }
        }
        ctx.stroke()

        for (const t of [0.08, 0.31, 0.58, 0.82]) {
          const [x, y] = logo(t)
          ctx.fillStyle = '#c6e1ff'
          ctx.shadowColor = '#82bbff'
          ctx.shadowBlur = 14
          ctx.beginPath()
          ctx.arc(x, y, 5, 0, Math.PI * 2)
          ctx.fill()
        }
        ctx.shadowBlur = 0
      } else {
        if (secondDegree) {
          fixture.mine.secondDegree.forEach(set => {
            line(set.starIndices, '#95aeca', 0.25)
          })
        }

        fixture.mine.mine
          .filter(set => day === 0 || set.day === day)
          .forEach(set => line(set.starIndices, colors[set.day - 1], 0.95))

        if (scene === 'Forming') {
          for (let index = 1; index <= Math.min(step, 10); index++) {
            const dropped = index % 3 === 0
            line([0, index], dropped ? '#8190a4' : '#d6e8ff', dropped ? 0.15 : 0.7)
          }
        }

        const [x, y] = point(fixture.mine.myStarIndex)
        ctx.globalAlpha = 1
        ctx.strokeStyle = '#fff'
        ctx.lineWidth = 1.5
        ctx.beginPath()
        ctx.arc(x, y, 8, 0, Math.PI * 2)
        ctx.stroke()
        ctx.fillStyle = '#fff'
        ctx.font = '12px system-ui'
        ctx.fillText('You', x + 14, y + 4)
      }

      ctx.globalAlpha = 1
      element.dataset.renderedStars = String(fixture.stars.count)
      element.dataset.secondDegreeOpacity = secondDegree ? '0.25' : '0'
    }

    const observer = new ResizeObserver(draw)
    observer.observe(element)
    draw()
    return () => observer.disconnect()
  }, [scene, day, secondDegree, step])

  return (
    <main>
      <div className="truth">
        TEST-ONLY · Proposed v3 · Synthetic player · Demo timing
      </div>
      <header>
        <a className="brand" href="./index.html">
          <span className="brand-icon">f</span> Facebook <span>Space</span>
        </a>
        <span className="preview">ISOLATED DESIGN PREVIEW</span>
      </header>

      <nav aria-label="Preview scene">
        {scenes.map(item => (
          <button
            key={item}
            aria-pressed={scene === item}
            onClick={() => {
              setScene(item)
              setStep(0)
            }}
          >
            {item}
          </button>
        ))}
      </nav>

      <section className="intro">
        <div>
          <p className="eyebrow">
            {isSunday ? 'SUNDAY · A LITTLE CLOSER' : 'YOUR WEEK, CONNECTED'}
          </p>
          <h1>{copy.heading}</h1>
          <p>{copy.description}</p>
        </div>
        <div className="week">
          NOV 09 — 15<br/>
          <strong>{isSunday ? 'Sunday' : 'Saturday'}</strong>
        </div>
      </section>

      <section className="sky-card" aria-label="Community sky preview">
        <div className="sky-toolbar">
          <span>
            <i/> {isSunday ? 'Main constellation · illustration' : 'The whole community sky'}
          </span>
          <span>Fixed view · no zoom</span>
        </div>
        <canvas
          ref={canvas}
          role="img"
          aria-label="Synthetic community sky with 10,000 stars, your colored weekly connections and faint second-degree connections"
        />
        <div className="sky-caption">
          <span>
            {isSunday
              ? 'Four synthetic stars · illustrative anchors'
              : 'Your star is circled. Your week is in color.'}
          </span>
          <span>10,000 synthetic stars</span>
        </div>
      </section>

      {scene === 'Saturday sky' && (
        <div className="controls">
          <div className="day-controls">
            <button aria-pressed={day === 0} onClick={() => setDay(0)}>
              Whole week
            </button>
            {days.map((name, index) => (
              <button
                key={name}
                aria-pressed={day === index + 1}
                onClick={() => setDay(index + 1)}
              >
                <span style={{ background: colors[index] }}/>
                {name}
              </button>
            ))}
          </div>
          <label>
            <input
              type="checkbox"
              checked={secondDegree}
              onChange={event => setSecondDegree(event.target.checked)}
            />
            Show nearby connections <small>25% opacity</small>
          </label>
        </div>
      )}

      {scene === 'Forming' && (
        <div className="formation" aria-live="polite">
          <span>
            Demo visualization · {step === 12 ? 'Ready · awaiting demo reveal' : 'Trying connections'}
          </span>
          <progress value={step} max={12}/>
        </div>
      )}

      <footer>
        <span>Synthetic fixture only.</span>
        <span>Contract 2.1 active · v3 proposed</span>
      </footer>
    </main>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App/>
  </StrictMode>,
)
