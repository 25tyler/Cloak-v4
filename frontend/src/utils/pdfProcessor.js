/**
 * Process PDF by sending it to the backend encryption API
 * 
 * @param {ArrayBuffer} arrayBuffer - The PDF file as an ArrayBuffer
 * @param {number} secretKey - Optional secret key for encryption (defaults to backend default)
 * @returns {Promise<ArrayBuffer>} - The encrypted PDF as an ArrayBuffer
 */
export async function processPDF(arrayBuffer, secretKey = null) {
  try {
    // Use relative URL - works in both development (Vite proxy) and production (Vercel)
    // Vercel will route /api/* to the serverless function
    const API_URL = import.meta.env.VITE_API_URL || ''
    const apiEndpoint = API_URL ? `${API_URL}/api/encrypt/pdf` : '/api/encrypt/pdf'
    
    // Convert ArrayBuffer to base64 for Vercel serverless function
    // Process in chunks to avoid "Maximum call stack size exceeded" error
    const uint8Array = new Uint8Array(arrayBuffer)
    const chunkSize = 8192 // Process 8KB at a time
    let binaryString = ''
    
    for (let i = 0; i < uint8Array.length; i += chunkSize) {
      const chunk = uint8Array.slice(i, i + chunkSize)
      binaryString += String.fromCharCode.apply(null, chunk)
    }
    
    const base64 = btoa(binaryString)
    
    // Create request body
    const requestBody = {
      file: base64,
      filename: 'document.pdf'
    }
    
    // Add secret key if provided
    if (secretKey !== null) {
      requestBody.secret_key = secretKey
    }
    
    // Send to backend API
    const response = await fetch(apiEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    })
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: response.statusText }))
      throw new Error(errorData.error || `Server error: ${response.status} ${response.statusText}`)
    }
    
    // Get encrypted PDF - Vercel returns base64 encoded
    const responseData = await response.text()
    
    // Decode base64 to ArrayBuffer
    // Process in chunks to avoid stack overflow for large files
    const binaryString2 = atob(responseData)
    const bytes = new Uint8Array(binaryString2.length)
    const decodeChunkSize = 8192
    
    for (let i = 0; i < binaryString2.length; i += decodeChunkSize) {
      const end = Math.min(i + decodeChunkSize, binaryString2.length)
      for (let j = i; j < end; j++) {
        bytes[j] = binaryString2.charCodeAt(j)
      }
    }
    
    return bytes.buffer
  } catch (error) {
    throw new Error(`Failed to process PDF: ${error.message}`)
  }
}


