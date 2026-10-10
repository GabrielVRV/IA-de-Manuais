/**
 * Copia um texto para a área de transferência. Devolve se deu certo.
 *
 * A API moderna (navigator.clipboard) só existe em HTTPS ou localhost. Na intranet,
 * servida por HTTP pelo XAMPP, cai no método antigo de selecionar e copiar.
 */
export async function copyText(text: string): Promise<boolean> {
  if (window.isSecureContext && 'clipboard' in navigator) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // Permissão negada: tenta o método antigo abaixo.
    }
  }
  const area = document.createElement('textarea')
  area.value = text
  area.setAttribute('readonly', '')
  area.style.position = 'fixed'
  area.style.opacity = '0'
  document.body.append(area)
  area.select()
  try {
    // eslint-disable-next-line @typescript-eslint/no-deprecated -- único caminho em páginas HTTP
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    area.remove()
  }
}
