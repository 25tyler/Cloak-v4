import { FileText } from 'lucide-react'
import { motion } from 'framer-motion'

export default function Header() {
  return (
    <motion.header
      initial={{ y: -100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5 }}
      className="glass-effect border-b border-gray-200"
    >
      <div className="container mx-auto px-4 py-6">
        <div className="flex items-center gap-3">
          <motion.div
            whileHover={{ scale: 1.05 }}
            transition={{ duration: 0.2 }}
            className="p-2 bg-blue-50 rounded-lg shadow-sm border border-gray-200"
          >
            <FileText className="w-6 h-6 text-blue-600" />
          </motion.div>
          <div>
            <motion.h1
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
              className="text-2xl font-bold text-gray-900 tracking-tight"
            >
              PDF Converter
            </motion.h1>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3 }}
              className="text-sm text-gray-600"
            >
              Professional PDF Processing Tool
            </motion.p>
          </div>
        </div>
      </div>
    </motion.header>
  )
}

