<script setup>
import { ref, computed } from 'vue';
import hljs from 'highlight.js';
import mermaid from 'mermaid';
import { useUiStore } from '../../stores/ui';
import { usePyodideStore } from '../../stores/pyodide';
import { useDiscussionsStore } from '../../stores/discussions'; // NEW: Import discussions store

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
const discussionsStore = useDiscussionsStore(); // NEW: Initialize discussions store

const copyStatus = ref('Copy');
const executionOutput = ref('');
const executionImage = ref(null); 
const isError = ref(false);
const isExecuting = ref(false);
const createdFiles = ref([]);
const isCollapsed = ref(false);

const isInstallUiVisible = ref(false);
const packagesToInstall = ref('');
const isInstalling = ref(false);

const fileInput = ref(null);
const uploadedFiles = ref([]);

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
const isPython = computed(() => props.language?.toLowerCase() === 'python');
const canExecute = computed(() => ['python', 'javascript', 'html', 'svg', 'mermaid'].includes(props.language?.toLowerCase()));

const executeButtonText = computed(() => {
    if (isExecuting.value) {
        const lang = props.language.toLowerCase();
        if (lang === 'mermaid') return 'Rendering...';
        if (lang === 'svg' || lang === 'html') return 'Showing...';
        return 'Running...';
    }
    if (['svg', 'mermaid', 'html'].includes(props.language?.toLowerCase())) return 'Show';
    return 'Run';
});

const themeClass = computed(() => uiStore.currentTheme === 'dark' ? 'theme-dark' : 'theme-light');

