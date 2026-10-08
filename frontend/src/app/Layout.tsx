import type { ReactNode } from 'react'

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
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={cx(styles.inner, styles.headerContent)}>
          <div className={styles.start}>
            <h1 className={styles.brand}>Assistente de Manuais</h1>
            {nav}
          </div>
          {actions}
        </div>
      </header>
      <main className={cx(styles.inner, styles.main)}>{children}</main>
    </div>
  )
}
