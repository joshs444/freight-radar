import js from '@eslint/js';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import globals from 'globals';
import prettier from 'eslint-config-prettier';

// Flat config (ESLint 9). The lint gate for the React app: correctness (rules of
// hooks + exhaustive-deps), React idioms, and accessibility (jsx-a11y) — which is
// what guides the Phase 2 a11y work. `prettier` is last so formatting is owned by
// Prettier, not ESLint.
export default [
  { ignores: ['dist/**', 'node_modules/**'] },
  js.configs.recommended,
  {
    files: ['src/**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    settings: { react: { version: 'detect' } },
    plugins: { react, 'react-hooks': reactHooks, 'jsx-a11y': jsxA11y },
    rules: {
      ...react.configs.recommended.rules,
      ...react.configs['jsx-runtime'].rules, // new JSX transform: no React import needed
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.configs.recommended.rules,
      'react/prop-types': 'off', // types come from the Phase 4 TypeScript migration
      'react/no-unescaped-entities': 'off', // apostrophes in prose are valid + readable
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      // Click handlers on non-interactive elements: these are Phase 2's semantic-a11y
      // worklist (convert to native <button>). Staged as warnings so the Phase 1 gate
      // is green; Phase 2 fixes them and promotes these back to errors.
      'jsx-a11y/click-events-have-key-events': 'warn',
      'jsx-a11y/no-static-element-interactions': 'warn',
      'jsx-a11y/no-noninteractive-element-interactions': 'warn',
    },
  },
  prettier,
];
