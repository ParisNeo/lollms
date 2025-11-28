<script setup>
import { ref, computed } from 'vue';
import hljs from 'highlight.js';
import mermaid from 'mermaid';
import { useUiStore } from '../../../stores/ui';
import { usePyodideStore } from '../../../stores/pyodide';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useAuthStore } from '../../../stores/auth';
import IconLatex from '../../../assets/icons/IconLatex.vue';
import IconPhoto from '../../../assets/icons/IconPhoto.vue';
import IconSave from '../../../assets/icons/IconSave.vue'; 

const props = defineProps({
  language: {
    type: String,
    default: 'plaintext',
  },
  code: {
    type: String,
    required: true,
  },
  messageId: {
    type: String,
    default: null,
  },
});

const uiStore = useUiStore();
const pyodideStore = usePyodideStore();
const discussionsStore = useDiscussionsStore();
const authStore = useAuthStore();

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

const isCompiling = ref(false);
const compilationResult = ref(null);

const canvasId = `code-canvas-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
const canvasSelector = `#${canvasId}`;

const highlightedCode = computed(() => {
  const lang = props.language || 'plaintext';
  if (lang.toLowerCase() === 'note') {
      return props.code; 
  }
  if (hljs.getLanguage(lang)) {
    try {
      return hljs.highlight(props.code, { language: lang, ignoreIllegals: true }).value;
    } catch (e) { console.error(e); }
  }
  return hljs.highlightAuto(props.code).value;
});

const displayLanguage = computed(() => props.language || 'text');
const isPython = computed(() => props.language?.toLowerCase() === 'python');
const isLatex = computed(() => ['latex', 'tex'].includes(props.language?.toLowerCase()));
const isLatexBuilderEnabled = computed(() => authStore.latex_builder_enabled);
const isGenerativeImage = computed(() => props.language?.toLowerCase() === 'generate_image');
const isNote = computed(() => props.language?.toLowerCase() === 'note');
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

const compileButtonTitle = computed(() => {
    if (!isLatexBuilderEnabled.value) {
        return 'LaTeX builder is not enabled by the administrator.';
    }
    return 'Compile LaTeX';
});

const themeClass = computed(() => uiStore.currentTheme === 'dark' ? 'theme-dark' : 'theme-light');

function copyCode() {
  uiStore.copyToClipboard(props.code).then(() => {
      copyStatus.value = 'Copied!';
      setTimeout(() => { copyStatus.value = 'Copy'; }, 2000);
    });
}