function copyCode() {
  uiStore.copyToClipboard(props.code).then(() => {
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
        case 'svg': return 'image/svg+xml';
        default: return 'text/plain';
    }
}

function getDownloadExtension(language) {
    const lang = language.toLowerCase();
    if (lang === 'python') return 'py';
    if (lang === 'javascript') return 'js';
    if (lang === 'svg') return 'svg';
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

function showInstallUi() {
    isInstallUiVisible.value = true;
    packagesToInstall.value = '';
}

function hideInstallUi() {
    isInstallUiVisible.value = false;
}

async function handleInstall() {
    if (!packagesToInstall.value.trim() || isInstalling.value) return;
    isInstalling.value = true;
    const packages = packagesToInstall.value.trim().split(/\s+/).filter(p => p);
    await pyodideStore.installPackages(packages);
    isInstalling.value = false;
    isInstallUiVisible.value = false;
}

function triggerFileUpload() {
    fileInput.value?.click();
}

function handleFileSelection(event) {
    const files = Array.from(event.target.files);
    uploadedFiles.value.push(...files);
    event.target.value = '';
}

function removeFile(index) {
    uploadedFiles.value.splice(index, 1);
}

async function executeCode() {
    if (!canExecute.value || isExecuting.value) return;
    isExecuting.value = true;
    isError.value = false;
    executionOutput.value = `Processing ${props.language} code...`;
    executionImage.value = null;
    createdFiles.value = [];
    
    try {
        const lang = props.language.toLowerCase();
        if (lang === 'python') {
            if (!pyodideStore.isReady) {
                await pyodideStore.initialize();
                if (!pyodideStore.isReady) throw new Error("Python runtime could not be initialized.");
            }
            const result = await pyodideStore.runCode(props.code, {
                canvasSelector: canvasSelector,
                files: uploadedFiles.value,
            });
            
            isError.value = !!result.error;
            const outputText = result.error || result.output || (result.image || result.usesCanvas ? '' : 'Execution finished with no output.');
            executionOutput.value = outputText.trim();

            if (result.usesCanvas) {
                uiStore.openModal('interactiveOutput', { canvasId: canvasId, title: 'Python Canvas Output' });
                if (!executionOutput.value) {
                    executionOutput.value = 'Interactive canvas opened in a modal window.';
                }
            } else {
                executionImage.value = result.image ? `data:image/png;base64,${result.image}` : null;
            }
            createdFiles.value = result.newFiles || [];

        } else if (lang === 'html') {
            uiStore.openModal('interactiveOutput', { htmlContent: props.code, title: 'HTML Output' });
            executionOutput.value = 'HTML content rendered in a modal canvas.';
        } else if (lang === 'svg') {
            const background = uiStore.currentTheme === 'dark' ? '#1f2937' : '#f9fafb';
            const htmlContent = `
                <body style="margin:0; display:flex; justify-content:center; align-items:center; height:100vh; background-color: ${background}; padding: 1rem;">
                    <div style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;">
                        ${props.code}
                    </div>
                </body>
            `;
            uiStore.openModal('interactiveOutput', { htmlContent, title: 'SVG Preview', contentType: 'svg' });
            executionOutput.value = 'SVG rendered in a modal window.';
        } else if (lang === 'mermaid') {
            try {
                mermaid.initialize({ 
                    startOnLoad: false, 
                    theme: uiStore.currentTheme,
                    securityLevel: 'loose', 
                });
                const { svg } = await mermaid.render(`mermaid-graph-${canvasId}`, props.code);
                
                const background = uiStore.currentTheme === 'dark' ? '#1f2937' : '#f9fafb';

                const htmlContent = `
                    <div style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; padding: 1rem; overflow: auto;">
                        ${svg}
                    </div>
                `;
                uiStore.openModal('interactiveOutput', {
                    htmlContent,
                    title: 'Mermaid Diagram',
                    contentType: 'mermaid',
                    sourceCode: props.code
                });
                executionOutput.value = 'Mermaid diagram rendered successfully.';
            } catch (e) {
                isError.value = true;
                executionOutput.value = `Mermaid render error: ${e.message}`;
            }
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
        uploadedFiles.value = [];
    }
}

// NEW: Function to send the error back to the AI
function sendErrorToAI() {
    const prompt = `The following \`${props.language}\` code block failed to execute. Please analyze the error and provide a corrected version of the code.

**Original Code:**
\`\`\`${props.language}
${props.code}
\`\`\`

**Error Message:**
\`\`\`
${executionOutput.value}
\`\`\`
`;
    discussionsStore.sendMessage({
        prompt: prompt,
        image_server_paths: [],
        localImageUrls: [],
    });
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
      <div class="flex items-center gap-2">
        <button @click="isCollapsed = !isCollapsed" class="p-1 rounded-full hover:bg-white/10" :title="isCollapsed ? 'Expand' : 'Collapse'">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 transition-transform" :class="{'rotate-90': !isCollapsed}" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4-4a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg>
        </button>
        <span class="code-language">{{ displayLanguage }}</span>
      </div>
      <div v-if="!isInstallUiVisible" class="flex flex-row gap-2">
          <button @click="downloadCode" class="code-action-btn" title="Download file">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
              <span>Download</span>
          </button>
           <button v-if="isPython" @click="showInstallUi" class="code-action-btn" title="Install packages">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M5.5 16a3.5 3.5 0 01-.369-6.98 4 4 0 117.753-1.977A4.5 4.5 0 1113.5 16h-8z" /></svg>
                <span>Install</span>
            </button>
            <input type="file" ref="fileInput" @change="handleFileSelection" multiple class="hidden" />
            <button v-if="isPython" @click="triggerFileUpload" class="code-action-btn" title="Upload files">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM6.293 6.707a1 1 0 010-1.414l3-3a1 1 0 011.414 0l3 3a1 1 0 01-1.414 1.414L11 5.414V13a1 1 0 11-2 0V5.414L7.707 6.707a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg>
                <span>Upload</span>
            </button>
          <button v-if="canExecute" @click="executeCode" class="code-action-btn" :disabled="isExecuting" title="Execute code">
              <svg v-if="!isExecuting" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd" /></svg>
              <svg v-else class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
              <span>{{ executeButtonText }}</span>
          </button>
          <button @click="copyCode" class="code-action-btn" title="Copy code">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
              <span>{{ copyStatus }}</span>
          </button>
      </div>
       <div v-else class="flex flex-row gap-2 items-center w-full">
            <input 
                v-model="packagesToInstall"
                @keyup.enter="handleInstall"
                @keyup.esc="hideInstallUi"
                type="text" 
                placeholder="e.g. pandas numpy" 
                class="install-input flex-grow"
                autofocus
            />
            <button @click="handleInstall" class="code-action-btn install-confirm-btn" :disabled="isInstalling">
                {{ isInstalling ? 'Installing...' : 'Install' }}
            </button>
            <button @click="hideInstallUi" class="code-action-btn install-cancel-btn" title="Cancel">×</button>
        </div>
    </div>
    
    <div v-if="uploadedFiles.length > 0 && !isCollapsed" class="uploaded-files-list">
        <div v-for="(file, index) in uploadedFiles" :key="index" class="uploaded-file-item">
            <span class="file-name" :title="file.name">{{ file.name }}</span>
            <button @click="removeFile(index)" class="remove-file-btn" title="Remove file">×</button>
        </div>
    </div>

    <pre v-if="!isCollapsed" class="code-block-scrollable"><code class="hljs" v-html="highlightedCode"></code></pre>

    <div v-if="!isCollapsed && (executionOutput || executionImage || createdFiles.length > 0)" class="code-execution-output" :class="{'is-error': isError}">
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
        <!-- NEW: Send error to AI button -->
        <div v-if="isError" class="mt-4 pt-3 border-t border-red-500/30">
            <button @click="sendErrorToAI" class="btn btn-danger-outline btn-sm">
                 <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>
                Send Error to AI for Correction
            </button>
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
.install-input { background-color: transparent; border: none; outline: none; font-size: 0.8rem; padding: 2px 4px; border-bottom: 1px solid; }
.install-cancel-btn { padding: 0 8px; font-size: 1.2rem; line-height: 1; }
.uploaded-files-list { padding: 8px 12px; border-top: 1px solid; display: flex; flex-wrap: wrap; gap: 8px; font-size: 0.75rem; }
.uploaded-file-item { display: flex; align-items: center; padding: 2px 6px; border-radius: 4px; gap: 6px; }
.file-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; }
.remove-file-btn { font-size: 1rem; line-height: 1; border-radius: 50%; width: 16px; height: 16px; display: flex; align-items: center; justify-content: center; }
.remove-file-btn:hover { background-color: rgba(0,0,0,0.1); }
.code-block-scrollable { margin: 0; padding: 16px; max-height: 400px; overflow-y: auto; overflow-x: auto; }
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
.theme-dark .install-input { color: #d4d4d4; border-bottom-color: #606060; }
.theme-dark .install-input:focus { border-bottom-color: #a2c1ff; }
.theme-dark .install-confirm-btn { background-color: #2c622f; border-color: #4CAF50; }
.theme-dark .uploaded-files-list { border-top-color: #333; }
.theme-dark .uploaded-file-item { background-color: #3e3e42; }
.theme-dark .remove-file-btn { color: #f0f0f0; }
.theme-dark .remove-file-btn:hover { background-color: #5a5a5e; }
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
.theme-light .install-input { color: #212121; border-bottom-color: #bdbdbd; }
.theme-light .install-input:focus { border-bottom-color: #0059b3; }
.theme-light .install-confirm-btn { background-color: #e8f5e9; border-color: #a5d6a7; }
.theme-light .uploaded-files-list { border-top-color: #e0e0e0; }
.theme-light .uploaded-file-item { background-color: #e0e0e0; }
.theme-light .remove-file-btn { color: #212121; }
.theme-light .remove-file-btn:hover { background-color: #bdbdbd; }
.theme-light .code-block-scrollable { scrollbar-color: #bdbdbd #f5f5f5; }
.theme-light .code-execution-output { background-color: #f5f5f5; border-top: 1px solid #e0e0e0; }
.theme-light .code-execution-output.is-error { background-color: #fff1f0; border-top-color: #ffccc7; color: #a8071a; }
.theme-light .code-execution-output.is-error pre { color: #a8071a; }
.theme-light .code-execution-output pre { color: #212121; }
.theme-light .output-header { color: #757575; }
.theme-light .file-link { color: #0059b3; }
.theme-light .file-link:hover { background-color: #e0e0e0; }
</style>