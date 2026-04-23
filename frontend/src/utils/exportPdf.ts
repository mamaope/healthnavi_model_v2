/**
 * Export a DOM element to PDF using html2canvas and jspdf.
 */
import html2canvas from 'html2canvas'
import { jsPDF } from 'jspdf'

export async function exportElementToPdf(
  element: HTMLElement,
  filename: string = 'report.pdf',
  options?: { scale?: number; useCORS?: boolean }
): Promise<void> {
  const scale = options?.scale ?? 2
  const canvas = await html2canvas(element, {
    scale,
    useCORS: options?.useCORS ?? true,
    logging: false,
    backgroundColor: '#ffffff',
    windowWidth: element.scrollWidth,
    windowHeight: element.scrollHeight,
  })

  const imgData = canvas.toDataURL('image/png', 1.0)
  const imgWidth = 210
  const pageHeight = 297
  const imgHeight = (canvas.height * imgWidth) / canvas.width
  let heightLeft = imgHeight
  let position = 0

  const pdf = new jsPDF('p', 'mm', 'a4')
  pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
  heightLeft -= pageHeight

  while (heightLeft > 0) {
    position = heightLeft - imgHeight
    pdf.addPage()
    pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
    heightLeft -= pageHeight
  }

  pdf.save(filename)
}
