import { useEffect, useRef } from 'react'

import styles from './LoginPage.module.css'

interface Node {
  x: number
  y: number
  vx: number
  vy: number
  r: number
}

const LINK_DISTANCE = 140
const POINTER_REACH = 190

/**
 * Fundo da tela de login: uma rede de pontos que se conectam como neurônios e
 * reagem ao ponteiro. É só decoração: sem suporte a canvas, não desenha nada.
 * Com "reduzir movimento" ativado (comum no Windows corporativo), os pontos
 * continuam flutuando, só que bem mais devagar.
 */
export function NeuralBackdrop() {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    // O jsdom (testes) não tem matchMedia nem canvas: sem eles, não há o que animar.
    if (!canvas || typeof window.matchMedia !== 'function') return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const speed = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0.3 : 1
    const accent = getComputedStyle(canvas).getPropertyValue('--brand-accent').trim() || '#1ec8ff'
    const pointer = { x: -9999, y: -9999 }
    let nodes: Node[] = []
    let width = 0
    let height = 0
    let frame = 0

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = canvas.clientWidth
      height = canvas.clientHeight
      canvas.width = Math.round(width * dpr)
      canvas.height = Math.round(height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      const count = Math.min(110, Math.round((width * height) / 13000))
      nodes = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.35 * speed,
        vy: (Math.random() - 0.5) * 0.35 * speed,
        r: 1 + Math.random() * 1.6,
      }))
    }

    const draw = () => {
      ctx.clearRect(0, 0, width, height)
      ctx.strokeStyle = accent
      ctx.fillStyle = accent

      for (const node of nodes) {
        // Afasta levemente os pontos do ponteiro, como se ele "abrisse caminho".
        const dx = node.x - pointer.x
        const dy = node.y - pointer.y
        const dist = Math.hypot(dx, dy)
        if (dist < POINTER_REACH && dist > 0) {
          const push = (1 - dist / POINTER_REACH) * 0.6
          node.x += (dx / dist) * push
          node.y += (dy / dist) * push
        }
        node.x += node.vx
        node.y += node.vy
        if (node.x < 0 || node.x > width) {
          node.vx *= -1
          node.x = Math.max(0, Math.min(width, node.x))
        }
        if (node.y < 0 || node.y > height) {
          node.vy *= -1
          node.y = Math.max(0, Math.min(height, node.y))
        }
      }

      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i]
        if (!a) continue
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j]
          if (!b) continue
          const dist = Math.hypot(a.x - b.x, a.y - b.y)
          if (dist > LINK_DISTANCE) continue
          ctx.globalAlpha = (1 - dist / LINK_DISTANCE) * 0.28
          ctx.lineWidth = 1
          ctx.beginPath()
          ctx.moveTo(a.x, a.y)
          ctx.lineTo(b.x, b.y)
          ctx.stroke()
        }
        // Ligações com o ponteiro: mais fortes, destacam a interação.
        const toPointer = Math.hypot(a.x - pointer.x, a.y - pointer.y)
        if (toPointer < POINTER_REACH) {
          ctx.globalAlpha = (1 - toPointer / POINTER_REACH) * 0.7
          ctx.lineWidth = 1.2
          ctx.beginPath()
          ctx.moveTo(a.x, a.y)
          ctx.lineTo(pointer.x, pointer.y)
          ctx.stroke()
        }
        ctx.globalAlpha = 0.85
        ctx.beginPath()
        ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.globalAlpha = 1
    }

    const loop = () => {
      draw()
      frame = requestAnimationFrame(loop)
    }

    const onPointerMove = (event: PointerEvent) => {
      const box = canvas.getBoundingClientRect()
      pointer.x = event.clientX - box.left
      pointer.y = event.clientY - box.top
    }
    const onPointerLeave = () => {
      pointer.x = -9999
      pointer.y = -9999
    }

    resize()
    loop()
    window.addEventListener('pointermove', onPointerMove)
    document.addEventListener('pointerleave', onPointerLeave)
    window.addEventListener('resize', resize)

    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('pointermove', onPointerMove)
      document.removeEventListener('pointerleave', onPointerLeave)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return <canvas ref={ref} className={styles.backdrop} aria-hidden="true" />
}
