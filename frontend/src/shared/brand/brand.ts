import { z } from 'zod'

/**
 * Identidade visual da instalação, lida em tempo de execução de `brand/brand.json`
 * (ao lado do index.html). A pasta `brand/` não é versionada: cada empresa coloca ali
 * o próprio nome, logo e cores, e o repositório continua com uma marca neutra.
 */
export interface Brand {
  readonly name: string
  readonly tagline: string
  /** Caminho da logo relativo ao index.html (ex.: "./brand/logo.webp"). */
  readonly logoUrl: string | null
  /** Versão pequena para o cabeçalho; sem ela, vale a logo (ou o robô, sem logo). */
  readonly iconUrl: string | null
  readonly colors: {
    readonly primary: string
    readonly accent: string
  }
  /** Perguntas de exemplo exibidas na tela de login. */
  readonly examples: readonly string[]
}

export const DEFAULT_BRAND: Brand = {
  name: 'Assistente de Manuais',
  tagline:
    'Pergunte em linguagem natural e receba a resposta direto dos manuais técnicos, com a página de origem.',
  logoUrl: null,
  iconUrl: null,
  colors: { primary: '#0046b4', accent: '#1ec8ff' },
  examples: [
    'Qual o torque de aperto dos parafusos da base?',
    'Como faço a manutenção preventiva do motorredutor?',
    'Qual a sequência de montagem do equipamento?',
    'Onde fica o diagrama elétrico do painel?',
  ],
}

const hexColor = z.string().regex(/^#[0-9a-f]{6}$/i, 'use uma cor no formato #rrggbb')

const brandSchema = z.object({
  name: z.string().trim().min(1).max(60).optional(),
  tagline: z.string().trim().min(1).max(200).optional(),
  logoUrl: z.string().trim().min(1).optional(),
  iconUrl: z.string().trim().min(1).optional(),
  colors: z.object({ primary: hexColor.optional(), accent: hexColor.optional() }).optional(),
  examples: z.array(z.string().trim().min(1).max(120)).min(1).optional(),
})

export class BrandError extends Error {
  override readonly name = 'BrandError'
}

export function parseBrand(raw: unknown): Brand {
  const result = brandSchema.safeParse(raw)
  if (!result.success) {
    throw new BrandError(`brand.json inválido: ${z.prettifyError(result.error)}`, {
      cause: result.error,
    })
  }
  const data = result.data
  return {
    name: data.name ?? DEFAULT_BRAND.name,
    tagline: data.tagline ?? DEFAULT_BRAND.tagline,
    logoUrl: data.logoUrl ?? DEFAULT_BRAND.logoUrl,
    iconUrl: data.iconUrl ?? data.logoUrl ?? DEFAULT_BRAND.iconUrl,
    colors: { ...DEFAULT_BRAND.colors, ...data.colors },
    examples: data.examples ?? DEFAULT_BRAND.examples,
  }
}

/**
 * Carrega a marca. Nunca falha: sem `brand.json` (ou com um arquivo inválido)
 * a aplicação segue com a marca neutra, pois a identidade visual é opcional.
 */
export async function loadBrand(
  url = './brand/brand.json',
  fetchFn: typeof fetch = globalThis.fetch.bind(globalThis),
): Promise<Brand> {
  try {
    const response = await fetchFn(url, { cache: 'no-store' })
    if (!response.ok) return DEFAULT_BRAND
    return parseBrand(await response.json())
  } catch (error) {
    console.warn('Usando a marca padrão:', error)
    return DEFAULT_BRAND
  }
}

/** Publica as cores da marca como variáveis CSS, das quais a paleta é derivada. */
export function applyBrand(brand: Brand, root: HTMLElement = document.documentElement): void {
  root.style.setProperty('--brand-primary', brand.colors.primary)
  root.style.setProperty('--brand-accent', brand.colors.accent)
  document.title = brand.name
}
