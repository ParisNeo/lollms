<script setup>
import { computed, ref, watch, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import { useNotesStore } from '../../stores/notes';
import { useSkillsStore } from '../../stores/skills';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue';
import IconClock from '../../assets/icons/IconClock.vue';
import IconGitBranch from '../../assets/icons/ui/IconGitBranch.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconMinimize from '../../assets/icons/IconMinimize.vue';
import IconError from '../../assets/icons/IconError.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconSpeakerWave from '../../assets/icons/IconSpeakerWave.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import { usePyodideStore } from '../../stores/pyodide';

const uiStore = useUiStore();
const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const notesStore = useNotesStore();
const skillsStore = useSkillsStore();
const dataStore = useDataStore(); // ADDED: Required for isTtsActive check

const title = computed(() => uiStore.activeSplitArtefactTitle);
const isFullscreen = ref(false);

const isTtsActive = computed(() => {
    return !!authStore.user?.tts_binding_model_name && 
           authStore.user.tts_binding_model_name.includes('/') && 
           dataStore.availableTtsModels.length > 0;
});

const exportFormats = computed(() => {
    const formats = [];
    if (authStore.export_to_txt_enabled) formats.push({ label: 'Text (.txt)', value: 'txt' });
    if (authStore.export_to_markdown_enabled) formats.push({ label: 'Markdown (.md)', value: 'md' });
    if (authStore.export_to_html_enabled) formats.push({ label: 'HTML (.html)', value: 'html' });
    if (authStore.export_to_pdf_enabled) formats.push({ label: 'PDF (.pdf)', value: 'pdf' });
    if (authStore.export_to_docx_enabled) formats.push({ label: 'Word (.docx)', value: 'docx' });
    return formats;
});

async function handleExport(format) {
    if (!dbContent.value) {
        uiStore.addNotification("Nothing to export.", "warning");
        return;
    }

    if (format === 'wav') {
        try {
            const response = await apiClient.post(`/api/discussions/${discussionsStore.currentDiscussionId}/artefacts/export_audio`, {
                title: title.value,
                content: dbContent.value
            });
            uiStore.addNotification("Audio generation started in background.", "info");
            // Open task manager so user can see progress
            uiStore.openModal('tasksManager', { initialTaskId: response.data.id });
        } catch (e) {
            uiStore.addNotification("Failed to start background task.", "error");
        }
        return;
    }

    discussionsStore.exportRawContent({ 
        content: dbContent.value, 
        format: format,
        filename: title.value || 'workspace_export'
    });
}

// Track if this file is currently being modified by AI - Added defensive checks
const isLiveUpdating = computed(() => {
    if (!title.value || !discussionsStore.activeUpdatingArtefacts) return false;
    // Defensive check to ensure it's a valid Set before calling .has()
    if (typeof discussionsStore.activeUpdatingArtefacts.has !== 'function') return false;
    return discussionsStore.activeUpdatingArtefacts.has(title.value);
});

const artefactGroup = computed(() => {
    if (!title.value) return null;
    const isSaved = discussionsStore.currentDiscussionId === 'saved';
    const all = isSaved ? (discussionsStore.allUserArtefacts || []) : (discussionsStore.activeDiscussionArtefacts || []);
    console.log('[ArtefactSplitView] Checking artefacts for title:', title.value, 'isSaved:', isSaved, 'available:', all.map(a => `${a.title}(v${a.version})`));
    // Sort versions DESC (newest first)
    const versions = all.filter(a => a.title === title.value).sort((a,b) => b.version - a.version);
    console.log('[ArtefactSplitView] Found versions:', versions.length, versions.map(v => ({v: v.version, is_loaded: v.is_loaded, size: v.content_size})));
    return versions.length > 0 ? { title: title.value, versions } : null;
});

const dataZoneWidth = ref(600);
const isResizing = ref(false);

function startResize(event) {
    isResizing.value = true;
    const startX = event.clientX;
    const startWidth = dataZoneWidth.value;
    
    const onMouseMove = (e) => {
        if (!isResizing.value) return;
        const delta = startX - e.clientX;
        dataZoneWidth.value = Math.max(350, Math.min(window.innerWidth * 0.8, startWidth + delta));
    };
    
    const onMouseUp = () => {
        isResizing.value = false;
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        localStorage.setItem('lollms_artefactWidth', dataZoneWidth.value);
    };
    
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
}

onMounted(() => {
    const saved = localStorage.getItem('lollms_artefactWidth');
    if (saved) dataZoneWidth.value = parseInt(saved, 10);
    
    // Force reload on mount if we have a title but no content yet
    if (title.value && !dbContent.value && artefactGroup.value) {
        console.log('[ArtefactSplitView] Force loading on mount');
        const latestVersion = artefactGroup.value.versions[0]?.version;
        if (latestVersion) {
            loadVersion(latestVersion);
        }
    }
});

const selectedVersion = ref(null);
const dbContent = ref('');
const isSaving = ref(false);
const isFetching = ref(false);
const isGeneratingAudio = ref(false);
const loadError = ref(null);
const isExecuting = ref(false);
const pyodideStore = usePyodideStore();

const isExecutable = computed(() => {
    const type = detectedContentType.value;
    return ['html', 'mermaid', 'svg', 'python', 'javascript'].includes(type);
});

const executeTitle = computed(() => {
    const type = detectedContentType.value;
    if (['html', 'mermaid', 'svg'].includes(type)) return 'Show Render / Preview';
    return 'Execute Code';
});

async function executeArtefactContent(title, content, ext) {
    const cleanContent = content.trim();

    if (ext === 'html') {
        const blob = new Blob([cleanContent], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        window.open(url, '_blank');
        setTimeout(() => URL.revokeObjectURL(url), 60000);
        uiStore.addNotification("HTML opened in a new tab.", "success");
    } else if (ext === 'svg') {
        const htmlContent = `<div style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; padding: 1rem;">${cleanContent}</div>`;
        uiStore.openModal('interactiveOutput', { htmlContent, title: `SVG Preview: ${title}`, contentType: 'svg' });
    } else if (ext === 'mermaid') {
        uiStore.openModal('interactiveOutput', {
            title: `Mermaid Diagram: ${title}`,
            contentType: 'mermaid',
            sourceCode: cleanContent
        });
    } else if (ext === 'js' || ext === 'javascript') {
        const createDynamicFn = window.Function;
        try {
            let capturedOutput = '';
            const originalLog = console.log;
            console.log = (...args) => { capturedOutput += args.map(String).join(' ') + '\n'; };

            const result = (new createDynamicFn(cleanContent))();
            if (result !== undefined && result !== null) {
                capturedOutput += String(result);
            }
            console.log = originalLog;

            const outputText = capturedOutput.trim() || 'Execution finished with no output.';
            uiStore.openModal('interactiveOutput', { content: `### Execution Output\n\`\`\`\n${outputText}\n\`\`\``, title: `JS Output: ${title}` });
        } catch (e) {
            uiStore.openModal('interactiveOutput', { content: `### Execution Error\n\`\`\`\n${e.toString()}\n\`\`\``, title: `JS Error: ${title}` });
        }
    } else if (ext === 'py' || ext === 'python') {
        uiStore.addNotification("Loading Python environment...", "info");
        if (!pyodideStore.isReady) {
            await pyodideStore.initialize();
        }

        const canvasId = `code-canvas-${Date.now()}`;
        const result = await pyodideStore.runCode(cleanContent, {
            canvasSelector: `#${canvasId}`
        });

        const outputText = result.error || result.output || (result.image || result.usesCanvas ? '' : 'Execution finished with no output.');

        if (result.usesCanvas) {
            uiStore.openModal('interactiveOutput', { canvasId: canvasId, title: `Python Canvas: ${title}` });
        } else if (result.image) {
            const htmlContent = `<div style="text-align: center;"><img src="data:image/png;base64,${result.image}" class="max-w-full h-auto mx-auto" /></div>`;
            uiStore.openModal('interactiveOutput', { htmlContent, title: `Python Output: ${title}` });
        } else {
            uiStore.openModal('interactiveOutput', { content: `### Python Output\n\`\`\`\n${outputText}\n\`\`\``, title: `Python Output: ${title}` });
        }
    } else {
        uiStore.openModal('interactiveOutput', { content: cleanContent, title: `Viewer: ${title}` });
    }
}

async function handleExecute() {
    if (isExecuting.value) return;
    isExecuting.value = true;
    try {
        const type = detectedContentType.value;
        const ext = type === 'python' ? 'py' : (type === 'javascript' ? 'js' : type);
        await executeArtefactContent(title.value, dbContent.value, ext);
    } catch (e) {
        console.error("Execution failed:", e);
        uiStore.addNotification("Execution failed: " + e.message, "error");
    } finally {
        isExecuting.value = false;
    }
}


    // Detect content type for syntax highlighting based on artefact type and title
    const detectedContentType = computed(() => {
        const artType = artefactGroup.value?.versions[0]?.artefact_type;
        const title = artefactGroup.value?.title || '';
        
        // Try to detect from file extension first (regardless of artefact_type)
        const ext = title.split('.').pop()?.toLowerCase();
        const extMap = {
            // Web
            'html': 'html', 'htm': 'html', 'css': 'css', 'scss': 'scss', 'sass': 'sass',
            'less': 'less', 'vue': 'vue', 'jsx': 'jsx', 'tsx': 'tsx',
            // Programming
            'py': 'python', 'js': 'javascript', 'ts': 'typescript', 'java': 'java',
            'kt': 'kotlin', 'go': 'go', 'rs': 'rust', 'swift': 'swift',
            'cpp': 'cpp', 'c': 'c', 'h': 'c', 'hpp': 'cpp', 'cs': 'csharp',
            'php': 'php', 'rb': 'ruby', 'r': 'r', 'm': 'objective-c', 'mm': 'objective-cpp',
            'scala': 'scala', 'groovy': 'groovy', 'clj': 'clojure', 'ex': 'elixir',
            'elm': 'elm', 'erl': 'erlang', 'fs': 'fsharp', 'hs': 'haskell',
            'lua': 'lua', 'ml': 'ocaml', 'pas': 'pascal', 'pl': 'perl',
            'ps1': 'powershell', 'sh': 'bash', 'bash': 'bash', 'zsh': 'bash',
            'sql': 'sql', 'v': 'verilog', 'vhdl': 'vhdl', 'asm': 'asm',
            // Data/Markup
            'json': 'json', 'xml': 'xml', 'yaml': 'yaml', 'yml': 'yaml',
            'toml': 'toml', 'ini': 'ini', 'csv': 'csv', 'tsv': 'tsv',
            'md': 'markdown', 'mdx': 'markdown', 'rst': 'restructuredtext',
            'tex': 'latex', 'latex': 'latex', 'txt': 'plaintext',
            // Config
            'dockerfile': 'dockerfile', 'makefile': 'makefile', 'cmake': 'cmake',
            'gradle': 'gradle', 'maven': 'xml', 'pom': 'xml',
            // Other
            'svg': 'svg', 'mermaid': 'mermaid', 'mmd': 'mermaid', 'graphql': 'graphql', 'proto': 'protobuf',
            };

            // Return detected type from extension if found
        if (extMap[ext]) {
            return extMap[ext];
        }
        
        // Fallback to artefact_type based detection
        // For skills and notes, content is typically markdown
        if (artType === 'skill' || artType === 'note') {
            return 'markdown';
        }
        
        return 'plaintext';
    });

    // Language for CodeMirror editor (for edit mode)
    const detectedLanguage = computed(() => {
        const type = detectedContentType.value;
        // Map content types to CodeMirror language modes
        const cmLangMap = {
            'python': 'python',
            'javascript': 'javascript',
            'typescript': 'javascript',
            'html': 'html',
            'css': 'html',
            'json': 'javascript',
            'mermaid': 'mermaid',
            'markdown': 'markdown',
        };
        return cmLangMap[type] || 'markdown';
    });

    async function loadVersion(v) {
        if (!title.value || v === null) return;
        isFetching.value = true;
        try {
            const data = await discussionsStore.fetchArtefactContent({
                discussionId: discussionsStore.currentDiscussionId,
                artefactTitle: title.value,
                version: v,
                strategy: 'raw'
            });
            
            console.log('[ArtefactSplitView] fetchArtefactContent response:', data);
            
            // Handle different response formats
            let rawContent = '';
            
            if (typeof data === 'string') {
                // Direct string response
                rawContent = data;
            } else if (data && typeof data === 'object') {
                // Object response with content field
                rawContent = data.content ?? '';
            }
            
            // Detect if we got the Vue app's HTML (error) vs actual artefact HTML content
            const isVueAppHtml = rawContent.includes('id="app"') && 
                                (rawContent.includes('/ui_assets/') || rawContent.includes('index-'));
            
            if (isVueAppHtml) {
                console.error('[ArtefactSplitView] Received Vue app HTML instead of artefact content. Backend API routing issue.');
                loadError.value = 'API routing error: Static file handler intercepted the request. Please report this issue.';
                dbContent.value = '';
                return;
            }
            
            // Valid HTML content from artefact - keep it as-is
            loadError.value = null;
            
            if (rawContent) {
                // Strip out library-injected context markers to keep the Workspace view "Pure"
                let cleaned = rawContent.trim();
                const headerPattern = /^--- (Document|Skill|Note|Artefact): .*? ---/i;
                const footerPattern = /--- End (Document|Skill|Note|Artefact)(?:: .*?)? ---$/i;
                
                cleaned = cleaned.replace(headerPattern, '').replace(footerPattern, '').trim();
                dbContent.value = cleaned;
                
                console.log('[ArtefactSplitView] Content loaded, length:', cleaned.length);
            } else {
                console.warn('[ArtefactSplitView] Empty content received');
                dbContent.value = '';
            }
        } catch (err) {
            console.error('[ArtefactSplitView] Failed to load artefact content:', err);
            dbContent.value = '';
        } finally {
            isFetching.value = false;
        }
    }

    // Performance Optimisation: Avoid deep watching large nested arrays.
    // Instead, watch a string key combining the file title and versions count.
    const watcherKey = computed(() => {
        if (!artefactGroup.value) return null;
        return `${artefactGroup.value.title}-${artefactGroup.value.versions.length}`;
    });

    watch(watcherKey, async (newVal, oldVal) => {
        if (!newVal) {
            dbContent.value = '';
            selectedVersion.value = null;
            return;
        }

        const group = artefactGroup.value;
        if (!group) return;

        const isNewFileSelection = !oldVal || newVal.split('-')[0] !== oldVal.split('-')[0];
        if (isNewFileSelection) {
            dbContent.value = ''; // Clear previous text immediately to prevent flickering
        }

        const latestVersion = group.versions[0]?.version;
        if (!latestVersion) {
            dbContent.value = '';
            selectedVersion.value = 1;
            return;
        }

        selectedVersion.value = latestVersion;
        await loadVersion(latestVersion);
    }, { immediate: true });

async function handleSave(forceType = null) {
    if (isLiveUpdating.value) return;
    isSaving.value = true;
    try {
        await discussionsStore.updateArtefact({
            discussionId: discussionsStore.currentDiscussionId,
            artefactTitle: title.value,
            newContent: dbContent.value,
            // Ensure we use the correct parameter for the store action
            artefactType: forceType || undefined,
            updateInPlace: false
        });

        // After updating/converting, refresh the context status 
        // to update token counts in the status bar
        if (discussionsStore.currentDiscussionId !== 'saved') {
            await discussionsStore.fetchContextStatus(discussionsStore.currentDiscussionId);
        }

        uiStore.addNotification(forceType ? `Converted to ${forceType}.` : "New version saved.", "success");
    } finally {
        isSaving.value = false;
    }
}

async function handleUndo() {
    if (!artefactGroup.value || artefactGroup.value.versions.length < 2) return;
    const prevVersion = artefactGroup.value.versions[1].version;

    await discussionsStore.revertArtefact({
        discussionId: discussionsStore.currentDiscussionId,
        artefactTitle: title.value,
        version: prevVersion
    });

    selectedVersion.value = prevVersion;
    await loadVersion(prevVersion);
}

async function handleCreateDiscussionFromVersion() {
    if (!selectedVersion.value || !title.value) return;

    const confirmed = await uiStore.showConfirmation({
        title: 'Start New Chat?',
        message: `Create a new discussion and pre-load it with v${selectedVersion.value} of "${title.value}"?`,
        confirmText: 'Start Chat'
    });

    if (confirmed.confirmed) {
        await discussionsStore.createDiscussionWithArtefactVersion({
            discussionId: discussionsStore.currentDiscussionId,
            artefactTitle: title.value,
            version: selectedVersion.value
        });
    }
}

async function handlePushToLibrary(type) {
    // FIX: Reference dbContent.value instead of content.value
    if (!dbContent.value) {
        uiStore.addNotification("Document is empty.", "warning");
        return;
    }

    try {
        if (type === 'saved') {
            await discussionsStore.saveArtefactToLibrary({
                discussionId: discussionsStore.currentDiscussionId,
                artefactTitle: title.value,
                version: selectedVersion.value
            });
        } else if (type === 'note') {
            await notesStore.createNote({
                title: title.value,
                content: dbContent.value
            });
            // FIX: Refresh the notes list so it appears in the sidebar
            await notesStore.fetchNotes();
            uiStore.addNotification("Saved to global Notes library.", "success");
        } else if (type === 'skill') {
            await skillsStore.createSkill({
                name: title.value,
                content: dbContent.value,
                category: 'Imported',
                description: `Created from workspace artefact: ${title.value}`
            });
            // FIX: Refresh the skills list so it appears in the sidebar
            await skillsStore.fetchSkills();
            uiStore.addNotification("Saved to global Skills library.", "success");
        }
    } catch (e) {
        console.error("Library export failed:", e);
        uiStore.addNotification("Failed to export to library.", "error");
    }
}

function download() {
    if (!dbContent.value) return;
    
    const blob = new Blob([dbContent.value], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = title.value || 'document.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
</script>

<template>
    <div 
        class="h-full flex flex-col bg-white dark:bg-gray-950"
        :class="{'fixed inset-0 !w-full z-[100]': isFullscreen}"
    >
        <div class="flex-1 flex flex-col min-w-0">
        <div class="p-3 border-b flex justify-between items-center bg-gray-50 dark:bg-gray-800 shadow-sm relative overflow-hidden">
            <!-- ── [NEW] Generation Animation Bar ── -->
            <div v-if="isLiveUpdating" class="absolute bottom-0 left-0 h-0.5 bg-blue-500 w-full animate-pulse-fast"></div>

            <div class="flex items-center gap-3 min-w-0 z-10">
                <!-- Type-Specific Dynamic Icon & Color -->
                <div class="relative">
                    <div class="p-2 rounded-lg transition-all duration-300" :class="[
                        isLiveUpdating ? 'ring-2 ring-blue-500 ring-offset-2 dark:ring-offset-gray-800 animate-pulse' : '',
                        {
                            'bg-amber-100 text-amber-600': artefactGroup?.versions[0]?.artefact_type === 'note',
                            'bg-emerald-100 text-emerald-600': artefactGroup?.versions[0]?.artefact_type === 'skill',
                            'bg-blue-100 text-blue-600': ['document', 'file'].includes(artefactGroup?.versions[0]?.artefact_type),
                            'bg-purple-100 text-purple-600': artefactGroup?.versions[0]?.artefact_type === 'code'
                        }
                    ]">
                        <IconPencil v-if="artefactGroup?.versions[0]?.artefact_type === 'note'" class="w-4 h-4" />
                        <IconSparkles v-else-if="artefactGroup?.versions[0]?.artefact_type === 'skill'" class="w-4 h-4" />
                        <IconCode v-else-if="artefactGroup?.versions[0]?.artefact_type === 'code'" class="w-4 h-4" />
                        <IconFileText v-else class="w-4 h-4" />
                    </div>
                    <!-- Live Dot -->
                    <div v-if="isLiveUpdating" class="absolute -top-1 -right-1 flex h-3 w-3">
                        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                        <span class="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span>
                    </div>
                </div>
                
                <div class="flex flex-col min-w-0">
                    <div class="flex items-center gap-2">
                        <span class="text-[9px] font-black uppercase tracking-widest" :class="{
                            'text-amber-500': artefactGroup?.versions[0]?.artefact_type === 'note',
                            'text-emerald-500': artefactGroup?.versions[0]?.artefact_type === 'skill',
                            'text-purple-500': artefactGroup?.versions[0]?.artefact_type === 'code',
                            'text-gray-400': !['note', 'skill', 'code'].includes(artefactGroup?.versions[0]?.artefact_type)
                        }">
                            {{ 
                              artefactGroup?.versions[0]?.artefact_type === 'note' ? 'RESEARCH NOTE' :
                              artefactGroup?.versions[0]?.artefact_type === 'skill' ? 'AI CAPABILITY' :
                              artefactGroup?.versions[0]?.artefact_type === 'code' ? 'CODE SNIPPET' :
                              artefactGroup?.versions[0]?.artefact_type === 'file' ? 'EXTERNAL DOCUMENT' :
                              'DOCUMENT'
                            }} WORKSPACE
                        </span>
                        <span v-if="isLiveUpdating" class="text-[8px] font-bold text-blue-500 animate-pulse uppercase tracking-tighter bg-blue-100 dark:bg-blue-900/40 px-1.5 rounded">AI is writing...</span>
                    </div>
                    <span class="font-bold text-sm truncate dark:text-gray-100">{{ title }}</span>
                </div>
            </div>
            <div class="flex items-center gap-1">
                <button @click="isFullscreen = !isFullscreen" class="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg text-gray-500 transition-colors" :title="isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'">
                    <IconMinimize v-if="isFullscreen" class="w-5 h-5" />
                    <IconMaximize v-else class="w-5 h-5" />
                </button>
            </div>
        </div>
        <div class="p-2 border-b border-border-main flex gap-2 items-center bg-bg-card shadow-sm relative z-10">
            <div v-if="artefactGroup" class="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg px-2 py-1 gap-2">
                <span class="text-[10px] font-black text-gray-400 uppercase tracking-tighter">Version</span>
                <select v-model="selectedVersion" @change="loadVersion(selectedVersion)" class="bg-transparent border-none text-xs font-bold text-blue-600 dark:text-blue-400 focus:ring-0 p-0 pr-6">
                    <option v-for="v in artefactGroup.versions" :key="v.version" :value="v.version">
                        v{{ v.version }} {{ v.version === artefactGroup.versions[0].version ? '(Latest)' : '' }}
                    </option>
                </select>
            </div>

            <button @click="uiStore.openModal('artefactVersionManager', { artefactTitle: title })" 
                    class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg text-gray-500 dark:text-gray-400 transition-colors h-8 w-8 flex items-center justify-center shrink-0" 
                    title="Manage Version History (Delete/Squash)">
                <IconClock class="w-4 h-4" />
            </button>

            <button @click="handleUndo" :disabled="artefactGroup?.versions.length < 2 || isSaving" 
                    class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg text-gray-500 dark:text-gray-400 transition-colors h-8 w-8 flex items-center justify-center shrink-0 disabled:opacity-50 disabled:cursor-not-allowed" 
                    title="Quick Undo">
                <IconArrowPath class="w-4 h-4" />
            </button>

            <button @click="handleCreateDiscussionFromVersion" :disabled="!selectedVersion || isSaving" 
                    class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg text-gray-500 dark:text-gray-400 transition-colors h-8 w-8 flex items-center justify-center shrink-0 disabled:opacity-50 disabled:cursor-not-allowed" 
                    title="Start new chat with this version">
                <IconGitBranch class="w-4 h-4" />
            </button>

            <div class="grow"></div>
            
            <!-- Export Dropdown -->
            <DropdownMenu v-if="exportFormats.length > 0" title="Export" icon="ticket" button-class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 transition-colors" collection="ui">
                <button v-for="format in exportFormats" :key="format.value" @click="handleExport(format.value)" class="w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 text-sm">
                    {{ format.label }}
                </button>
                <div v-if="isTtsActive" class="menu-divider"></div>
                <button v-if="isTtsActive" @click="handleExport('wav')" class="w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 text-sm flex items-center justify-between" :disabled="isGeneratingAudio">
                    <div class="flex items-center">
                        <IconSpeakerWave class="w-4 h-4 mr-2 text-blue-500" />
                        <span>Audio (.wav)</span>
                    </div>
                    <IconAnimateSpin v-if="isGeneratingAudio" class="w-3.5 h-3.5 animate-spin" />
                </button>
            </DropdownMenu>

            <!-- Execute/Preview Button -->
            <button v-if="isExecutable" @click="handleExecute" class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 transition-colors" :title="executeTitle" :disabled="isExecuting">
                <IconAnimateSpin v-if="isExecuting" class="w-4 h-4 animate-spin" />
                <IconPlayCircle v-else class="w-4 h-4" />
            </button>

            <button @click="download" class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 transition-colors" title="Download Source">
                <IconArrowDownTray class="w-4 h-4" />
            </button>

            <div class="h-6 w-px bg-gray-200 dark:bg-gray-700 mx-1"></div>

            <!-- Global Library Export -->
            <DropdownMenu title="Library & Types" icon="folder" button-class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-blue-500 transition-colors" collection="ui">
                <!-- EXPORTS: Save copy to global library -->
                <button v-if="!isLiveUpdating" @click="handlePushToLibrary('saved')" class="menu-item">
                    <IconFileText class="w-4 h-4 mr-3 text-blue-500" />
                    <div class="flex flex-col">
                        <span class="font-bold">Save to Featured Library</span>
                        <span class="text-[10px] opacity-60 text-gray-500">Copy to global featured artefacts list</span>
                    </div>
                </button>
                <button @click="handlePushToLibrary('note')" class="menu-item">
                    <IconPencil class="w-4 h-4 mr-3 text-amber-500" />
                    <div class="flex flex-col">
                        <span class="font-bold">Save as Global Note</span>
                        <span class="text-[10px] opacity-60 text-gray-500">Copy to global Notes library</span>
                    </div>
                </button>
                <button @click="handlePushToLibrary('skill')" class="menu-item">
                    <IconSparkles class="w-4 h-4 mr-3 text-emerald-500" />
                    <div class="flex flex-col">
                        <span class="font-bold">Save as Global Skill</span>
                        <span class="text-[10px] opacity-60 text-gray-500">Copy to global Skills library</span>
                    </div>
                </button>

                <div class="menu-divider"></div>
                
                <!-- CONVERSIONS: Change behavior in current chat -->
                <div class="px-4 py-1 text-[9px] font-black uppercase text-gray-400 tracking-widest">Re-categorize in Chat</div>
                
                <button v-if="['note', 'skill'].includes(artefactGroup?.versions[0]?.artefact_type)" @click="handleSave('document')" class="menu-item">
                    <IconFileText class="w-4 h-4 mr-3 text-blue-500" />
                    <span>Convert to Reference File</span>
                </button>
                <button v-if="artefactGroup?.versions[0]?.artefact_type !== 'note'" @click="handleSave('note')" class="menu-item">
                    <IconPencil class="w-4 h-4 mr-3 text-amber-500" />
                    <span>Convert to Research Note</span>
                </button>
                <button v-if="artefactGroup?.versions[0]?.artefact_type !== 'skill'" @click="handleSave('skill')" class="menu-item">
                    <IconSparkles class="w-4 h-4 mr-3 text-emerald-500" />
                    <span>Convert to AI Skill</span>
                </button>

                <div class="menu-divider"></div>
                <button @click="uiStore.openModal('artefactVersionManager', { artefactTitle: title })" class="menu-item text-blue-500 font-bold">
                    <IconScissors class="w-4 h-4 mr-3" />
                    <span>Manage Versions...</span>
                </button>
                </DropdownMenu>

            <!-- Primary Action Button -->
            <div class="flex gap-1">
                <button v-if="artefactGroup?.versions[0]?.artefact_type === 'note'" @click="handlePushToLibrary('note')" class="btn btn-warning btn-sm h-8 flex items-center gap-2 shadow-sm" :disabled="isSaving || isLiveUpdating">
                    <IconPencil class="w-3.5 h-3.5" />
                    <span>Save Note</span>
                </button>
                <button v-else-if="artefactGroup?.versions[0]?.artefact_type === 'skill'" @click="handlePushToLibrary('skill')" class="btn btn-success btn-sm h-8 flex items-center gap-2 shadow-sm" :disabled="isSaving || isLiveUpdating">
                    <IconSparkles class="w-3.5 h-3.5" />
                    <span>Save Skill</span>
                </button>
                <button v-else @click="handleSave()" class="btn btn-primary btn-sm h-8 flex items-center gap-2 shadow-lg shadow-blue-500/10" :disabled="isSaving || isLiveUpdating">
                    <IconRefresh v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
                    <IconPencil v-else class="w-3.5 h-3.5" />
                    <span>Save v{{ (artefactGroup?.versions[0]?.version || 0) + 1 }}</span>
                </button>
            </div>
        </div>
        <div class="flex-1 relative bg-white dark:bg-gray-950">
            <div v-if="isFetching" class="absolute inset-0 z-10 bg-white/50 dark:bg-gray-900/50 backdrop-blur-sm flex items-center justify-center">
                <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin" />
            </div>
            <div v-else-if="loadError" class="absolute inset-0 flex flex-col items-center justify-center text-red-400 p-6 text-center">
                <IconError class="w-12 h-12 mb-4 opacity-50" />
                <p class="text-sm font-medium">{{ loadError }}</p>
                <button @click="loadVersion(selectedVersion)" class="mt-4 btn btn-secondary btn-sm">Retry</button>
            </div>
            <CodeMirrorEditor 
                v-else
                v-model="dbContent" 
                class="absolute inset-0 h-full" 
                :initialMode="dbContent ? 'view' : 'edit'"
                :renderable="true"
                :contentType="detectedContentType"
                :language="detectedLanguage"
                placeholder="Start typing to add content or update the document..."
            />
        </div>
        </div>
    </div>
</template>