function saveNote() {
    const rawCode = props.code.trim();
    const lines = rawCode.split('\n');
    let noteTitle = 'New AI Note';
    let noteContent = rawCode;
    
    // Find the first line starting with # to use as title
    const headerIndex = lines.findIndex(line => line.trim().startsWith('#'));
    
    if (headerIndex !== -1) {
        // Extract title from the header line, removing # chars
        noteTitle = lines[headerIndex].trim().replace(/^#+\s*/, '');
        
        // Remove the header line from the content to avoid duplication/clutter
        const contentLines = [...lines];
        contentLines.splice(headerIndex, 1);
        noteContent = contentLines.join('\n').trim();
    }

    uiStore.openModal('noteEditor', { 
        title: noteTitle,
        content: noteContent
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

async function compileLatex() {
    if (isCompiling.value) return;
    isCompiling.value = true;
    compilationResult.value = { logs: 'Compiling LaTeX document...' };
    try {
        const result = await discussionsStore.compileLatexCode({ code: props.code });
        compilationResult.value = result;
        if (result.pdf_b64) {
            const pdfWindow = window.open("");
            if(pdfWindow) {
                pdfWindow.document.write(`<title>PDF Preview</title><iframe width='100%' height='100%' src='data:application/pdf;base64,${result.pdf_b64}'></iframe>`);
                pdfWindow.document.close();
            } else {
                uiStore.addNotification('Could not open a new tab. Please allow pop-ups for this site.', 'warning');
            }
        }
    } catch (error) {
        compilationResult.value = { error: error.message || 'An unknown error occurred.', logs: error.logs || '' };
    } finally {
        isCompiling.value = false;
    }
}

async function generateImage() {
    if (isExecuting.value) return;
    const discussionId = discussionsStore.currentDiscussionId;
    if (!discussionId) return;

    isExecuting.value = true;
    isError.value = false;
    executionOutput.value = `Requesting image generation...`;
    
    try {
        await discussionsStore.generateImageFromDataZone(discussionId, props.code, props.messageId);
        executionOutput.value = 'Image generation task started successfully. Check the task manager for progress.';
    } catch (e) {
        isError.value = true;
        executionOutput.value = 'Failed to start image generation task.';
        console.error("Image generation task start failed:", e);
    } finally {
        isExecuting.value = false;
    }
}

async function executeCode() {
    if (!canExecute.value || isExecuting.value) return;
    isExecuting.value = true;
    isError.value = false;
    executionOutput.value = `Processing ${props.language} code...`;
    executionImage.value = null;
    createdFiles.value = [];
    compilationResult.value = null;
    
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
            const htmlContent = `
                <div style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; padding: 1rem;">
                    ${props.code}
                </div>
            `;
            uiStore.openModal('interactiveOutput', { htmlContent, title: 'SVG Preview', contentType: 'svg' });
            executionOutput.value = 'SVG rendered in a modal window.';
        } else if (lang === 'mermaid') {
            try {
                await mermaid.parse(props.code);
                uiStore.openModal('interactiveOutput', {
                    title: 'Interactive Mermaid Diagram',
                    contentType: 'mermaid',
                    interactive: true,
                    sourceCode: props.code
                });
                executionOutput.value = 'Interactive Mermaid diagram opened.';
            } catch (parseError) {
                try {
                    mermaid.initialize({ startOnLoad: false, theme: uiStore.currentTheme, securityLevel: 'loose' });
                    const { svg } = await mermaid.render(`mermaid-graph-${canvasId}`, props.code);
                    const background = uiStore.currentTheme === 'dark' ? '#1f2937' : '#f9fafb';
                    const htmlContent = `<body style="margin:0; display:flex; justify-content:center; align-items:center; height:100vh; background-color: ${background}; padding: 1rem;"><div style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;">${svg}</div></body>`;
                    uiStore.openModal('interactiveOutput', { htmlContent, title: 'Mermaid Diagram (Static)', contentType: 'mermaid', sourceCode: props.code });
                    executionOutput.value = 'Mermaid diagram rendered successfully as a static image due to parsing issues for interactive mode.';
                } catch (renderError) {
                    isError.value = true;
                    executionOutput.value = `Mermaid render error: ${renderError.message}`;
                }
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

function sendErrorToAI() {
    const prompt = `The code in your previous response failed to execute. Please fix it.
Error message:
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

function sendLatexErrorToAI() {
    const prompt = `The following LaTeX code failed to compile. Please analyze the error logs and provide a corrected version of the code.

Original Code:
\`\`\`latex
${props.code}
\`\`\`

Compilation Logs:
\`\`\`
${compilationResult.value.logs || compilationResult.value.error}
\`\`\`

Correct the LaTeX code block below:
`;
    discussionsStore.sendMessage({
        prompt: prompt,
        image_server_paths: [],
        localImageUrls: [],
    });
    compilationResult.value = null;
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
    <button @click="isCollapsed = !isCollapsed" class="code-block-header" :title="isCollapsed ? 'Expand' : 'Collapse'">
      <div class="flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 transition-transform flex-shrink-0" :class="{'rotate-90': !isCollapsed}" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4-4a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg>
        <span class="code-language">{{ displayLanguage }}</span>
      </div>
      <div v-if="!isInstallUiVisible" class="flex flex-row gap-2" @click.stop>
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
          <button v-if="isGenerativeImage" @click="generateImage" class="code-action-btn" :disabled="isExecuting" title="Generate Image">
              <IconPhoto class="h-4 w-4" />
              <span>{{ isExecuting ? 'Generating...' : 'Generate' }}</span>
          </button>
          <!-- NOTE BUTTON -->
          <button v-if="isNote" @click="saveNote" class="code-action-btn" title="Save as Note">
              <IconSave class="h-4 w-4" />
              <span>Save Note</span>
          </button>
          <button v-if="canExecute" @click="executeCode" class="code-action-btn" :disabled="isExecuting" title="Execute code">
              <svg v-if="!isExecuting" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd" /></svg>
              <svg v-else class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
              <span>{{ executeButtonText }}</span>
          </button>
          <button v-if="isLatex" @click="compileLatex" class="code-action-btn" :disabled="isCompiling || !isLatexBuilderEnabled" :title="compileButtonTitle">
                <IconLatex class="w-4 h-4" />
                <span>{{ isCompiling ? 'Compiling...' : 'Compile' }}</span>
          </button>
          <button @click="copyCode" class="code-action-btn" title="Copy code">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
              <span>{{ copyStatus }}</span>
          </button>
      </div>
       <div v-else class="flex flex-row gap-2 items-center w-full" @click.stop>
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
    </button>
    
    <div v-if="uploadedFiles.length > 0 && !isCollapsed" class="uploaded-files-list">
        <div v-for="(file, index) in uploadedFiles" :key="index" class="uploaded-file-item">
            <span class="file-name" :title="file.name">{{ file.name }}</span>
            <button @click="removeFile(index)" class="remove-file-btn" title="Remove file">×</button>
        </div>
    </div>

    <pre v-if="!isCollapsed" class="code-block-scrollable"><code class="hljs" v-html="highlightedCode"></code></pre>

    <div v-if="!isCollapsed && (executionOutput || executionImage || createdFiles.length > 0 || compilationResult)" class="code-execution-output" :class="{'is-error': isError || compilationResult?.error}">
        <div v-if="executionOutput" class="output-section">
            <div class="output-header">Execution Output</div>
            <pre>{{ executionOutput }}</pre>
        </div>
        <div v-if="compilationResult" class="output-section">
            <div class="output-header">Compilation Result</div>
            <div v-if="compilationResult.error" class="text-red-500 font-semibold">{{ compilationResult.error }}</div>
            <pre v-if="compilationResult.logs" class="text-xs max-h-40 overflow-y-auto">{{ compilationResult.logs }}</pre>
            <div v-if="compilationResult.pdf_b64 && !compilationResult.error" class="text-green-600 dark:text-green-400 font-semibold mt-2">PDF generated successfully and opened in a new tab.</div>
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
        <div v-if="isError" class="mt-4 pt-3 border-t border-red-500/30">
            <button @click="sendErrorToAI" class="btn btn-danger-outline btn-sm">
                 <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>
                Send Error to AI for Correction
            </button>
        </div>
         <div v-if="compilationResult && compilationResult.error" class="mt-4 pt-3 border-t border-red-500/30">
            <button @click="sendLatexErrorToAI" class="btn btn-danger-outline btn-sm">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>
                Send Error to AI for Correction
            </button>
        </div>
    </div>
  </div>
</template>

<style scoped>
.code-block-container { overflow: hidden; font-family: 'Fira Code', 'Courier New', monospace; border-radius: 8px; }
.code-block-header { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; font-size: 0.8rem; width: 100%; cursor: pointer; }
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
