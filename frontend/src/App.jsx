import { useState } from 'react'
import PDFConverter from './components/PDFConverter'
import Header from './components/Header'
import ParticleBackground from './components/ParticleBackground'

function App() {
  return (
    <div className="min-h-screen relative">
      <ParticleBackground />
      <div className="relative z-10">
        <Header />
        <main className="container mx-auto px-4 py-12">
          <PDFConverter />
        </main>
      </div>
    </div>
  )
}

export default App

