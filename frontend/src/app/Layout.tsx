import type { ReactNode } from 'react'

import { useBrand } from '@/shared/brand/brand-context'
import { cx } from '@/shared/cx'

import styles from './Layout.module.css'

interface LayoutProps {
  readonly children: ReactNode
  /** Navegação principal, ao lado da marca. */
  readonly nav?: ReactNode
  /** Elementos à direita no cabeçalho (ex.: status do servidor, usuário). */
  readonly actions?: ReactNode
}

export function Layout({ children, nav, actions }: LayoutProps) {
  const brand = useBrand()
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={cx(styles.inner, styles.headerContent)}>
          <div className={styles.start}>
            <h1 className={styles.brand}>{brand.name}</h1>
            {nav}
          </div>
          {actions}
        </div>
      </header>
      <main className={cx(styles.inner, styles.main)}>{children}</main>
    </div>
  )
}
