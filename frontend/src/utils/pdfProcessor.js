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
    const uint8Array = new Uint8Array(arrayBuffer)
    const binaryString = String.fromCharCode.apply(null, uint8Array)
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
    const binaryString2 = atob(responseData)
    const bytes = new Uint8Array(binaryString2.length)
    for (let i = 0; i < binaryString2.length; i++) {
      bytes[i] = binaryString2.charCodeAt(i)
    }
    
    return bytes.buffer
  } catch (error) {
    throw new Error(`Failed to process PDF: ${error.message}`)
  }
}


