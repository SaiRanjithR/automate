import { Canvas, useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'

/**
 * Hero animation: tender pages stream into a glowing core and come out as a compliance matrix whose
 * tiles flip from grey to green / amber / red as they are "drafted". Colours come from the app theme.
 */

type Palette = {
  primary: THREE.Color
  full: THREE.Color
  partial: THREE.Color
  gap: THREE.Color
  idle: THREE.Color
  paper: THREE.Color
}

function cssColor(name: string, fallback: string): THREE.Color {
  const value =
    typeof window === 'undefined'
      ? ''
      : getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  try {
    return new THREE.Color(value.startsWith('#') ? value : fallback)
  } catch {
    return new THREE.Color(fallback)
  }
}

function usePalette(): Palette {
  return useMemo(
    () => ({
      primary: cssColor('--primary', '#2952cc'),
      full: cssColor('--status-full', '#1f9d55'),
      partial: cssColor('--status-partial', '#c27c0e'),
      gap: cssColor('--status-gap', '#c53030'),
      idle: new THREE.Color('#2a3566'),
      paper: new THREE.Color('#f4f6fb'),
    }),
    [],
  )
}

const smooth = (x: number) => {
  const t = Math.min(1, Math.max(0, x))
  return t * t * (3 - 2 * t)
}

/** Scene time; a fixed moment when motion is reduced so the still frame shows a drafted matrix. */
const sceneTime = (elapsed: number, speed: number) => (speed === 0 ? 6.5 : elapsed * speed)

const PAGE_COUNT = 7

function Pages({ palette, speed }: { palette: Palette; speed: number }) {
  const refs = useRef<(THREE.Mesh | null)[]>([])
  useFrame(({ clock }) => {
    const time = sceneTime(clock.getElapsedTime(), speed)
    refs.current.forEach((mesh, i) => {
      if (!mesh) return
      const t = (time * 0.16 + i / PAGE_COUNT) % 1
      const lane = (i % 3) - 1
      mesh.position.set(
        THREE.MathUtils.lerp(-2.55, -0.95, smooth(t)),
        Math.sin(t * Math.PI) * 0.6 + lane * 0.4 * (1 - t),
        THREE.MathUtils.lerp(-1.4, 0, t),
      )
      mesh.rotation.set(0.25 * (1 - t), 0.9 * (1 - t) + 0.3, Math.sin(t * 5 + i) * 0.15)
      const scale = 0.8 - smooth(t) * 0.68
      mesh.scale.setScalar(Math.max(scale, 0.05))
      const material = mesh.material as THREE.MeshStandardMaterial
      material.opacity = t < 0.1 ? t * 9 : t > 0.82 ? Math.max(0, (1 - t) * 5.5) : 0.92
    })
  })
  return (
    <group>
      {Array.from({ length: PAGE_COUNT }, (_, i) => (
        <mesh
          key={i}
          ref={(mesh) => {
            refs.current[i] = mesh
          }}
        >
          <boxGeometry args={[0.95, 1.25, 0.02]} />
          <meshStandardMaterial
            color={palette.paper}
            emissive={palette.primary}
            emissiveIntensity={0.08}
            transparent
            roughness={0.45}
          />
        </mesh>
      ))}
    </group>
  )
}

function Core({ palette, speed }: { palette: Palette; speed: number }) {
  const outer = useRef<THREE.Mesh>(null)
  const inner = useRef<THREE.Mesh>(null)
  const ring = useRef<THREE.Mesh>(null)
  useFrame(({ clock }) => {
    const time = sceneTime(clock.getElapsedTime(), speed)
    if (outer.current) {
      outer.current.rotation.set(time * 0.3, time * 0.45, 0)
      outer.current.scale.setScalar(1 + Math.sin(time * 2) * 0.04)
    }
    if (inner.current) inner.current.rotation.set(-time * 0.5, time * 0.2, time * 0.3)
    if (ring.current) ring.current.rotation.set(Math.PI / 2.4, 0, time * 0.6)
  })
  return (
    <group position={[-0.85, 0, 0]}>
      <mesh ref={outer}>
        <icosahedronGeometry args={[0.95, 1]} />
        <meshStandardMaterial
          color={palette.primary}
          emissive={palette.primary}
          emissiveIntensity={0.9}
          wireframe
        />
      </mesh>
      <mesh ref={inner}>
        <icosahedronGeometry args={[0.5, 0]} />
        <meshStandardMaterial
          color={palette.primary}
          emissive={palette.primary}
          emissiveIntensity={0.55}
          metalness={0.6}
          roughness={0.2}
          flatShading
        />
      </mesh>
      <mesh ref={ring}>
        <torusGeometry args={[1.35, 0.012, 8, 96]} />
        <meshBasicMaterial color={palette.primary} transparent opacity={0.7} />
      </mesh>
      <pointLight color={palette.primary} intensity={18} distance={6} />
    </group>
  )
}

const COLS = 6
const ROWS = 5
const CYCLE = 11 // seconds per drafting wave

function statusFor(index: number): 'full' | 'partial' | 'gap' {
  const v = (index * 37 + 11) % 10
  return v < 7 ? 'full' : v < 9 ? 'partial' : 'gap'
}

function Matrix({ palette, speed }: { palette: Palette; speed: number }) {
  const tiles = useRef<(THREE.Mesh | null)[]>([])
  const group = useRef<THREE.Group>(null)
  const targets = useMemo(
    () => Array.from({ length: COLS * ROWS }, (_, i) => palette[statusFor(i)]),
    [palette],
  )
  useFrame(({ clock }) => {
    const time = sceneTime(clock.getElapsedTime(), speed)
    const phase = time % CYCLE
    if (group.current) group.current.position.y = Math.sin(time * 0.6) * 0.08
    tiles.current.forEach((mesh, i) => {
      if (!mesh) return
      const start = 0.6 + i * 0.16
      const reset = CYCLE - 1.2
      const flip =
        phase < reset ? smooth((phase - start) / 0.45) : 1 - smooth((phase - reset) / 0.9)
      mesh.rotation.x = flip * Math.PI
      const material = mesh.material as THREE.MeshStandardMaterial
      const target = targets[i] ?? palette.full
      const color = flip > 0.5 ? target : palette.idle
      material.color.copy(color)
      material.emissive.copy(color)
      material.emissiveIntensity = flip > 0.5 ? 0.45 : 0.15
      mesh.position.z = Math.sin(flip * Math.PI) * 0.25
    })
  })
  return (
    <group ref={group} position={[1.75, 0, -0.2]} rotation={[0.18, -0.55, 0.04]} scale={0.92}>
      {Array.from({ length: COLS * ROWS }, (_, i) => {
        const col = i % COLS
        const row = Math.floor(i / COLS)
        return (
          <mesh
            key={i}
            position={[(col - (COLS - 1) / 2) * 0.5, ((ROWS - 1) / 2 - row) * 0.36, 0]}
            ref={(mesh) => {
              tiles.current[i] = mesh
            }}
          >
            <boxGeometry args={[0.44, 0.29, 0.06]} />
            <meshStandardMaterial color={palette.idle} roughness={0.35} metalness={0.2} />
          </mesh>
        )
      })}
      {/* frame of the matrix */}
      <mesh position={[0, 0, -0.06]}>
        <boxGeometry args={[COLS * 0.5 + 0.25, ROWS * 0.36 + 0.25, 0.02]} />
        <meshStandardMaterial color="#0d1740" transparent opacity={0.55} roughness={0.9} />
      </mesh>
    </group>
  )
}

const CHIP_COUNT = 12

function Chips({ palette, speed }: { palette: Palette; speed: number }) {
  const refs = useRef<(THREE.Mesh | null)[]>([])
  useFrame(({ clock }) => {
    const time = sceneTime(clock.getElapsedTime(), speed)
    refs.current.forEach((mesh, i) => {
      if (!mesh) return
      const t = (time * 0.35 + i / CHIP_COUNT) % 1
      const lane = ((i * 7) % 5) - 2
      mesh.position.set(
        THREE.MathUtils.lerp(-0.35, 0.85, t),
        lane * 0.28 * t + Math.sin(t * Math.PI) * 0.35,
        Math.sin(t * Math.PI) * 0.6,
      )
      mesh.rotation.set(time + i, time * 1.3, 0)
      mesh.scale.setScalar(Math.sin(t * Math.PI) * 0.9 + 0.1)
    })
  })
  return (
    <group>
      {Array.from({ length: CHIP_COUNT }, (_, i) => (
        <mesh
          key={i}
          ref={(mesh) => {
            refs.current[i] = mesh
          }}
        >
          <boxGeometry args={[0.09, 0.09, 0.09]} />
          <meshStandardMaterial
            color={palette[statusFor(i)]}
            emissive={palette[statusFor(i)]}
            emissiveIntensity={0.8}
          />
        </mesh>
      ))}
    </group>
  )
}

function Dust({ palette, speed }: { palette: Palette; speed: number }) {
  const points = useRef<THREE.Points>(null)
  const positions = useMemo(() => {
    const array = new Float32Array(600 * 3)
    for (let i = 0; i < 600; i++) {
      // deterministic pseudo-random spread so renders are stable
      const a = Math.sin(i * 12.9898) * 43758.5453
      const b = Math.sin(i * 78.233) * 12543.123
      const c = Math.sin(i * 39.425) * 9871.77
      array[i * 3] = (a - Math.floor(a) - 0.5) * 16
      array[i * 3 + 1] = (b - Math.floor(b) - 0.5) * 9
      array[i * 3 + 2] = (c - Math.floor(c) - 0.5) * 6 - 2
    }
    return array
  }, [])
  useFrame(({ clock }) => {
    if (points.current) points.current.rotation.y = sceneTime(clock.getElapsedTime(), speed) * 0.02
  })
  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color={palette.primary}
        size={0.03}
        transparent
        opacity={0.7}
        sizeAttenuation
      />
    </points>
  )
}

