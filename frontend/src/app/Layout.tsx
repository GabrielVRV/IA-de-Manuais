import { type ReactNode, useState } from 'react'

import { useBrand } from '@/shared/brand/brand-context'
import { cx } from '@/shared/cx'
import { VisorBot } from '@/shared/mascot/VisorBot'

import styles from './Layout.module.css'

interface LayoutProps {
  readonly children: ReactNode
  /** Navegação principal, ao lado da marca. */
  readonly nav?: ReactNode
  /** Elementos à direita no cabeçalho (ex.: status do servidor, usuário). */
  readonly actions?: ReactNode
  /** Conteúdo de ponta a ponta (ex.: o chat com o histórico ao lado). */
  readonly fullWidth?: boolean
}

const ICON_GAZE = { x: 0, y: 0.2 }

export function Layout({ children, nav, actions, fullWidth = false }: LayoutProps) {
  const brand = useBrand()
  const [logoBroken, setLogoBroken] = useState(false)

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={cx(styles.inner, styles.headerContent, fullWidth && styles.full)}>
          <div className={styles.start}>
            <h1 className={styles.brand}>
              <span className={styles.brandIcon} aria-hidden="true">
                {brand.iconUrl && !logoBroken ? (
                  <img
                    src={brand.iconUrl}
                    alt=""
                    onError={() => {
                      setLogoBroken(true)
                    }}
                  />
                ) : (
                  <VisorBot mood="happy" gaze={ICON_GAZE} />
                )}
              </span>
              {brand.name}
            </h1>
            {nav}
          </div>
          {actions}
        </div>
      </header>
      <main className={cx(styles.main, !fullWidth && styles.inner)}>{children}</main>
    </div>
  )
}
