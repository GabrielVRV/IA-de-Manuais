import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// O jsdom não implementa rolagem; o chat a usa para mostrar a última mensagem.
Element.prototype.scrollIntoView = vi.fn()

afterEach(() => {
  cleanup()
})
