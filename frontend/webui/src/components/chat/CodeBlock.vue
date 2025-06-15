<script>
import hljs from 'highlight.js';

export default {
  name: 'CodeBlock',
  props: {
    language: {
      type: String,
      default: 'plaintext',
    },
    code: {
      type: String,
      required: true,
    },
  },
  computed: {
    highlightedCode() {
      const lang = this.language || 'plaintext';
      if (hljs.getLanguage(lang)) {
        try {
          return hljs.highlight(this.code, { language: lang, ignoreIllegals: true }).value;
        } catch (e) {
            console.error(e);
        }
      }
      return hljs.highlightAuto(this.code).value;
    },
    displayLanguage() {
        return this.language || 'text';
    }
  },
  methods: {
    copyCode() {
      navigator.clipboard.writeText(this.code)
        .then(() => {
          // You can emit an event or use a store to show a notification
          console.log('Code copied to clipboard!');
        })
        .catch(err => {
          console.error('Failed to copy code: ', err);
        });
    },
    runCode() {
        // Placeholder for Pyodide or other execution logic
        console.log("Running code:", this.code)
    }
  },
};
</script>

<template>
  <div class="code-block-container my-4">
    <!-- Header -->
    <div class="code-block-header">
      <span class="code-language">{{ displayLanguage }}</span>
      <div class="flex items-center space-x-2">
        <button v-if="language === 'python'" @click="runCode" class="code-copy-btn" title="Run Python code (requires Pyodide)">
            <!-- Run Icon -->
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
        </button>
        <button @click="copyCode" class="code-copy-btn" title="Copy code">
          <!-- Copy Icon -->
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
        </button>
      </div>
    </div>
    <!-- Code -->
    <pre class="code-block"><code class="hljs" v-html="highlightedCode"></code></pre>
  </div>
</template>

<style scoped>
/* Specific styles for the code block component can go here if needed */
/* Most styles are handled globally in main.css via CSS variables for theming */
</style>