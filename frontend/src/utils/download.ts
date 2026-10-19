/**
 * Safely downloads a file from a URL within the browser's active SSL/auth context.
 * Prevents Chromium 'Fehler – Netzwerkfehler' / ERR_CERT_AUTHORITY_INVALID issues
 * caused by raw `<a download>` anchors on self-signed HTTPS or local IP deployments.
 */
export async function downloadFile(url: string, defaultFilename?: string): Promise<void> {
  if (!url) return

  try {
    const response = await fetch(url, {
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error(`Download failed with status ${response.status}: ${response.statusText}`)
    }

    // Attempt to extract filename from Content-Disposition header
    let filename = defaultFilename
    const disposition = response.headers.get('content-disposition')
    if (disposition && disposition.includes('filename')) {
      const utf8Match = disposition.match(/filename\*=UTF-8''([^"';]+)/i)
      if (utf8Match && utf8Match[1]) {
        filename = decodeURIComponent(utf8Match[1])
      } else {
        const regularMatch = disposition.match(/filename=["']?([^"';]+)["']?/i)
        if (regularMatch && regularMatch[1]) {
          filename = regularMatch[1]
        }
      }
    }

    if (!filename) {
      const urlPath = url.split('?')[0].split('#')[0]
      const lastPart = urlPath.substring(urlPath.lastIndexOf('/') + 1)
      filename = lastPart && lastPart !== 'download' ? lastPart : 'image.png'
    }

    const blob = await response.blob()
    const blobUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)

    setTimeout(() => {
      URL.revokeObjectURL(blobUrl)
    }, 1000)
  } catch (error) {
    console.error('Error downloading file via blob fetch:', error)
    // Fallback: direct anchor trigger
    const link = document.createElement('a')
    link.href = url
    if (defaultFilename) {
      link.download = defaultFilename
    }
    link.target = '_blank'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }
}
