import { Layout } from './Layout'
import styles from './StartupError.module.css'

/** Exibida quando a aplicação não consegue nem iniciar (ex.: config.json ausente). */
export function StartupError({ error }: { readonly error: unknown }) {
  const message = error instanceof Error ? error.message : String(error)

  return (
    <Layout>
      <section className={styles.box} role="alert">
        <h2 className={styles.title}>Não foi possível iniciar a aplicação</h2>
        <p className={styles.message}>{message}</p>
        <p className={styles.hint}>
          Se você é o administrador, verifique o arquivo <code>config.json</code> na pasta da
          aplicação.
        </p>
      </section>
    </Layout>
  )
}
