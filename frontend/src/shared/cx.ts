/** Junta nomes de classe, ignorando os vazios: cx(ui.button, active && ui.primary). */
export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ')
}
