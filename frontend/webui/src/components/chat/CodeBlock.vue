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
const isError = ref(false);
const isExecuting = ref(false);

const highlightedCode = computed(() => {
  const lang = props.language || 'plaintext';
  if (hljs.getLanguage(lang)) {
    try {
      return hljs.highlight(props.code, { language: lang, ignoreIllegals: true }).value;
    } catch (e) {
      console.error(e);
    }
  }
  return hljs.highlightAuto(props.code).value;
});

const displayLanguage = computed(() => props.language || 'text');
const canExecute = computed(() => ['python', 'javascript'].includes(props.language?.toLowerCase()));

function copyCode() {
  navigator.clipboard.writeText(props.code)
    .then(() => {
      copyStatus.value = 'Copied!';
      setTimeout(() => { copyStatus.value = 'Copy'; }, 2000);
    })
    .catch(err => {
      uiStore.addNotification('Failed to copy code.', 'error');
      console.error('Failed to copy code: ', err);
    });
}

async function executeCode() {
    if (!canExecute.value || isExecuting.value) return;

    isExecuting.value = true;
    isError.value = false;
    executionOutput.value = `Executing ${props.language} code...`;
    
    try {
        if (props.language.toLowerCase() === 'python') {
            if (!pyodideStore.isReady) {
                await pyodideStore.initialize();
                if (!pyodideStore.isReady) {
                    throw new Error("Python runtime could not be initialized.");
                }
            }
            const result = await pyodideStore.runCode(props.code);
            executionOutput.value = result.output || result.error || 'Execution finished with no output.';
            isError.value = !!result.error;

        } else if (props.language.toLowerCase() === 'javascript') {
            let capturedOutput = '';
            const originalLog = console.log;
            console.log = (...args) => {
                capturedOutput += args.map(String).join(' ') + '\n';
            };
            
            try {
                const result = new Function(props.code)();
                if (result !== undefined && result !== null) {
                    capturedOutput += String(result);
                }
                executionOutput.value = capturedOutput.trim() || 'Execution finished with no output.';
            } catch (e) {
                isError.value = true;
                executionOutput.value = e.toString();
            } finally {
                console.log = originalLog; // Restore original console.log
            }
        }
    } catch (e) {
        isError.value = true;
        executionOutput.value = e.toString();
    } finally {
        isExecuting.value = false;
    }
}
</script>

<template>
  <div class="code-block-container not-prose my-4">
    <!-- Header -->
    <div class="code-block-header">
      <span class="code-language">{{ displayLanguage }}</span>
    </div>
    <!-- Code Wrapper for floating buttons -->
    <div class="code-block-wrapper">
        <pre class="code-block"><code class="hljs" v-html="highlightedCode"></code></pre>
        
        <div class="code-action-buttons">
            <button v-if="canExecute" @click="executeCode" class="code-action-btn" :disabled="isExecuting" title="Execute code">
                <svg v-if="!isExecuting" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd" /></svg>
                <svg v-else class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                <span>{{ isExecuting ? 'Running...' : 'Run' }}</span>
            </button>
            <button @click="copyCode" class="code-action-btn" title="Copy code">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                <span>{{ copyStatus }}</span>
            </button>
        </div>
    </div>
    <!-- Execution Output -->
    <div v-if="executionOutput" class="code-execution-output" :class="{'is-error': isError}">
        {{ executionOutput }}
    </div>
  </div>
</template>