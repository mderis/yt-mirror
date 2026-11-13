// ESLint configuration of the yt-mirror frontend (docs/CODING-STANDARDS.md section 4).
import vueI18n from '@intlify/eslint-plugin-vue-i18n'
import prettier from 'eslint-config-prettier'
import vue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'coverage', 'src/api/schema.d.ts'] },
  ...tseslint.configs.strict,
  ...vue.configs['flat/recommended'],
  {
    files: ['**/*.vue'],
    languageOptions: { parserOptions: { parser: tseslint.parser } },
  },
  {
    plugins: { '@intlify/vue-i18n': vueI18n },
    rules: {
      // All user-visible text comes from src/i18n (R-PL-06). No text in templates.
      '@intlify/vue-i18n/no-raw-text': 'error',
      // No `any` without a comment explaining it.
      '@typescript-eslint/no-explicit-any': 'error',
      // Components do not call fetch. Only the API client does.
      'no-restricted-globals': [
        'error',
        { name: 'fetch', message: 'Use the API client in src/api/client.ts.' },
      ],
    },
  },
  {
    files: ['src/api/client.ts', 'tests/**'],
    rules: { 'no-restricted-globals': 'off' },
  },
  prettier,
)
