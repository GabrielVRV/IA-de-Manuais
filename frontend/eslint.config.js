import js from '@eslint/js'
import { defineConfig, globalIgnores } from 'eslint/config'
import prettier from 'eslint-config-prettier/flat'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'
import tseslint from 'typescript-eslint'

/** Proíbe imports que violem a regra de dependência entre camadas. */
const forbidImports = (groups, message) => ({
  'no-restricted-imports': ['error', { patterns: [{ group: groups, message }] }],
})

export default defineConfig([
  globalIgnores(['dist', 'coverage']),

  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.strictTypeChecked,
      tseslint.configs.stylisticTypeChecked,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },

  // --------------------------------------------------------------------- //
  // Clean Architecture: regra de dependência (as setas apontam para dentro)
  // --------------------------------------------------------------------- //
  {
    files: ['src/features/*/domain/**'],
    rules: forbidImports(
      ['react', 'react-dom', 'zod', '**/infrastructure/**', '**/presentation/**', '@/shared/**'],
      'O domínio é puro: não depende de frameworks nem de camadas externas.',
    ),
  },
  {
    files: ['src/features/*/infrastructure/**'],
    rules: forbidImports(
      ['react', 'react-dom', '**/presentation/**'],
      'A infraestrutura não conhece a interface do usuário.',
    ),
  },
  {
    files: ['src/features/*/presentation/**'],
    ignores: ['**/*.test.{ts,tsx}'],
    rules: forbidImports(
      ['**/infrastructure/**'],
      'A apresentação depende só das portas do domínio; a implementação é injetada em main.tsx.',
    ),
  },
  {
    files: ['src/shared/**'],
    rules: forbidImports(
      ['@/features/**', '@/app/**'],
      'Código compartilhado não pode depender de funcionalidades específicas.',
    ),
  },

  prettier,
])
