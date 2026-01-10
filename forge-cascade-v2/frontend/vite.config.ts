import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // SECURITY FIX (Audit 4 - L7): Disable source maps in production
  // to prevent exposing source code structure
  build: {
    sourcemap: false,
  },
})
