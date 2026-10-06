import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StartupError } from './StartupError'

describe('<StartupError />', () => {
  it('shows the reason the app could not start', () => {
    render(<StartupError error={new Error('config.json inválido')} />)

    expect(screen.getByRole('alert')).toHaveTextContent('config.json inválido')
  })
})
