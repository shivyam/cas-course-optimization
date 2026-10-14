// ESLint config (flat config format): https://eslint.org/docs/latest/use/configure/
// Run with `npm run lint`. Formatting is left to Prettier (see .prettierrc).
import js from '@eslint/js'
import prettier from 'eslint-config-prettier'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  // Never lint build output.
  { ignores: ['dist', 'coverage'] },

  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended, // rules of hooks, exhaustive deps
      reactRefresh.configs.vite, // keeps hot reload working in dev
    ],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
    rules: {
      // Team naming conventions (Development Plan):
      // camelCase for variables and functions, PascalCase for components and types.
      '@typescript-eslint/naming-convention': [
        'error',
        { selector: 'default', format: ['camelCase'], leadingUnderscore: 'allow' },
        // PascalCase allowed for React components stored in variables.
        { selector: 'variable', format: ['camelCase', 'PascalCase'] },
        // PascalCase allowed because React components are functions.
        { selector: 'function', format: ['camelCase', 'PascalCase'] },
        { selector: 'typeLike', format: ['PascalCase'] },
        { selector: 'import', format: ['camelCase', 'PascalCase'] },
        // Object keys often mirror external data (API JSON, CSS, URLs), so skip them.
        { selector: ['objectLiteralProperty', 'typeProperty'], format: null },
      ],
    },
  },

  // Must be last: turns off ESLint rules that would fight with Prettier.
  prettier,
)
