import { resolve } from 'path';
import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    outDir: '../web/pipecat',
    emptyOutDir: true,
    lib: {
      entry: resolve(import.meta.dirname, 'src/voice-client.js'),
      formats: ['es'],
      fileName: () => 'voice-client.js',
    },
  },
});
