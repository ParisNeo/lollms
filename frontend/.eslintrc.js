// .eslintrc.js
/** @type {import('eslint').Linter.Config} */
export default {
  root: true,
  env: {
    browser: true,
    es2021: true, // or a newer version like es2022
    node: true, // Still useful for recognizing Node.js globals if some scripts need them
  },
  extends: [
    'eslint:recommended',
    'plugin:vue/vue3-essential', // Or vue3-strongly-recommended / vue3-recommended
    // 'plugin:@typescript-eslint/recommended', // If using TypeScript
  ],
  parserOptions: {
    ecmaVersion: 'latest', // or 12, 13, etc.
    sourceType: 'module', // CRITICAL: Tell ESLint your .js files are ES Modules
  },
  plugins: [
    'vue',
    // '@typescript-eslint', // If using TypeScript
  ],
  rules: {
    // Your custom rules
  },
  // No 'overrides' needed for .cjs if you don't have any .cjs files
};  