import type { ReactNode } from 'react'

import styles from './Layout.module.css'

export function Layout({ children }: { readonly children: ReactNode }) {
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.inner}>
          <h1 className={styles.brand}>Assistente de Manuais</h1>
        </div>
      </header>
      <main className={styles.inner}>{children}</main>
    </div>
  )
}
