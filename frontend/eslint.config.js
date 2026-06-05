import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import globals from 'globals';
import prettier from 'eslint-config-prettier';

// Flat config (ESLint 9). The lint gate for the React app: TypeScript correctness
// (typescript-eslint), rules of hooks + exhaustive-deps, React idioms, and
// accessibility (jsx-a11y). `prettier` is last so formatting is owned by Prettier.
const unusedVars = ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }];

export default tseslint.config(
  { ignores: ['dist/**', 'node_modules/**'] },
  js.configs.recommended,

  // TypeScript-specific rules, only on .ts/.tsx
  {
    files: ['src/**/*.{ts,tsx}'],
    extends: [...tseslint.configs.recommended],
    rules: {
      'no-unused-vars': 'off', // handled by the typescript-eslint version below
      '@typescript-eslint/no-unused-vars': unusedVars,
      '@typescript-eslint/no-explicit-any': 'error', // the migration forbids `any` escapes
    },
  },

  // React + accessibility, across all source (the TS parser set above is preserved
  // for .ts/.tsx since this block only adds parserOptions, not a parser)
  {
    files: ['src/**/*.{js,jsx,ts,tsx}'],
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
      'react/prop-types': 'off', // types come from TypeScript now
      'react/no-unescaped-entities': 'off', // apostrophes in prose are valid + readable
    },
  },

  // plain-JS unused-vars (the TS files use the typescript-eslint rule instead)
  {
    files: ['src/**/*.{js,jsx}'],
    rules: { 'no-unused-vars': unusedVars },
  },

  prettier
);
