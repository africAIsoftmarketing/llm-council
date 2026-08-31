import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Prepend an eslint-disable directive to every emitted JS chunk. The build
// bundles minified third-party code (jspdf, html2canvas) that references host
// globals (ActiveXObject, Bun, RGBColor); static linters must skip these
// generated artifacts. Runs post-minification so the comment survives.
function eslintDisableBanner() {
  return {
    name: 'eslint-disable-banner',
    enforce: 'post',
    generateBundle(_options, bundle) {
      for (const file of Object.values(bundle)) {
        if (file.type === 'chunk') {
          file.code = '/* eslint-disable */\n' + file.code
        }
      }
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), eslintDisableBanner()],
  server: {
    allowedHosts: true,
    host: '0.0.0.0',
  },
})
