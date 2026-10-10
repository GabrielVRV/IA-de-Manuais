import { createContext, use } from 'react'

import { type Brand, DEFAULT_BRAND } from './brand'

/** A marca carregada em main.tsx; sem provedor (ex.: testes), vale a marca neutra. */
export const BrandContext = createContext<Brand>(DEFAULT_BRAND)

export function useBrand(): Brand {
  return use(BrandContext)
}
