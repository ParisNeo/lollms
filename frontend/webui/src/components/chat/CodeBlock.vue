<script setup>
import { ref, computed } from 'vue';
import hljs from 'highlight.js';
import { useUiStore } from '../../stores/ui';
import { usePyodideStore } from '../../stores/pyodide';

const props = defineProps({
  language: {
    type: String,
    default: 'plaintext',
  },
  code: {
    type: String,
    required: true,
  },
});

const uiStore = useUiStore();
const pyodideStore = usePyodideStore();

const copyStatus = ref('Copy');
const executionOutput = ref('');
const executionImage = ref(null); 
const isError = ref(false);
const isExecuting = ref(false);
const createdFiles = ref([]);

const canvasId = `code-canvas-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
const canvasSelector = `#${canvasId}`;

const highlightedCode = computed(() => {
  const lang = props.language || 'plaintext';
  if (hljs.getLanguage(lang)) {
    try {
      return hljs.highlight(props.code, { language: lang, ignoreIllegals: true }).value;
    } catch (e) { console.error(e); }
  }
  return hljs.highlightAuto(props.code).value;
});

const displayLanguage = computed(() => props.language || 'text');
const canExecute = computed(() => ['python', 'javascript', 'html'].includes(props.language?.toLowerCase()));
const themeClass = computed(() => uiStore.currentTheme === 'dark' ? 'theme-dark' : 'theme-light');

function copyCode() {
  navigator.clipboard.writeText(props.code)
    .then(() => {
      copyStatus.value = 'Copied!';
      setTimeout(() => { copyStatus.value = 'Copy'; }, 2000);
    });
}

function getMimeType(language) {
    switch (language.toLowerCase()) {
        case 'python': return 'text/x-python';
        case 'javascript': return 'application/javascript';
        case 'html': return 'text/html';
        case 'css': return 'text/css';
        case 'json': return 'application/json';
        default: return 'text/plain';
    }
}

function getDownloadExtension(language) {
    const lang = language.toLowerCase();
    if (lang === 'python') return 'py';
    if (lang === 'javascript') return 'js';
    return lang || 'txt';
}

