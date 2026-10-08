import type { ReactNode } from 'react'

import styles from './Layout.module.css'

interface LayoutProps {
  readonly children: ReactNode
  /** Elementos à direita no cabeçalho (ex.: status do servidor). */
  readonly actions?: ReactNode
}

export function Layout({ children, actions }: LayoutProps) {
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={[styles.inner, styles.headerContent].join(' ')}>
          <h1 className={styles.brand}>Assistente de Manuais</h1>
          {actions}
        </div>
      </header>
      <main className={[styles.inner, styles.main].join(' ')}>{children}</main>
    </div>
  )
}
