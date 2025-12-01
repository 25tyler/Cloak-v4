import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, Download, Loader2, CheckCircle2, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import PDFPreview from './PDFPreview'
import { processPDF } from '../utils/pdfProcessor'

export default function PDFConverter() {
  const [inputFile, setInputFile] = useState(null)
  const [outputFile, setOutputFile] = useState(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState(null)
  const [inputPreview, setInputPreview] = useState(null)

  const onDrop = useCallback((acceptedFiles) => {
    const file = acceptedFiles[0]
    if (file && file.type === 'application/pdf') {
      // Check file size (3.4MB limit due to Vercel serverless function limits)
      const MAX_FILE_SIZE = 3.4 * 1024 * 1024 // 3.4 MB
      if (file.size > MAX_FILE_SIZE) {
        const fileSizeMB = (file.size / (1024 * 1024)).toFixed(2)
        const maxSizeMB = (MAX_FILE_SIZE / (1024 * 1024)).toFixed(2)
        setError(`File too large: ${fileSizeMB} MB. Maximum size is ${maxSizeMB} MB.`)
        return
      }
      
      setInputFile(file)
      setError(null)
      setOutputFile(null)
      
      // Create preview URL
      const url = URL.createObjectURL(file)
      setInputPreview(url)
    } else {
      setError('Please upload a valid PDF file')
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: false
  })

  const handleConvert = async () => {
    if (!inputFile) return

    setIsProcessing(true)
    setError(null)

    try {
      const arrayBuffer = await inputFile.arrayBuffer()
      const processedPdfBytes = await processPDF(arrayBuffer)
      
      // Create blob and URL for download
      const blob = new Blob([processedPdfBytes], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)
      setOutputFile({ blob, url, name: `converted_${inputFile.name}` })
    } catch (err) {
      setError(err.message || 'Failed to process PDF')
      console.error('PDF processing error:', err)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleDownload = () => {
    if (!outputFile) return
    
    const link = document.createElement('a')
    link.href = outputFile.url
    link.download = outputFile.name
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const handleClear = () => {
    if (inputPreview) URL.revokeObjectURL(inputPreview)
    if (outputFile?.url) URL.revokeObjectURL(outputFile.url)
    setInputFile(null)
    setOutputFile(null)
    setInputPreview(null)
    setError(null)
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex flex-col gap-8 items-center">
        {/* Input PDF Widget - Top */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="w-full max-w-[600px]"
        >
          <motion.div
            whileHover={{ y: -2 }}
            className="glass-effect rounded-xl p-8 shadow-lg border-gray-200 aspect-square flex flex-col"
            style={{ minHeight: '600px', maxHeight: '700px' }}
          >
            <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5 text-blue-600" />
              Input PDF
            </h2>

            {!inputFile ? (
              <motion.div
                {...getRootProps()}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                animate={isDragActive ? { scale: 1.05, borderColor: 'rgba(59, 130, 246, 0.5)' } : {}}
                className={`
                  border-2 border-dashed rounded-xl p-16 text-center cursor-pointer flex-1 flex flex-col items-center justify-center
                  transition-all duration-300
                  ${isDragActive
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
                  }
                `}
              >
                <input {...getInputProps()} />
                <motion.div
                  animate={isDragActive ? { y: [-5, 5, -5] } : {}}
                  transition={{ duration: 1, repeat: Infinity, ease: 'easeInOut' }}
                >
                  <Upload className={`w-16 h-16 mx-auto mb-6 ${isDragActive ? 'text-blue-600' : 'text-gray-400'}`} />
                </motion.div>
                <p className="text-gray-700 font-semibold text-lg mb-2">
                  {isDragActive ? 'Drop PDF here' : 'Drag & drop PDF file'}
                </p>
                <p className="text-sm text-gray-500">or click to browse</p>
              </motion.div>
            ) : (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-4"
              >
                <motion.div
                  whileHover={{ scale: 1.01 }}
                  className="flex items-center justify-between p-6 bg-gray-50 rounded-lg border border-gray-200"
                >
                  <div className="flex items-center gap-4">
                    <FileText className="w-10 h-10 text-blue-600" />
                    <div>
                      <p className="font-semibold text-gray-900 text-lg">{inputFile.name}</p>
                      <p className="text-sm text-gray-600 mt-1">
                        {(inputFile.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                  </div>
                  <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={handleClear}
                    className="p-3 hover:bg-gray-200 rounded-lg transition-colors"
                    aria-label="Remove file"
                  >
                    <X className="w-6 h-6 text-gray-600" />
                  </motion.button>
                </motion.div>

                {inputPreview && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.3 }}
                    className="mt-4"
                  >
                    <PDFPreview fileUrl={inputPreview} />
                  </motion.div>
                )}

                <motion.button
                  whileHover={!isProcessing ? { scale: 1.02 } : {}}
                  whileTap={!isProcessing ? { scale: 0.98 } : {}}
                  onClick={handleConvert}
                  disabled={isProcessing}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-4 px-8 rounded-lg shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3 text-lg"
                >
                  {isProcessing ? (
                    <>
                      <Loader2 className="w-6 h-6 animate-spin" />
                      <span>Processing...</span>
                    </>
                  ) : (
                    <>
                      <FileText className="w-6 h-6" />
                      <span>Convert PDF</span>
                    </>
                  )}
                </motion.button>
              </motion.div>
            )}

            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm"
                >
                  Error: {error}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </motion.div>

        {/* Output PDF Widget - Bottom */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: 'easeOut' }}
          className="w-full max-w-[600px]"
        >
          <motion.div
            whileHover={{ y: -2 }}
            className={`rounded-xl p-8 shadow-lg aspect-square flex flex-col transition-all duration-300 ${
              !outputFile 
                ? 'bg-gray-50 border-2 border-dashed border-gray-300' 
                : 'glass-effect border border-gray-200'
            }`}
            style={{ minHeight: '600px', maxHeight: '700px' }}
          >
            <h2 className={`text-xl font-semibold mb-4 flex items-center gap-2 ${
              !outputFile ? 'text-gray-400' : 'text-gray-900'
            }`}>
              <Download className={`w-5 h-5 ${!outputFile ? 'text-gray-400' : 'text-blue-600'}`} />
              Output PDF
            </h2>

            {!outputFile ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="p-16 text-center flex-1 flex flex-col items-center justify-center"
              >
                <motion.div
                  animate={{ scale: [1, 1.05, 1] }}
                  transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                  className="w-20 h-20 mx-auto mb-6 bg-gray-200 rounded-full flex items-center justify-center border-2 border-dashed border-gray-300"
                >
                  <FileText className="w-10 h-10 text-gray-400" />
                </motion.div>
                <p className="text-gray-500 font-medium text-base">Converted PDF will appear here</p>
                <p className="text-xs text-gray-400 mt-2">Upload and convert a PDF to get started</p>
              </motion.div>
            ) : (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3 }}
                className="space-y-4 flex-1"
              >
                <motion.div
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  whileHover={{ scale: 1.01 }}
                  className="flex items-center justify-between p-6 bg-green-50 rounded-lg border border-green-200"
                >
                  <div className="flex items-center gap-4">
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: 'spring', stiffness: 200 }}
                    >
                      <CheckCircle2 className="w-10 h-10 text-green-600" />
                    </motion.div>
                    <div>
                      <p className="font-semibold text-gray-900 text-lg">{outputFile.name}</p>
                      <p className="text-sm text-gray-600 mt-1">Ready to download</p>
                    </div>
                  </div>
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.3, delay: 0.1 }}
                  className="mt-4"
                >
                  <PDFPreview fileUrl={outputFile.url} />
                </motion.div>
              </motion.div>
            )}
            
            {/* Download Button - Always visible */}
            <motion.button
              whileHover={outputFile ? { scale: 1.02 } : {}}
              whileTap={outputFile ? { scale: 0.98 } : {}}
              onClick={handleDownload}
              disabled={!outputFile}
              className={`w-full font-semibold py-4 px-8 rounded-lg shadow-md transition-all flex items-center justify-center gap-3 text-lg ${
                outputFile
                  ? 'bg-green-600 hover:bg-green-700 text-white hover:shadow-lg cursor-pointer'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
            >
              <Download className={`w-6 h-6 ${!outputFile ? 'text-gray-500' : ''}`} />
              <span>{outputFile ? 'Download PDF' : 'No output available'}</span>
            </motion.button>
          </motion.div>
        </motion.div>
      </div>
    </div>
  )
}