function downloadCode() {
    const blob = new Blob([props.code], { type: getMimeType(props.language) });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `code.${getDownloadExtension(props.language)}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

async function executeCode() {
    if (!canExecute.value || isExecuting.value) return;
    isExecuting.value = true;
    isError.value = false;
    executionOutput.value = `Executing ${props.language} code...`;
    executionImage.value = null;
    createdFiles.value = [];
    
    try {
        const lang = props.language.toLowerCase();
        if (lang === 'python') {
            if (!pyodideStore.isReady) {
                await pyodideStore.initialize();
                if (!pyodideStore.isReady) throw new Error("Python runtime could not be initialized.");
            }
            const result = await pyodideStore.runCode(props.code, canvasSelector);
            
            isError.value = !!result.error;
            const outputText = result.error || result.output || (result.image || result.usesCanvas ? '' : 'Execution finished with no output.');
            executionOutput.value = outputText.trim();

            if (result.usesCanvas) {
                uiStore.openModal('interactiveOutput', { canvasId: canvasId });
                if (!executionOutput.value) {
                    executionOutput.value = 'Interactive canvas opened in a modal window.';
                }
            } else {
                executionImage.value = result.image ? `data:image/png;base64,${result.image}` : null;
            }
            createdFiles.value = result.newFiles || [];

        } else if (lang === 'html') {
            const blob = new Blob([props.code], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            window.open(url, '_blank');
            executionOutput.value = 'HTML content opened in a new tab.';
        } else if (lang === 'javascript') {
            let capturedOutput = '';
            const originalLog = console.log;
            console.log = (...args) => { capturedOutput += args.map(String).join(' ') + '\n'; };
            try {
                const result = new Function(props.code)();
                if (result !== undefined && result !== null) capturedOutput += String(result);
                executionOutput.value = capturedOutput.trim() || 'Execution finished with no output.';
            } catch (e) {
                isError.value = true;
                executionOutput.value = e.toString();
            } finally {
                console.log = originalLog;
            }
        }
    } catch (e) {
        isError.value = true;
        executionOutput.value = e.toString();
    } finally {
        isExecuting.value = false;
    }
}

async function downloadCreatedFile(filename) {
    const fileData = await pyodideStore.readFile(filename);
    if (fileData) {
        const blob = new Blob([fileData]);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } else {
        uiStore.addNotification(`Could not read file: ${filename}`, 'error');
    }
}
</script>

<template>
  <div class="code-block-container not-prose my-4" :class="themeClass">
    <div class="code-block-header">
      <span class="code-language">{{ displayLanguage }}</span>
      <div class="flex flex-row gap-2">
          <button @click="downloadCode" class="code-action-btn" title="Download file">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
              <span>Download</span>
          </button>
          <button v-if="canExecute" @click="executeCode" class="code-action-btn" :disabled="isExecuting" title="Execute code">
              <svg v-if="!isExecuting" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd" /></svg>
              <svg v-else class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
              <span>{{ isExecuting ? 'Running...' : 'Run' }}</span>
          </button>
          <button @click="copyCode" class="code-action-btn" title="Copy code">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
              <span>{{ copyStatus }}</span>
          </button>
      </div>
    </div>
    
    <pre class="code-block-scrollable"><code class="hljs" v-html="highlightedCode"></code></pre>

    <div v-if="executionOutput || executionImage || createdFiles.length > 0" class="code-execution-output" :class="{'is-error': isError}">
        <div v-if="executionOutput" class="output-section">
            <div class="output-header">Execution Output</div>
            <pre>{{ executionOutput }}</pre>
        </div>
        <img v-if="executionImage" :src="executionImage" alt="Matplotlib plot" class="mt-2 max-w-full h-auto rounded-md bg-white">
        <div v-if="createdFiles.length > 0" class="output-section">
            <div class="output-header">Created Files</div>
            <ul class="file-list">
                <li v-for="file in createdFiles" :key="file">
                    <a href="#" @click.prevent="downloadCreatedFile(file)" class="file-link">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M6 2a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V7.414A2 2 0 0015.414 6L12 2.586A2 2 0 0010.586 2H6zm5 6a1 1 0 10-2 0v3.586l-1.293-1.293a1 1 0 10-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 00-1.414-1.414L11 11.586V8z" clip-rule="evenodd" /></svg>
                        {{ file }}
                    </a>
                </li>
            </ul>
        </div>
    </div>
  </div>
</template>

<style scoped>
.code-block-container { overflow: hidden; font-family: 'Fira Code', 'Courier New', monospace; border-radius: 8px; }
.code-block-header { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; font-size: 0.8rem; }
.code-language { font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }
.code-action-btn { display: flex; align-items: center; gap: 6px; border-radius: 5px; padding: 4px 10px; font-size: 0.75rem; cursor: pointer; transition: background-color 0.2s, color 0.2s; }
.code-action-btn:disabled { cursor: not-allowed; opacity: 0.6; }

/* FIX: Added overflow-x: auto to handle long lines of code */
.code-block-scrollable { 
  margin: 0; 
  padding: 16px; 
  max-height: 400px; 
  overflow-y: auto; 
  overflow-x: auto;
}

.code-block-scrollable > .hljs { background-color: transparent !important; padding: 0 !important; }
.code-execution-output { padding: 12px; font-size: 0.8rem; }
.code-execution-output pre { margin: 0; white-space: pre-wrap; word-break: break-word; }
.output-header { font-weight: bold; font-size: 0.7rem; text-transform: uppercase; margin-bottom: 8px; }
.output-section:not(:first-child) { margin-top: 1rem; }
.file-list { list-style: none; padding: 0; margin: 0; }
.file-link { display: flex; align-items: center; text-decoration: none; padding: 4px 0; border-radius: 4px; }
.theme-dark { background-color: #1e1e1e; border: 1px solid #333; color: #d4d4d4; }
.theme-dark .code-block-header { background-color: #252526; border-bottom: 1px solid #333; }
.theme-dark .code-language { color: #cecece; }
.theme-dark .code-action-btn { background-color: #3e3e42; color: #f0f0f0; border: 1px solid #606060; }
.theme-dark .code-action-btn:hover:not(:disabled) { background-color: #5a5a5e; color: #ffffff; }
.theme-dark .code-block-scrollable { scrollbar-color: #555 #252526; }
.theme-dark .code-execution-output { background-color: #252526; border-top: 1px solid #333; }
.theme-dark .code-execution-output.is-error { background-color: #4a1d1d; border-top-color: #842e2e; color: #f8d7da; }
.theme-dark .code-execution-output.is-error pre { color: #f8d7da; }
.theme-dark .code-execution-output pre { color: #d4d4d4; }
.theme-dark .output-header { color: #888; }
.theme-dark .file-link { color: #a2c1ff; }
.theme-dark .file-link:hover { background-color: #3e3e42; }
.theme-light { background-color: #ffffff; border: 1px solid #e0e0e0; color: #212121; }
.theme-light .code-block-header { background-color: #f5f5f5; border-bottom: 1px solid #e0e0e0; }
.theme-light .code-language { color: #333; }
.theme-light .code-action-btn { background-color: #e0e0e0; color: #212121; border: 1px solid #bdbdbd; }
.theme-light .code-action-btn:hover:not(:disabled) { background-color: #d4d4d4; }
.theme-light .code-block-scrollable { scrollbar-color: #bdbdbd #f5f5f5; }
.theme-light .code-execution-output { background-color: #f5f5f5; border-top: 1px solid #e0e0e0; }
.theme-light .code-execution-output.is-error { background-color: #fff1f0; border-top-color: #ffccc7; color: #a8071a; }
.theme-light .code-execution-output.is-error pre { color: #a8071a; }
.theme-light .code-execution-output pre { color: #212121; }
.theme-light .output-header { color: #757575; }
.theme-light .file-link { color: #0059b3; }
.theme-light .file-link:hover { background-color: #e0e0e0; }
</style>