import ui from '@/styles/ui.module.css'

import styles from './ManualsAdmin.module.css'

/** Escolha de mandar as figuras para a IA, com o aviso de custo. */
export function FigureCheckbox({
  checked,
  disabled = false,
  label = 'Descrever as figuras com IA',
  onChange,
}: {
  readonly checked: boolean
  readonly disabled?: boolean
  readonly label?: string
  readonly onChange: (value: boolean) => void
}) {
  return (
    <span className={styles.figureOption}>
      <label className={styles.checkbox}>
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(event) => {
            onChange(event.target.checked)
          }}
        />
        {label}
      </label>
      <span className={ui.hint}>
        Fotos, diagramas, desenhos técnicos e PDFs escaneados viram texto pesquisável. Uma chamada
        de IA por página com figuras; o que já foi descrito não é pago de novo.
      </span>
    </span>
  )
}
