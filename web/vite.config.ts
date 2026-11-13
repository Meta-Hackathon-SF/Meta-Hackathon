import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import { museChatPlugin } from './museChatPlugin'

export default defineConfig({
  plugins: [react(), tailwindcss(), museChatPlugin()],
})
