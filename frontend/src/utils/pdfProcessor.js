/**
 * Process PDF by sending it to the backend encryption API
 * 
 * @param {ArrayBuffer} arrayBuffer - The PDF file as an ArrayBuffer
 * @param {number} secretKey - Optional secret key for encryption (defaults to backend default)
 * @returns {Promise<ArrayBuffer>} - The encrypted PDF as an ArrayBuffer
 */
export async function processPDF(arrayBuffer, secretKey = null) {
  try {
    // Check file size (Vercel has ~4.5MB request limit, base64 adds ~33% overhead)
    // So we limit to ~3.4MB original file size to be safe
    const MAX_FILE_SIZE = 3.4 * 1024 * 1024 // 3.4 MB in bytes
    if (arrayBuffer.byteLength > MAX_FILE_SIZE) {
      const fileSizeMB = (arrayBuffer.byteLength / (1024 * 1024)).toFixed(2)
      const maxSizeMB = (MAX_FILE_SIZE / (1024 * 1024)).toFixed(2)
      throw new Error(`File too large: ${fileSizeMB} MB. Maximum size is ${maxSizeMB} MB.`)
    }
    // Use relative URL - works in both development (Vite proxy) and production (Vercel)
    // Vercel will route /api/* to the serverless function
    const API_URL = import.meta.env.VITE_API_URL || ''
    const apiEndpoint = API_URL ? `${API_URL}/api/encrypt/pdf` : '/api/encrypt/pdf'
    
    // Convert ArrayBuffer to base64 for Vercel serverless function
    // Process in chunks to avoid "Maximum call stack size exceeded" error
    // Use efficient chunking that works for files of any size
    const uint8Array = new Uint8Array(arrayBuffer)
    const chunkSize = 0x8000 // 32KB chunks for optimal performance
    const chunks = []
    
    for (let i = 0; i < uint8Array.length; i += chunkSize) {
      const chunk = uint8Array.slice(i, Math.min(i + chunkSize, uint8Array.length))
      chunks.push(String.fromCharCode.apply(null, chunk))
    }
    
    // Concatenate all chunks and encode to base64
    const binaryString = chunks.join('')
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
    const decodeChunkSize = 0x8000 // 32KB chunks for optimal performance
    
    // Process in chunks for memory efficiency
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


