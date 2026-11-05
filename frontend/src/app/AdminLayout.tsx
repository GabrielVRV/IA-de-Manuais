import { NavLink, Outlet } from 'react-router'

import { cx } from '@/shared/cx'

import styles from './AdminLayout.module.css'

interface AdminLink {
  readonly to: string
  readonly label: string
}

interface AdminSection {
  readonly title: string
  readonly links: readonly AdminLink[]
}

/**
 * Menu da administração. "Geral" vale para o sistema todo (usuários, consumo, limites);
 * cada assistente tem a própria seção, para que um assistente novo (ex.: o da TI)
 * entre aqui sem mudar a navegação.
 */
const ADMIN_SECTIONS: readonly AdminSection[] = [
  {
    title: 'Geral',
    links: [
      { to: 'usuarios', label: 'Usuários' },
      { to: 'acessos', label: 'Acessos' },
      { to: 'consumo', label: 'Consumo' },
      { to: 'configuracoes', label: 'Configurações' },
    ],
  },
  {
    title: 'Assistente de Engenharia',
    links: [{ to: 'manuais', label: 'Manuais' }],
  },
]

/** Área de administração: menu lateral por seção e a tela escolhida ao lado. */
export function AdminLayout() {
  const link = ({ isActive }: { isActive: boolean }) => cx(styles.link, isActive && styles.active)
  return (
    <div className={styles.admin}>
      <nav className={styles.sidebar} aria-label="Administração">
        <div className={styles.sidebarInner}>
          {ADMIN_SECTIONS.map((section) => (
            <div key={section.title} className={styles.section}>
              <h2 className={styles.sectionTitle}>{section.title}</h2>
              <ul className={styles.links}>
                {section.links.map((item) => (
                  <li key={item.to}>
                    <NavLink to={item.to} className={link}>
                      {item.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </nav>
      <div className={styles.content}>
        <Outlet />
      </div>
    </div>
  )
}
