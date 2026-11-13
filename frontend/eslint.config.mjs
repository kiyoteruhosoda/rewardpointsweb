import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import sonarjs from 'eslint-plugin-sonarjs'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  // Build output and dependencies are not linted
  {
    ignores: ['dist/**', 'coverage/**', 'dev-dist/**', 'node_modules/**'],
  },

  js.configs.recommended,

  ...tseslint.configs.strictTypeChecked,

  {
    plugins: {
      'react-hooks': reactHooks,
      sonarjs,
    },

    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },

    rules: {
      '@typescript-eslint/no-floating-promises': 'error',

      '@typescript-eslint/no-explicit-any': 'error',

      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
        },
      ],

      '@typescript-eslint/consistent-type-imports': 'error',

      'react-hooks/rules-of-hooks': 'error',

      'react-hooks/exhaustive-deps': 'error',

      'sonarjs/cognitive-complexity': ['error', 15],

      // Stringifying numbers is unambiguous and safe (used to embed IDs in URLs).
      // The point of this rule is catching objects or null slipping in.
      '@typescript-eslint/restrict-template-expressions': [
        'error',
        {
          allowNumber: true,
        },
      ],
    },
  },

  // Config files (Node side) are not linted with type information
  {
    files: ['*.config.{ts,mts,mjs}', 'eslint.config.mjs'],
    extends: [tseslint.configs.disableTypeChecked],
  },
)