/** Move the camera so the ~7-unit-wide scene fills the canvas whatever its shape. */
function CameraFit() {
  const lastAspect = useRef(0)
  useFrame(({ camera, size }) => {
    const aspect = size.width / Math.max(size.height, 1)
    if (Math.abs(aspect - lastAspect.current) < 0.001) return
    lastAspect.current = aspect
    const halfFov = THREE.MathUtils.degToRad(42 / 2)
    camera.position.z = Math.max(6.4, 7.2 / (2 * Math.tan(halfFov) * aspect))
    camera.updateProjectionMatrix()
  })
  return null
}

function Rig({ children }: { children: React.ReactNode }) {
  const group = useRef<THREE.Group>(null)
  useFrame(({ pointer }) => {
    if (!group.current) return
    group.current.rotation.y = THREE.MathUtils.lerp(
      group.current.rotation.y,
      pointer.x * 0.18,
      0.05,
    )
    group.current.rotation.x = THREE.MathUtils.lerp(
      group.current.rotation.x,
      -pointer.y * 0.1,
      0.05,
    )
  })
  return <group ref={group}>{children}</group>
}

export default function HeroScene({ reducedMotion = false }: { reducedMotion?: boolean }) {
  const palette = usePalette()
  const speed = reducedMotion ? 0 : 1
  return (
    <Canvas
      camera={{ position: [0, 0, 8.6], fov: 42 }}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true }}
      frameloop={reducedMotion ? 'demand' : 'always'}
      aria-hidden="true"
    >
      <CameraFit />
      <ambientLight intensity={0.55} />
      <directionalLight position={[4, 5, 6]} intensity={1.6} />
      <directionalLight position={[-6, -2, 3]} intensity={0.5} color={palette.primary} />
      <Rig>
        <Pages palette={palette} speed={speed} />
        <Core palette={palette} speed={speed} />
        <Chips palette={palette} speed={speed} />
        <Matrix palette={palette} speed={speed} />
      </Rig>
      <Dust palette={palette} speed={speed} />
    </Canvas>
  )
}
