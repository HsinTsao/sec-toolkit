import { defineConfig } from '@hey-api/openapi-ts'

export default defineConfig({
  input: 'http://localhost:8000/api/openapi.json',
  output: {
    path: 'src/api/generated',
  },
  client: '@hey-api/client-axios',
})
