import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

const alias = (path: string) => fileURLToPath(new URL(path, import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@ew/core': alias('./packages/core/src/index.ts'),
      '@ew/commands': alias('./packages/commands/src/index.ts'),
      '@ew/graph': alias('./packages/graph/src/index.ts'),
      '@ew/router': alias('./packages/graph-router/src/index.ts'),
      '@ew/validation': alias('./packages/validation/src/index.ts'),
      '@ew/plugin-api': alias('./packages/plugin-api/src/index.ts'),
      '@ew/persistence': alias('./packages/persistence/src/index.ts'),
      '@ew/workbench-ui': alias('./packages/workbench-ui/src/index.ts'),
      '@plugins/example-electronics': alias('./plugins/example-electronics/src/index.ts')
    }
  },
  root: '.',
  build: { outDir: 'dist' }
});
