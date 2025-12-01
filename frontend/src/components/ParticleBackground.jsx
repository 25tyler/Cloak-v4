import { useCallback, useMemo } from 'react'
import Particles from 'react-particles'
import { loadSlim } from 'tsparticles-slim'

export default function ParticleBackground() {
  const particlesInit = useCallback(async (engine) => {
    await loadSlim(engine)
  }, [])

  const options = useMemo(
    () => ({
      background: {
        color: {
          value: 'transparent',
        },
      },
      fpsLimit: 60,
      interactivity: {
        events: {
          onClick: {
            enable: false,
          },
          onHover: {
            enable: true,
            mode: 'grab',
          },
        },
        modes: {
          grab: {
            distance: 120,
            links: {
              opacity: 0.3,
            },
          },
        },
      },
      particles: {
        color: {
          value: ['#94a3b8', '#cbd5e1', '#e2e8f0', '#f1f5f9'],
        },
        links: {
          color: '#cbd5e1',
          distance: 150,
          enable: true,
          opacity: 0.1,
          width: 1,
          triangles: {
            enable: false,
          },
        },
        move: {
          direction: 'none',
          enable: true,
          outModes: {
            default: 'out',
          },
          random: false,
          speed: 0.3,
          straight: false,
          attract: {
            enable: false,
          },
        },
        number: {
          density: {
            enable: true,
            area: 1200,
          },
          value: 30,
        },
        opacity: {
          value: 0.4,
          animation: {
            enable: true,
            speed: 1,
            minimumValue: 0.2,
            sync: false,
          },
        },
        shape: {
          type: 'circle',
        },
        size: {
          value: { min: 1, max: 2 },
          animation: {
            enable: false,
          },
        },
        twinkle: {
          particles: {
            enable: false,
          },
        },
      },
      detectRetina: true,
    }),
    []
  )

  return (
    <Particles
      id="tsparticles"
      init={particlesInit}
      options={options}
      className="absolute inset-0 -z-10"
    />
  )
}

