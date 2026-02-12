// Personal ESLint configuration for linting arbitrary files
// Usage: eslint --config ~/.config/eslint/eslint.config.mjs <file>
// Or use the alias: eslint-global <file>
//
// Note: Required plugins are automatically installed via chezmoi's
// run_once_before_install-global-npm-packages.sh.tmpl script

import js from '@eslint/js';
import globals from 'globals';
import typescriptEslintPlugin from '@typescript-eslint/eslint-plugin';
import tsParser from '@typescript-eslint/parser';
import prettierConfig from 'eslint-config-prettier';
import jestPlugin from 'eslint-plugin-jest';
import jsdoc from 'eslint-plugin-jsdoc';

export default [
  {
    ignores: [
      'node_modules/**/*',
      'dist/**/*',
      'build/**/*',
      'coverage/**/*',
      '*.config.{js,cjs,mjs}',
    ],
  },
  js.configs.recommended,
  {
    files: ['**/*'],
    plugins: {
      '@typescript-eslint': typescriptEslintPlugin,
      jsdoc,
    },
    rules: {
      // What the rule does: Reports comments containing the configured term so they are resolved or tracked.
      'no-warning-comments': [
        'error',
        { terms: ['todo', 'fixme', 'placeholder'], location: 'anywhere' },
      ],

      // What the rule does: Requires explicit return type annotations on all functions and methods. This improves code readability and can help catch type errors early.
      '@typescript-eslint/explicit-function-return-type': 'error',

      // What the rule does: Disallows the use of the 'any' type, requiring more specific types. This enforces type safety throughout the codebase.
      '@typescript-eslint/no-explicit-any': 'error',

      // What the rule does: Disallows empty function bodies. Empty functions are often a sign of incomplete implementation or unnecessary code.
      '@typescript-eslint/no-empty-function': 'off',

      // What the rule does: Disallows unused variables, parameters, and imports. This helps identify dead code and ensures all declared variables are actually used.
      '@typescript-eslint/no-unused-vars': [
        'warn',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
        },
      ],

      // What the rule does: Ensures that only Error objects (or allowed exceptions) are thrown, preventing throwing of non-Error values. This improves error handling and stack trace quality.
      '@typescript-eslint/only-throw-error': [
        'error',
        {
          allowThrowingAny: false,
          allowThrowingUnknown: false,
        },
      ],

      // What the rule does: Enforces the use of starred-block style (/* */) for multiline comments instead of consecutive line comments. This maintains consistent comment formatting.
      'multiline-comment-style': ['error', 'starred-block'],

      // What the rule does: Disallows 'var' usage, requiring 'let' or 'const' instead.
      'no-var': 'error',

      // What the rule does: Suggests using 'const' for variables that are never reassigned.
      'prefer-const': 'warn',

      // What the rule does: Requires JSDoc comments to include a description for all documented items. This ensures documentation is complete and useful.
      'jsdoc/require-description': 'error',
    },
  },
  {
    files: ['**/*.js'],
    languageOptions: {
      ecmaVersion: 2020,
      sourceType: 'module',
      globals: {
        ...globals.node,
        ...globals.browser,
      },
    },
  },
  {
    files: ['**/*.ts', '**/*.tsx'],
    languageOptions: {
      ecmaVersion: 2020,
      sourceType: 'module',
      globals: {
        ...globals.node,
        ...globals.jest,
      },
      parser: tsParser,
    },
  },
  {
    files: ['**/*.spec.ts', '**/*.test.ts', '**/*.test.tsx', '**/*.spec.tsx'],
    plugins: {
      jest: jestPlugin,
    },
    languageOptions: {
      ecmaVersion: 2020,
      sourceType: 'module',
      globals: {
        ...globals.node,
        ...globals.jest,
      },
      parser: tsParser,
    },
    rules: {
      // What the rule does: Prevents skipped tests (it.skip, describe.skip, test.skip, xit, xdescribe, xtest). This ensures all tests run and helps prevent accidentally committed skipped tests.
      'jest/no-disabled-tests': 'error',

      // Relaxed rules for test files
      '@typescript-eslint/explicit-function-return-type': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      'jsdoc/require-description': 'off',
    },
  },
  prettierConfig,
];
