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
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconMinimize from '../../assets/icons/IconMinimize.vue';
import IconError from '../../assets/icons/IconError.vue';
import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';
import { useAuthStore } from '../../stores/auth';

const uiStore = useUiStore();
const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const notesStore = useNotesStore();
const skillsStore = useSkillsStore();

const title = computed(() => uiStore.activeSplitArtefactTitle);
const isFullscreen = ref(false);

const exportFormats = computed(() => {
    const formats = [];
    if (authStore.export_to_txt_enabled) formats.push({ label: 'Text (.txt)', value: 'txt' });
    if (authStore.export_to_markdown_enabled) formats.push({ label: 'Markdown (.md)', value: 'md' });
    if (authStore.export_to_html_enabled) formats.push({ label: 'HTML (.html)', value: 'html' });
    if (authStore.export_to_pdf_enabled) formats.push({ label: 'PDF (.pdf)', value: 'pdf' });
    if (authStore.export_to_docx_enabled) formats.push({ label: 'Word (.docx)', value: 'docx' });
    return formats;
});

function handleExport(format) {
    discussionsStore.exportRawContent({ 
        content: content.value, 
        format: format 
    });
}

// Track if this file is currently being modified by AI - Added defensive checks
const isLiveUpdating = computed(() => {
    if (!title.value || !discussionsStore.activeUpdatingArtefacts) return false;
    return discussionsStore.activeUpdatingArtefacts.has(title.value);
});

const artefactGroup = computed(() => {
    if (!title.value) return null;
    const all = discussionsStore.activeDiscussionArtefacts || [];
    console.log('[ArtefactSplitView] Checking artefacts for title:', title.value, 'available:', all.map(a => `${a.title}(v${a.version})`));
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
const loadError = ref(null);


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
            'svg': 'svg', 'graphql': 'graphql', 'proto': 'protobuf',
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
            'css': 'html', // CodeMirror uses html mode for css in some configs, or we could add css
            'json': 'javascript',
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

    // [FIX] Robust observer: Automatically loads the latest version whenever a file is selected
    // or when a new version is created by the AI.
    watch(() => artefactGroup.value, async (newGroup, oldGroup) => {
        // If no group is found, we might still be loading or nothing is selected
        if (!newGroup) {
            if (!title.value) {
                dbContent.value = '';
                selectedVersion.value = null;
            }
            return;
        }

        const isNewFileSelection = !oldGroup || newGroup.title !== oldGroup.title;
        const hasNewVersion = oldGroup && newGroup.versions.length > oldGroup.versions.length;

        // Trigger load if:
        // 1. We just switched to a different file
        // 2. The AI just added a new version to the current file
        // 3. The workspace is open but no version is selected yet (initial load)
        if (isNewFileSelection || hasNewVersion || selectedVersion.value === null) {
            
            if (isNewFileSelection) {
                dbContent.value = ''; // Clear previous text immediately to prevent flickering
            }

            // Default to the latest version (at index 0 due to our DESC sorting)
            const latestVersion = newGroup.versions[0]?.version;
            
            // If no versions exist yet (new file), just clear and ready for editing
            if (!latestVersion) {
                dbContent.value = '';
                selectedVersion.value = 1;
                return;
            }
            
            // Sync the dropdown state and fetch the actual text content
            selectedVersion.value = latestVersion;
            await loadVersion(latestVersion);
        }
    }, { immediate: true, deep: true });

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
        await discussionsStore.fetchContextStatus(discussionsStore.currentDiscussionId);
        
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

async function handlePushToLibrary(type) {
    // FIX: Reference dbContent.value instead of content.value
    if (!dbContent.value) {
        uiStore.addNotification("Document is empty.", "warning");
        return;
    }
    
    try {
        if (type === 'note') {
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
        <div class="p-2 border-b border-gray-200 dark:border-gray-700 flex gap-2 items-center bg-white dark:bg-gray-850 shadow-sm relative z-10">
            <div v-if="artefactGroup" class="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg px-2 py-1 gap-2">
                <span class="text-[10px] font-black text-gray-400 uppercase tracking-tighter">Version</span>
                <select v-model="selectedVersion" @change="loadVersion(selectedVersion)" class="bg-transparent border-none text-xs font-bold text-blue-600 dark:text-blue-400 focus:ring-0 p-0 pr-6">
                    <option v-for="v in artefactGroup.versions" :key="v.version" :value="v.version">
                        v{{ v.version }} {{ v.version === artefactGroup.versions[0].version ? '(Latest)' : '' }}
                    </option>
                </select>
            </div>

            <button @click="handleUndo" :disabled="artefactGroup?.versions.length < 2 || isSaving" 
                    class="btn btn-secondary btn-xs h-8" title="Restore previous version">
                <IconArrowPath class="w-3.5 h-3.5 mr-1" />
                Undo
            </button>
            
            <div class="flex-grow"></div>
            
            <!-- Export Dropdown -->
            <DropdownMenu v-if="exportFormats.length > 0" title="Export" icon="ticket" button-class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 transition-colors" collection="ui">
                <button v-for="format in exportFormats" :key="format.value" @click="handleExport(format.value)" class="w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 text-sm">
                    {{ format.label }}
                </button>
            </DropdownMenu>

            <button @click="download" class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 transition-colors" title="Download Source">
                <IconArrowDownTray class="w-4 h-4" />
            </button>

            <div class="h-6 w-px bg-gray-200 dark:bg-gray-700 mx-1"></div>

            <!-- Global Library Export -->
            <DropdownMenu title="Library & Types" icon="folder" button-class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-blue-500 transition-colors" collection="ui">
                <!-- EXPORTS: Save copy to global library -->
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
            </DropdownMenu>

            <!-- Primary Action Button -->
            <div class="flex gap-1">
                <button v-if="artefactGroup?.versions[0]?.artefact_type === 'note'" @click="handleSave()" class="btn btn-warning btn-sm h-8 flex items-center gap-2 shadow-sm" :disabled="isSaving || isLiveUpdating">
                    <IconSave class="w-3.5 h-3.5" />
                    <span>Save Note</span>
                </button>
                <button v-else-if="artefactGroup?.versions[0]?.artefact_type === 'skill'" @click="handleSave()" class="btn btn-success btn-sm h-8 flex items-center gap-2 shadow-sm" :disabled="isSaving || isLiveUpdating">
                    <IconCheckCircle class="w-3.5 h-3.5" />
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
            <div v-else-if="!dbContent" class="absolute inset-0 flex flex-col items-center justify-center text-gray-400">
                <IconPencil class="w-12 h-12 mb-4 opacity-30" />
                <p class="text-sm font-medium">This file is empty</p>
                <p class="text-xs mt-1 opacity-60">Start typing to add content</p>
            </div>
            <CodeMirrorEditor 
                v-else
                v-model="dbContent" 
                class="absolute inset-0 h-full" 
                :initialMode="'view'"
                :renderable="true"
                :contentType="detectedContentType"
                :language="detectedLanguage"
            />
        </div>
        </div>
    </div>
</template>