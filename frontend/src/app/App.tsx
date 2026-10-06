import { ApiStatus } from '@/features/health/presentation/ApiStatus'

import styles from './App.module.css'
import { Layout } from './Layout'

export function App() {
  return (
    <Layout>
      <section className={styles.intro}>
        <h2 className={styles.heading}>Tire suas dúvidas sobre os manuais dos equipamentos</h2>
        <p className={styles.lead}>
          Em breve você poderá perguntar em linguagem natural e receber a resposta com a indicação
          do manual e da página de origem.
        </p>
      </section>
      <ApiStatus />
    </Layout>
  )
}
