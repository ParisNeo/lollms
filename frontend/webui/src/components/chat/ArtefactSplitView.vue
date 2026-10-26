<script setup>
import { computed, nextTick, ref, watch, onMounted, onUnmounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import { useNotesStore } from '../../stores/notes';
import { useSkillsStore } from '../../stores/skills';
import apiClient from '../../services/api';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';

import IconDatabase from '../../assets/icons/IconDatabase.vue';
import IconScissors from '../../assets/icons/IconScissors.vue';

import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue';
import IconClock from '../../assets/icons/IconClock.vue';
import IconGitBranch from '../../assets/icons/ui/IconGitBranch.vue';
import IconError from '../../assets/icons/IconError.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconSpeakerWave from '../../assets/icons/IconSpeakerWave.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import { usePyodideStore } from '../../stores/pyodide';
import InteractiveDataGrid from '../ui/DataGrid/InteractiveDataGrid.vue';
import { oneDark } from '@codemirror/theme-one-dark';

const uiStore = useUiStore();
const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const notesStore = useNotesStore();
const skillsStore = useSkillsStore();
const dataStore = useDataStore(); // ADDED: Required for isTtsActive check

const title = computed(() => uiStore.activeSplitArtefactTitle);

const editorExtensions = computed(() => {
    const extensions = [];
    if (uiStore.currentTheme === 'dark') {
        extensions.push(oneDark);
    }
    return extensions;
});

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
const activeLoadedRagStores = computed(() => {
    const loadedIds = discussionsStore.activeDiscussion?.rag_datastore_ids || [];
    const all = [...(dataStore.ownedDataStores || []), ...(dataStore.sharedDataStores || [])];
    if (loadedIds.length > 0) {
        return loadedIds.map(id => all.find(s => s.id === id) || { id, name: `DataStore (${id.substring(0, 8)})` });
    }
    return all;
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
const audioBlobUrl = ref(null);
const asIsBlobUrl = ref(null);
const officeBlobUrl = ref(null);
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
            'owl': 'xml', 'ttl': 'turtle', 'rdf': 'xml',
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
            'xml': 'xml',
            'owl': 'xml',
            'rdf': 'xml',
            'ttl': 'xml',
            'turtle': 'xml'
        };
        return cmLangMap[type] || 'markdown';
    });

    // Only markdown, html, svg, and mermaid should have a visual render preview tab by default
    const isRenderable = computed(() => {
        const type = detectedContentType.value;
        return ['markdown', 'html', 'svg', 'mermaid'].includes(type);
    });

    async function loadVersion(version) {
        if (!version) { isFetching.value = false; return; }
        isFetching.value = true;
        loadError.value = null;
        if (audioBlobUrl.value && !isAudioArtefact.value) {
            URL.revokeObjectURL(audioBlobUrl.value);
            audioBlobUrl.value = null;
        }
        if (officeBlobUrl.value) {
            URL.revokeObjectURL(officeBlobUrl.value);
            officeBlobUrl.value = null;
        }
        try {
            if (isAudioArtefact.value) {
                dbContent.value = '';
                await fetchAudioBlobUrl(version);
            } else {
                dbContent.value = '';
                const { data } = await apiClient.get(`/api/discussions/${discussionsStore.currentDiscussionId}/artefacts/${encodeURIComponent(title.value)}/content?version=${version}`);
                let payload = data;
                if (typeof payload === 'string') {
                    const trimmed = payload.trim();
                    if (trimmed.startsWith('{')) {
                        try { payload = JSON.parse(trimmed); } catch { /* keep as text */ }
                    }
                }
                if (payload && typeof payload === 'object' && payload.__binary_asset__) {
                    // Binary asset (image/office): render via blob, keep dbContent empty
                    if (payload.kind === 'image' || isImageArtefact.value) {
                        await fetchAsIsBlobUrl(version);
                    } else if (payload.kind === 'office' || isOfficeArtefact.value) {
                        await buildOfficePreview(version);
                    }
                } else {
                    dbContent.value = typeof payload === 'string' ? payload : (payload?.content ?? '');
                    if (isImageArtefact.value && !asIsBlobUrl.value) {
                        await fetchAsIsBlobUrl(version);
                    } else if (isOfficeArtefact.value && !officePreviewHtml.value) {
                        await buildOfficePreview(version);
                    }
                }
            }
        } catch (error) {
            loadError.value = "Failed to load version. It might not exist or you may lack permission.";
        } finally {
            isFetching.value = false;
        }
    }

    const isDataArtifact = computed(() => {
        return artefactGroup.value?.versions[0]?.artefact_type === 'data';
    });

const OFFICE_EXTENSIONS = ['pptx', 'pptm', 'docx', 'docm', 'xlsx', 'xlsm', 'xls'];
const isOfficeArtefact = computed(() => {
    const t = (title.value || '').toLowerCase();
    return OFFICE_EXTENSIONS.some(ext => t.endsWith('.' + ext));
});
const isSpreadsheetArtefact = computed(() => {
    const t = (title.value || '').toLowerCase();
    return t.endsWith('.xlsx') || t.endsWith('.xls');
});

// ── Inline Office / Media preview state ──
// NOTE: These declarations MUST stay above the watcherKey watch below —
// the immediate watcher calls resetOfficePreview() during setup, so any
// ref declared after it would hit the temporal dead zone (TDZ).
const VIDEO_EXTENSIONS = ['mp4', 'webm', 'mov', 'm4v', 'mkv', 'avi'];
const VIDEO_MIME_MAP = {
    mp4: 'video/mp4', webm: 'video/webm', mov: 'video/quicktime',
    m4v: 'video/mp4', mkv: 'video/x-matroska', avi: 'video/x-msvideo'
};
const isVideoArtefact = computed(() => {
    const t = (title.value || '').toLowerCase();
    return VIDEO_EXTENSIONS.some(ext => t.endsWith('.' + ext));
});
const isDocxArtefact = computed(() => {
    const t = (title.value || '').toLowerCase();
    return t.endsWith('.docx') || t.endsWith('.docm');
});
const isXlsxArtefact = computed(() => {
    const t = (title.value || '').toLowerCase();
    return t.endsWith('.xlsx') || t.endsWith('.xlsm') || t.endsWith('.xls');
});
const isPptxArtefact = computed(() => {
    const t = (title.value || '').toLowerCase();
    return t.endsWith('.pptx') || t.endsWith('.pptm');
});

const officePreviewHtml = ref('');
const officePreviewLoading = ref(false);
const officePreviewError = ref('');
const xlsxRows = ref([]);
const xlsxSheets = ref([]);
const activeSheet = ref('');
const videoObjectUrl = ref('');
const pptxContainerRef = ref(null);
const pptxRenderActive = ref(false);
const officePreviewFetches = new Map();
// Unified sheet-rows cache: name → string[][]. Populated by BOTH parsers
// (ExcelJS and the raw-XML zip fallback) so tab switching works the same.
const parsedSheetRows = new Map();
// ── @silurus/ooxml XlsxViewer (Tier 0): WASM/Canvas renderer with ──
// embedded-image + classic-chart support. Falls back to the cell-text
// tiers below when a workbook is unsupported.
const xlsxViewerContainerRef = ref(null);
let xlsxViewerInstance = null;
const xlsxRenderMode = ref('silurus'); // 'silurus' | 'exceljs' | 'zip'

function getExt(name) {
    return (name || '').split('.').pop()?.toLowerCase() || '';
}

function destroyXlsxViewer() {
    if (xlsxViewerInstance) {
        try { xlsxViewerInstance.destroy?.(); } catch { /* noop */ }
        xlsxViewerInstance = null;
    }
}

function resetOfficePreview() {
    officePreviewHtml.value = '';
    officePreviewError.value = '';
    officePreviewLoading.value = false;
    officePreviewFetches.clear();
    xlsxRows.value = [];
    xlsxSheets.value = [];
    activeSheet.value = '';
    parsedSheetRows.clear();
    xlsxBufferCache.clear();
    destroyXlsxViewer();
    xlsxRenderMode.value = 'silurus';
    pptxRenderActive.value = false;
    if (pptxContainerRef.value) {
        pptxContainerRef.value.innerHTML = '';
    }
    if (videoObjectUrl.value) {
        URL.revokeObjectURL(videoObjectUrl.value);
        videoObjectUrl.value = '';
    }
}

// Cached ArrayBuffer per title::version so the three render tiers share a
// single download instead of refetching the blob on every fallback.
const xlsxBufferCache = new Map();

async function fetchArtefactArrayBuffer(version) {
    const cacheKey = `${title.value}::v${version ?? 'latest'}`;
    if (xlsxBufferCache.has(cacheKey)) {
        return xlsxBufferCache.get(cacheKey);
    }
    // Prefix with window.location.origin so axios resolves the URL against
    // the page origin (Vite dev proxy / same-origin prod) instead of the
    // apiClient baseURL, which points directly at the backend and triggers
    // CORS on the blob download.
    const downloadUrl = `${window.location.origin}/api/discussions/${encodeURIComponent(discussionsStore.currentDiscussionId)}/artefacts/${encodeURIComponent(title.value)}/download${version ? `?version=${version}` : ''}`;
    const response = await apiClient.get(downloadUrl, { responseType: 'blob' });
    const arrayBuffer = await response.data.arrayBuffer();
    xlsxBufferCache.set(cacheKey, arrayBuffer);
    return arrayBuffer;
}

async function buildDocxPreview(version) {
    const arrayBuffer = await fetchArtefactArrayBuffer(version);
    const mammoth = await import('mammoth');
    const result = await mammoth.convertToHtml({ arrayBuffer });
    officePreviewHtml.value = result.value || '<p><em>Empty document.</em></p>';
}
async function importExcelJS() {
    try {
        return await import('exceljs');
    } catch (e) {
        // Vite dev-server: stale optimize-deps cache returns 504 "Outdated
        // Optimize Dep" for the pre-bundled module. Vite re-optimizes on the
        // next request, so a single retry usually resolves it.
        console.warn('[ArtefactSplitView] exceljs import failed, retrying once after Vite re-optimization...', e);
        await new Promise(resolve => setTimeout(resolve, 300));
        return await import('exceljs');
    }
}

// Bounded wait for the container ref: survives residual timing (HMR,
// double-mount, deferred ref assignment) without blocking the common
// case, where the ref is already populated on the first check.
async function waitForXlsxContainer(timeoutMs = 2000) {
    const start = Date.now();
    while (!xlsxViewerContainerRef.value) {
        if (Date.now() - start > timeoutMs) {
            console.warn('[ArtefactSplitView] container wait timed out; isXlsxArtefact=', isXlsxArtefact.value, 'mode=', xlsxRenderMode.value, 'loading=', officePreviewLoading.value, 'fetching=', isFetching.value);
            return false;
        }
        await nextTick();
        await new Promise(resolve => setTimeout(resolve, 16));
    }
    return true;
}

async function buildXlsxPreviewViaSilurus(arrayBuffer) {
    const { XlsxViewer } = await import('@silurus/ooxml/xlsx');
    // The container div must exist in the DOM before construction. The
    // template mounts it independently of the loading overlay, so the
    // ref is normally populated already; the poll only covers edge cases.
    if (!(await waitForXlsxContainer()) || !xlsxViewerContainerRef.value) {
        throw new Error('XLSX viewer container not rendered');
    }
    destroyXlsxViewer();
    xlsxViewerInstance = new XlsxViewer(xlsxViewerContainerRef.value, {
        showZoomSlider: true,
    });
    await xlsxViewerInstance.load(arrayBuffer);
    xlsxRenderMode.value = 'silurus';
}

async function buildXlsxPreview(version) {
    // Single download shared by all tiers — a transport failure (CORS,
    // backend down) short-circuits with a clear message instead of
    // triggering three doomed refetches.
    let arrayBuffer;
    try {
        arrayBuffer = await fetchArtefactArrayBuffer(version);
    } catch (e) {
        console.error('[ArtefactSplitView] Failed to download artefact:', e);
        officePreviewError.value = 'Could not download the file — check your connection or use the Download button.';
        return;
    }
    // Tier 0: @silurus/ooxml — real rendering engine (images + charts).
    try {
        await buildXlsxPreviewViaSilurus(arrayBuffer);
        return;
    } catch (e) {
        console.warn('[ArtefactSplitView] @silurus/ooxml render failed, falling back to cell-text preview:', e);
        destroyXlsxViewer();
    }
    // Tier 1: ExcelJS — cell values only.
    let workbook = null;
    try {
        const ExcelJS = await importExcelJS();
        workbook = new ExcelJS.Workbook();
        await workbook.xlsx.load(arrayBuffer);
    } catch (e) {
        // ExcelJS chokes on some openpyxl-authored files (hyperlink
        // reconcile dereferences undefined .anchors). Fall back to
        // reading the raw OOXML zip directly.
        console.warn('[ArtefactSplitView] ExcelJS failed to parse xlsx, falling back to raw XML parse:', e);
        await buildXlsxPreviewViaZip(arrayBuffer);
        xlsxRenderMode.value = 'zip';
        return;
    }
    xlsxSheets.value = (workbook.worksheets || []).map(ws => ws.name);
    if (xlsxSheets.value.length === 0) {
        officePreviewError.value = 'This spreadsheet contains no sheets.';
        return;
    }
    parsedSheetRows.clear();
    for (const ws of workbook.worksheets) {
        const rows = [];
        ws.eachRow({ includeEmpty: true }, (row) => {
            const width = Math.max(ws.columnCount, 1);
            const cells = new Array(width).fill('');
            row.eachCell({ includeEmpty: true }, (cell, colNumber) => {
                if (colNumber - 1 < width)cells[colNumber - 1] = normalizeXlsxCell(cell.value);
            });
            rows.push(cells);
        });
        parsedSheetRows.set(ws.name, rows);
    }
    activeSheet.value = xlsxSheets.value[0];
    loadXlsxSheet(activeSheet.value);
    xlsxRenderMode.value = 'exceljs';
}

function loadXlsxSheet(name) {
    const rows = parsedSheetRows.get(name);
    if (!rows) return;
    activeSheet.value = name;
    xlsxRows.value = rows;
}

// Fallback parser: read sheet data straight from the OOXML zip when
// ExcelJS cannot load the workbook (openpyxl hyperlink quirk, etc.).
async function buildXlsxPreviewViaZip(arrayBuffer) {
    const JSZip = await import('jszip');
    const zip = await JSZip.loadAsync(arrayBuffer);
    const parser = new DOMParser();

    const sharedStringsXml = await zip.file('xl/sharedStrings.xml')?.async('string').catch(() => '') || '';
    const sharedStrings = [];
    if (sharedStringsXml) {
        const ssDoc = parser.parseFromString(sharedStringsXml, 'application/xml');
        ssDoc.querySelectorAll('si').forEach((si) => {
            sharedStrings.push(Array.from(si.getElementsByTagName('t')).map((t) => t.textContent).join(''));
        });
    }

    const workbookXml = await zip.file('xl/workbook.xml')?.async('string').catch(() => '') || '';
    const relsXml = await zip.file('xl/_rels/workbook.xml.rels')?.async('string').catch(() => '') || '';
    if (!workbookXml || !relsXml) {
        officePreviewError.value = 'This spreadsheet contains no readable sheets.';
        return;
    }

    const wbDoc = parser.parseFromString(workbookXml, 'application/xml');
    const relsDoc = parser.parseFromString(relsXml, 'application/xml');
    const relMap = {};
    relsDoc.querySelectorAll('Relationship').forEach((rel) => {
        let target = rel.getAttribute('Target') || '';
        if (target.startsWith('/xl/')) target = target.slice(1);
        else if (!target.startsWith('xl/')) target = 'xl/' + target;
        relMap[rel.getAttribute('Id')] = target;
    });

    parsedSheetRows.clear();
    const sheetEls = Array.from(wbDoc.getElementsByTagName('sheet'));
    for (const sheetEl of sheetEls) {
        const name = sheetEl.getAttribute('name') || 'Sheet';
        const rid = sheetEl.getAttribute('r:id') || sheetEl.getAttributeNS('http://schemas.openxmlformats.org/officeDocument/2006/relationships', 'id');
        const path = relMap[rid];
        if (!path) continue;
        const xml = await zip.file(path)?.async('string').catch(() => '') || '';
        if (!xml) continue;
        const sheetDoc = parser.parseFromString(xml, 'application/xml');
        const rows = [];
        sheetDoc.querySelectorAll('sheetData > row').forEach((rowEl) => {
            const cells = [];
            Array.from(rowEl.getElementsByTagName('c')).forEach((c) => {
                const ref = c.getAttribute('r') || '';
                const col = ref.replace(/\d+/g, '');
                const colIdx = col.split('').reduce((acc, ch) => acc * 26 + (ch.charCodeAt(0) - 64), 0) - 1;
                const type = c.getAttribute('t') || '';
                const vEl = c.getElementsByTagName('v')[0];
                let value = vEl ? vEl.textContent : '';
                if (type === 's') value = sharedStrings[Number(value)] ?? '';
                else if (type === 'inlineStr') value = Array.from(c.getElementsByTagName('t')).map((t) => t.textContent).join('');
                while (cells.length < colIdx) cells.push('');
                cells[colIdx] = value;
            });
            rows.push(cells);
        });
        parsedSheetRows.set(name, rows);
    }

    if (parsedSheetRows.size === 0) {
        officePreviewError.value = 'This spreadsheet contains no readable sheets.';
        return;
    }
    xlsxSheets.value = Array.from(parsedSheetRows.keys());
    activeSheet.value = xlsxSheets.value[0];
    xlsxRows.value = parsedSheetRows.get(activeSheet.value);
}

function normalizeXlsxCell(value) {
    if (value === null || value === undefined) return '';
    if (value instanceof Date) return value.toISOString().slice(0, 10);
    if (value.richText) return value.richText.map(t => t.text).join('');
    if (value.hyperlink) return String(value.text ?? value.hyperlink);
    if (value.formula) return String(value.result ?? '');
    if (value.error) return String(value.error);
    return String(value);
}

// Bounded wait for the pptx container ref: mirrors waitForXlsxContainer.
// The template mounts the container independently of the loading overlay,
// so the common case exits on the first check with zero added latency.
async function waitForPptxContainer(timeoutMs = 2000) {
    const start = Date.now();
    while (!pptxContainerRef.value || !pptxContainerRef.value.isConnected) {
        if (Date.now() - start > timeoutMs) {
            console.warn('[ArtefactSplitView] pptx container wait timed out; isPptxArtefact=', isPptxArtefact.value, 'loading=', officePreviewLoading.value, 'fetching=', isFetching.value);
            return false;
        }
        await nextTick();
        await new Promise(resolve => setTimeout(resolve, 16));
    }
    return true;
}

// pptx-preview paints each slide into the host as it parses, but its
// preview() promise can stay pending forever on decks whose embedded
// media never finishes loading. This watchdog resolves as soon as the
// host contains rendered content so the loading overlay is always
// dismissed; it only rejects when nothing at all was painted.
async function waitForPptxPainted(host, baselineChildCount, timeoutMs = 30000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
        if (host.children.length > baselineChildCount) return;
        await new Promise(resolve => setTimeout(resolve, 200));
    }
    if (host.children.length > baselineChildCount || host.innerHTML.trim() !== '') return;
    throw new Error('PPTX renderer produced no output');
}

async function buildPptxPreview(version) {
    // Arm the template branch FIRST so the container mounts before any await.
    pptxRenderActive.value = true;
    const arrayBuffer = await fetchArtefactArrayBuffer(version);
    const { init } = await import('pptx-preview');
    if (!(await waitForPptxContainer()) || !pptxContainerRef.value) {
        throw new Error('PPTX viewer container not rendered');
    }
    const host = pptxContainerRef.value;
    host.innerHTML = '';
    const previewer = init(host, { width: 960, height: 540 });
    const baselineChildCount = host.children.length;
    let previewError = null;
    const previewDone = previewer.preview(arrayBuffer).catch((e) => { previewError = e; });
    await Promise.race([previewDone, waitForPptxPainted(host, baselineChildCount)]);
    if (previewError) throw previewError;
}

async function buildVideoPreview(version) {
    const downloadUrl = `/api/discussions/${encodeURIComponent(discussionsStore.currentDiscussionId)}/artefacts/${encodeURIComponent(title.value)}/download${version ? `?version=${version}` : ''}`;
    const response = await apiClient.get(downloadUrl, { responseType: 'blob' });
    const blob = new Blob([response.data], { type: VIDEO_MIME_MAP[getExt(title.value)] || 'video/mp4' });
    videoObjectUrl.value = URL.createObjectURL(blob);
}

async function buildOfficePreview(version) {
    if (!title.value || !discussionsStore.currentDiscussionId) return;
    const cacheKey = `${title.value}::v${version ?? 'latest'}`;
    if (officePreviewFetches.has(cacheKey)) {
        await officePreviewFetches.get(cacheKey);
        return;
    }
    officePreviewLoading.value = true;
    officePreviewError.value = '';
    const task = (async () => {
        try {
            if (isDocxArtefact.value) await buildDocxPreview(version);
            else if (isXlsxArtefact.value) await buildXlsxPreview(version);
            else if (isPptxArtefact.value) await buildPptxPreview(version);
            else if (isVideoArtefact.value) await buildVideoPreview(version);
        } catch (e) {
            console.error('Inline preview failed:', e);
            pptxRenderActive.value = false;
            officePreviewError.value = 'Preview unavailable — use the Download button instead.';
        } finally {
            officePreviewLoading.value = false;
            officePreviewFetches.delete(cacheKey);
        }
    })();
    officePreviewFetches.set(cacheKey, task);
    await task;
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
            resetOfficePreview();
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
        const targetType = forceType || artefactGroup.value?.versions[0]?.artefact_type || 'document';
        await discussionsStore.updateArtefact({
            discussionId: discussionsStore.currentDiscussionId,
            artefactTitle: title.value,
            newContent: dbContent.value,
            artefactType: targetType,
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

async function handleSendToDataStore(datastoreId, datastoreName) {
    if (!title.value || !discussionsStore.currentDiscussionId) return;

    const confirmed = await uiStore.showConfirmation({
        title: 'Vectorize into DataStore',
        message: `Send "${title.value}" to DataStore "${datastoreName}" for vector indexing? It will be removed from this discussion.`,
        confirmText: 'Vectorize & Remove'
    });

    if (confirmed.confirmed) {
        await discussionsStore.sendArtefactToDataStore({
            discussionId: discussionsStore.currentDiscussionId,
            artefactTitle: title.value,
            datastoreId: datastoreId
        });
    }
}

async function handlePushToLibrary(type) {
    if (!dbContent.value) {
        uiStore.addNotification("Document is empty.", "warning");
        return;
    }

    isSaving.value = true;
    try {
        if (type === 'saved') {
            await discussionsStore.saveArtefactToLibrary({
                discussionId: discussionsStore.currentDiscussionId,
                artefactTitle: title.value,
                version: selectedVersion.value
            });
        } else if (type === 'note') {
            const cleanTitle = title.value.replace(/\.md$/i, '').replace(/\.txt$/i, '');
            await notesStore.createNote({
                title: cleanTitle,
                content: dbContent.value
            });
            await notesStore.fetchNotes();
            if (discussionsStore.currentDiscussionId !== 'saved') {
                await discussionsStore.updateArtefact({
                    discussionId: discussionsStore.currentDiscussionId,
                    artefactTitle: title.value,
                    newContent: dbContent.value,
                    updateInPlace: false
                });
            }
            uiStore.addNotification("Saved to global Notes library.", "success");
        } else if (type === 'skill') {
            const cleanTitle = title.value.replace(/\.md$/i, '').replace(/\.txt$/i, '');
            if (skillsStore.skills.length === 0) {
                await skillsStore.fetchSkills();
            }
            const existing = skillsStore.skills.find(s => s.name.toLowerCase() === cleanTitle.toLowerCase());
            let finalName = cleanTitle;
            let overwrite = true;

            if (existing) {
                const choice = await uiStore.showConfirmation({
                    title: 'Skill Already Exists',
                    message: `A skill named "${cleanTitle}" already exists in your Skills Studio library. Do you want to update the existing skill or save a new version / copy?`,
                    confirmText: 'Update Existing',
                    cancelText: 'Save as New Version'
                });

                if (choice.confirmed) {
                    overwrite = true;
                    finalName = cleanTitle;
                } else {
                    overwrite = false;
                    let vCount = 2;
                    while (skillsStore.skills.some(s => s.name.toLowerCase() === `${cleanTitle} (v${vCount})`.toLowerCase())) {
                        vCount++;
                    }
                    finalName = `${cleanTitle} (v${vCount})`;
                }
            }

            await skillsStore.createSkill({
                name: finalName,
                content: dbContent.value,
                category: artefactGroup.value?.versions[0]?.category || 'General',
                description: artefactGroup.value?.versions[0]?.description || `Skill: ${finalName}`
            }, overwrite);

            await skillsStore.fetchSkills();
            if (discussionsStore.currentDiscussionId !== 'saved') {
                await discussionsStore.updateArtefact({
                    discussionId: discussionsStore.currentDiscussionId,
                    artefactTitle: title.value,
                    newContent: dbContent.value,
                    updateInPlace: false
                });
            }
            uiStore.addNotification(`Saved "${finalName}" to Skills Studio!`, "success");
        }
    } catch (e) {
        console.error("Library export failed:", e);
        uiStore.addNotification("Failed to export to library.", "error");
    } finally {
        isSaving.value = false;
    }
}

const AUDIO_EXTENSIONS = ['mp3', 'wav', 'ogg', 'oga', 'm4a', 'flac', 'webm', 'aac', 'opus'];
const isAudioArtefact = computed(() => {
    const artType = artefactGroup.value?.versions[0]?.artefact_type;
    if (artType === 'audio') return true;
    const ext = (artefactGroup.value?.title || '').split('.').pop()?.toLowerCase();
    return AUDIO_EXTENSIONS.includes(ext);
});

async function fetchAudioBlobUrl(version) {
    if (audioBlobUrl.value) {
        URL.revokeObjectURL(audioBlobUrl.value);
        audioBlobUrl.value = null;
    }
    try {
        const downloadUrl = `/api/discussions/${encodeURIComponent(discussionsStore.currentDiscussionId)}/artefacts/${encodeURIComponent(title.value)}/download${version ? `?version=${version}` : ''}`;
        const response = await apiClient.get(downloadUrl, { responseType: 'blob' });
        const mimeExt = (title.value || '').split('.').pop()?.toLowerCase();
        const mimeMap = {
            mp3: 'audio/mpeg', wav: 'audio/wav', ogg: 'audio/ogg', oga: 'audio/ogg',
            opus: 'audio/ogg', m4a: 'audio/mp4', aac: 'audio/aac',
            flac: 'audio/flac', webm: 'audio/webm'
        };
        const blob = new Blob([response.data], { type: mimeMap[mimeExt] || 'audio/mpeg' });
        audioBlobUrl.value = URL.createObjectURL(blob);
    } catch (e) {
        console.error('Failed to load audio artefact:', e);
        loadError.value = 'Failed to load audio stream.';
    }
}

// AS-IS Native Binary File Detection
const isAsIsFile = computed(() => {
    const c = (dbContent.value || '').trim();
    return c.startsWith('# As-Is File:') || c.includes('**Mode**: AS-IS') || artefactGroup.value?.versions[0]?.artefact_type === 'file';
});

const IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'];
const isImageArtefact = computed(() => {
    const t = (title.value || '').toLowerCase();
    return IMAGE_EXTENSIONS.some(ext => t.endsWith('.' + ext));
});

// ── Image thumbnail for the split-view header (list-row equivalent) ──
// Reuses the authenticated /download blob route (same as fetchAsIsBlobUrl).
// One object URL cached per title+version; all revoked on unmount.
const splitThumbnails = ref({});
const splitThumbFetches = new Map();

function getSplitThumbKey() {
    return `${title.value}::v${selectedVersion.value ?? 'latest'}`;
}

function getSplitThumbnail() {
    if (!isImageArtefact.value || !title.value || !discussionsStore.currentDiscussionId) return '';
    const cacheKey = getSplitThumbKey();
    if (splitThumbnails.value[cacheKey]) return splitThumbnails.value[cacheKey];
    if (splitThumbFetches.has(cacheKey)) return '';

    const version = selectedVersion.value || artefactGroup.value?.versions[0]?.version;
    const fetchPromise = apiClient
        .get(
            `/api/discussions/${encodeURIComponent(discussionsStore.currentDiscussionId)}/artefacts/${encodeURIComponent(title.value)}/download${version ? `?version=${version}` : ''}`,
            { responseType: 'blob' }
        )
        .then((response) => {
            const mimeExt = (title.value || '').split('.').pop()?.toLowerCase();
            const mimeMap = {
                png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg',
                gif: 'image/gif', webp: 'image/webp', bmp: 'image/bmp', svg: 'image/svg+xml'
            };
            const blob = new Blob([response.data], { type: mimeMap[mimeExt] || 'image/png' });
            const url = URL.createObjectURL(blob);
            splitThumbnails.value[cacheKey] = url;
            return url;
        })
        .catch(() => '')
        .finally(() => splitThumbFetches.delete(cacheKey));

    splitThumbFetches.set(cacheKey, fetchPromise);
    return '';
}

watch([title, selectedVersion], () => {
    getSplitThumbnail();
}, { immediate: true });

function releaseSplitThumbnails() {
    Object.values(splitThumbnails.value).forEach((url) => {
        if (url) URL.revokeObjectURL(url);
    });
    splitThumbnails.value = {};
}
const isAsIsImage = computed(() => isImageArtefact.value);

const officeBadgeClass = computed(() => {
    const t = (title.value || '').toLowerCase();
    if (t.endsWith('.pptx')) return 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300';
    if (t.endsWith('.docx')) return 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300';
    return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300';
});
const officeIconClass = computed(() => {
    const t = (title.value || '').toLowerCase();
    if (t.endsWith('.pptx')) return 'bg-orange-50 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400';
    if (t.endsWith('.docx')) return 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400';
    return 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400';
});
const officeHint = computed(() => {
    if (isSpreadsheetArtefact.value) return 'Download to open in Excel — inline preview is not supported for spreadsheets.';
    if ((title.value || '').toLowerCase().endsWith('.pptx')) return 'Download to open in PowerPoint.';
    return 'Download to open in Word.';
});

async function fetchAsIsBlobUrl(version) {
    if (asIsBlobUrl.value) {
        URL.revokeObjectURL(asIsBlobUrl.value);
        asIsBlobUrl.value = null;
    }
    try {
        const downloadUrl = `/api/discussions/${encodeURIComponent(discussionsStore.currentDiscussionId)}/artefacts/${encodeURIComponent(title.value)}/download${version ? `?version=${version}` : ''}`;
        const response = await apiClient.get(downloadUrl, { responseType: 'blob' });
        const mimeExt = (title.value || '').split('.').pop()?.toLowerCase();
        const mimeMap = {
            png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg',
            gif: 'image/gif', webp: 'image/webp', bmp: 'image/bmp'
        };
        const blob = new Blob([response.data], { type: mimeMap[mimeExt] || 'image/png' });
        asIsBlobUrl.value = URL.createObjectURL(blob);
    } catch (e) {
        console.error('Failed to load image artefact:', e);
        loadError.value = 'Failed to load image.';
    }
}

async function fetchOfficeBlobUrl(version) {
    if (officeBlobUrl.value) {
        URL.revokeObjectURL(officeBlobUrl.value);
        officeBlobUrl.value = null;
    }
    try {
        const downloadUrl = `/api/discussions/${encodeURIComponent(discussionsStore.currentDiscussionId)}/artefacts/${encodeURIComponent(title.value)}/download${version ? `?version=${version}` : ''}`;
        const response = await apiClient.get(downloadUrl, { responseType: 'blob' });
        const blob = new Blob([response.data], { type: 'application/octet-stream' });
        officeBlobUrl.value = URL.createObjectURL(blob);
    } catch (e) {
        console.error('Failed to load office artefact:', e);
        loadError.value = 'Failed to load document.';
    }
}

const asIsMetadata = computed(() => {
    if (!isAsIsFile.value) return null;
    const c = dbContent.value || '';
    const fnMatch = c.match(/\*\*Filename\*\*:\s*`?([^`\n]+)`?/i);
    const fmtMatch = c.match(/\*\*Format\*\*:\s*([^\n]+)/i);
    const sizeMatch = c.match(/\*\*Size\*\*:\s*([^\n]+)/i);
    const locMatch = c.match(/\*\*Location\*\*:\s*`?([^`\n]+)`?/i);
    return {
        filename: fnMatch ? fnMatch[1].trim() : title.value,
        format: fmtMatch ? fmtMatch[1].trim() : (title.value?.split('.').pop() || 'FILE').toUpperCase(),
        size: sizeMatch ? sizeMatch[1].trim() : null,
        location: locMatch ? locMatch[1].trim() : title.value
    };
});

onUnmounted(() => {
    releaseSplitThumbnails();
    destroyXlsxViewer();
    if (audioBlobUrl.value) {
        URL.revokeObjectURL(audioBlobUrl.value);
    }
    if (asIsBlobUrl.value) {
        URL.revokeObjectURL(asIsBlobUrl.value);
    }
    if (officeBlobUrl.value) {
        URL.revokeObjectURL(officeBlobUrl.value);
    }
    if (videoObjectUrl.value) {
        URL.revokeObjectURL(videoObjectUrl.value);
    }
});

function download() {
    if (!title.value) return;

    // For AS-IS files or binary documents, download the raw physical binary bytes from the server!
    if (isImageArtefact.value || isOfficeArtefact.value || isAsIsFile.value || artefactGroup.value?.versions[0]?.artefact_type === 'file') {
        const downloadName = asIsMetadata.value?.filename || title.value;
        if (isAsIsImage.value || isOfficeArtefact.value) {
            // Blob-based download guarantees the actual binary is saved (auth-safe, no navigation)
            const downloadUrl = `/api/discussions/${encodeURIComponent(discussionsStore.currentDiscussionId)}/artefacts/${encodeURIComponent(title.value)}/download${selectedVersion.value ? `?version=${selectedVersion.value}` : ''}`;
            apiClient.get(downloadUrl, { responseType: 'blob' })
                .then(response => {
                    const url = URL.createObjectURL(response.data);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = downloadName;
                    a.click();
                    URL.revokeObjectURL(url);
                })
                .catch(() => {
                    uiStore.addNotification("Failed to download file.", "error");
                });
        } else {
            const downloadUrl = `/api/discussions/${discussionsStore.currentDiscussionId}/artefacts/${encodeURIComponent(title.value)}/download`;
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = downloadName;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
        uiStore.addNotification(`Downloading native file: ${downloadName}`, 'info');
        return;
    }

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

<style scoped>
.office-doc-preview :deep(img) { max-width: 100%; height: auto; }
.office-doc-preview :deep(table) { border-collapse: collapse; width: 100%; }
.office-doc-preview :deep(td), .office-doc-preview :deep(th) { border: 1px solid var(--brand-border-muted, #d1d5db); padding: 4px 8px; }
.pptx-preview-container { width: 100%; max-width: 960px; }
.pptx-preview-container :deep(img) { max-width: 100%; height: auto; }
</style>

<template>
    <div class="h-full flex flex-col" :style="{
        backgroundColor: 'var(--brand-bg-app)',
        color: 'var(--brand-text-main)'
    }">
        <div class="flex-1 flex flex-col min-w-0" :style="{
            backgroundColor: 'var(--brand-bg-card)'
        }">
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
                            'bg-purple-100 text-purple-600': ['code', 'audio'].includes(artefactGroup?.versions[0]?.artefact_type)
                        }
                    ]">
                        <img v-if="isImageArtefact && splitThumbnails[getSplitThumbKey()]"
                             :src="splitThumbnails[getSplitThumbKey()]"
                             :alt="title"
                             class="w-6 h-6 rounded object-cover border border-gray-200 dark:border-gray-600" />
                        <IconPencil v-else-if="artefactGroup?.versions[0]?.artefact_type === 'note'" class="w-4 h-4" />
                        <IconSparkles v-else-if="artefactGroup?.versions[0]?.artefact_type === 'skill'" class="w-4 h-4" />
                        <IconCode v-else-if="artefactGroup?.versions[0]?.artefact_type === 'code'" class="w-4 h-4" />
                        <IconSpeakerWave v-else-if="artefactGroup?.versions[0]?.artefact_type === 'audio'" class="w-4 h-4" />
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
                            'text-purple-500': ['code', 'audio'].includes(artefactGroup?.versions[0]?.artefact_type),
                            'text-gray-400': !['note', 'skill', 'code', 'audio'].includes(artefactGroup?.versions[0]?.artefact_type)
                        }">
                            {{ 
                              artefactGroup?.versions[0]?.artefact_type === 'note' ? 'RESEARCH NOTE' :
                              artefactGroup?.versions[0]?.artefact_type === 'skill' ? 'AI CAPABILITY' :
                              artefactGroup?.versions[0]?.artefact_type === 'code' ? 'CODE SNIPPET' :
                              artefactGroup?.versions[0]?.artefact_type === 'audio' ? 'AUDIO TRACK' :
                              artefactGroup?.versions[0]?.artefact_type === 'file' ? 'EXTERNAL DOCUMENT' :
                              'DOCUMENT'
                            }} WORKSPACE
                        </span>
                        <span v-if="isLiveUpdating" class="text-[8px] font-bold text-blue-500 animate-pulse uppercase tracking-tighter bg-blue-100 dark:bg-blue-900/40 px-1.5 rounded">AI is writing...</span>
                    </div>
                    <span class="font-bold text-sm truncate dark:text-gray-100">{{ title }}</span>
                </div>
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

            <button @click="download" class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 transition-colors" :title="isAsIsFile ? 'Download Native Binary File' : 'Download Source'">
                <IconArrowDownTray class="w-4 h-4" :class="{'text-blue-500 font-bold': isAsIsFile}" />
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

                <!-- RAG DATASTORE VECTORIZATION -->
                <div class="px-4 py-1 text-[9px] font-black uppercase text-gray-400 tracking-widest">RAG Knowledge Base</div>
                <template v-if="activeLoadedRagStores.length > 0">
                    <button v-for="store in activeLoadedRagStores" :key="`send-rag-${store.id}`" @click="handleSendToDataStore(store.id, store.name)" class="menu-item">
                        <IconDatabase class="w-4 h-4 mr-3 text-green-500 shrink-0" />
                        <div class="flex flex-col truncate">
                            <span class="font-bold truncate">Vectorize into {{ store.name }}</span>
                            <span class="text-[10px] opacity-60 text-gray-500">Vectorize & purge from chat</span>
                        </div>
                    </button>
                </template>
                <div v-else class="px-4 py-2 text-xs text-gray-400 italic">
                    No DataStores available.
                </div>

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
            <div v-if="!isAudioArtefact" class="flex gap-1">
                <button @click="handleSave()" class="btn btn-primary btn-sm h-8 flex items-center gap-2 shadow-lg shadow-blue-500/10" :disabled="isSaving || isLiveUpdating" :title="`Save new version v${(artefactGroup?.versions[0]?.version || 0) + 1} to discussion workspace`">
                    <IconRefresh v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
                    <IconPencil v-else class="w-3.5 h-3.5" />
                    <span>Save v{{ (artefactGroup?.versions[0]?.version || 0) + 1 }}</span>
                </button>
            </div>
        </div>
        <div class="flex-1 relative bg-white dark:bg-gray-950">
            <!-- Fetching overlay: NON-GATING sibling so the content area
                 (including the silurus container) stays mounted while
                 loadVersion runs its async build. -->
            <div v-if="isFetching" class="absolute inset-0 z-10 bg-white/50 dark:bg-gray-900/50 backdrop-blur-sm flex items-center justify-center">
                <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin" />
            </div>
            <div v-if="loadError" class="absolute inset-0 flex flex-col items-center justify-center text-red-400 p-6 text-center">
                <IconError class="w-12 h-12 mb-4 opacity-50" />
                <p class="text-sm font-medium">{{ loadError }}</p>
                <button @click="loadVersion(selectedVersion)" class="mt-4 btn btn-secondary btn-sm">Retry</button>
            </div>

            <!-- Conditional Rendering: Native AS-IS File Card, Interactive Data Grid, or CodeMirror Editor -->
            <template v-if="!loadError">
                <!-- Interactive Audio Player -->
                <div v-if="isAudioArtefact" class="absolute inset-0 h-full overflow-y-auto custom-scrollbar p-6 flex flex-col items-center justify-center text-center" :style="{
                    backgroundColor: 'var(--brand-bg-app)'
                }">
                    <div class="max-w-xl w-full p-8 rounded-3xl shadow-xl space-y-6 animate-in fade-in" :style="{
                        backgroundColor: 'var(--brand-bg-card)',
                        borderColor: 'var(--brand-border-main)',
                        color: 'var(--brand-text-main)'
                    }" style="border-width: 1px;">
                        <div class="w-20 h-20 rounded-2xl bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 flex items-center justify-center mx-auto shadow-inner">
                            <IconSpeakerWave class="w-10 h-10" />
                        </div>
                        <div class="space-y-1">
                            <span class="px-2.5 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider font-mono" :style="{
                                backgroundColor: 'var(--brand-primary-light)',
                                color: 'var(--brand-primary)'
                            }">
                                {{ (title.split('.').pop() || 'AUDIO').toUpperCase() }} AUDIO
                            </span>
                            <h3 class="text-base font-black break-all" :style="{
                                color: 'var(--brand-text-main)'
                            }">{{ title }}</h3>
                        </div>
                        <div v-if="audioBlobUrl" class="w-full">
                            <audio :src="audioBlobUrl" controls preload="metadata" class="w-full rounded-lg"></audio>
                        </div>
                        <div v-else class="w-full flex items-center justify-center py-4">
                            <IconAnimateSpin class="w-6 h-6 text-purple-500 animate-spin" />
                        </div>
                        <button
                            type="button"
                            @click="download"
                            class="w-full btn btn-primary py-3 rounded-2xl flex items-center justify-center gap-2 shadow-lg shadow-purple-500/20 text-xs font-bold uppercase tracking-wider cursor-pointer transition-all"
                        >
                            <IconArrowDownTray class="w-4 h-4" />
                            <span>Download Original</span>
                        </button>
                    </div>
                </div>

                <!-- AS-IS Image Viewer -->
                <div v-else-if="isAsIsImage" class="absolute inset-0 h-full overflow-y-auto custom-scrollbar p-6 flex flex-col items-center justify-center text-center bg-gray-50/50 dark:bg-gray-900/30">
                    <div class="max-w-3xl w-full p-8 bg-white dark:bg-gray-850 rounded-3xl border border-gray-200/80 dark:border-gray-700 shadow-xl space-y-5 animate-in fade-in">
                        <div class="space-y-1">
                            <span class="px-2.5 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 font-mono">
                                {{ (title.split('.').pop() || 'IMAGE').toUpperCase() }} IMAGE
                            </span>
                            <h3 class="text-base font-black text-gray-900 dark:text-white break-all">
                                {{ asIsMetadata?.filename || title }}
                            </h3>
                        </div>
                        <div v-if="asIsBlobUrl" class="flex items-center justify-center">
                            <img :src="asIsBlobUrl" :alt="title" class="max-w-full max-h-[60vh] rounded-xl shadow-md object-contain" />
                        </div>
                        <div v-else class="w-full flex items-center justify-center py-12">
                            <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin" />
                        </div>
                        <button
                            type="button"
                            @click="download"
                            class="w-full btn btn-primary py-3 rounded-2xl flex items-center justify-center gap-2 shadow-lg shadow-blue-500/20 text-xs font-bold uppercase tracking-wider cursor-pointer active:scale-98 transition-all"
                        >
                            <IconArrowDownTray class="w-4 h-4" />
                            <span>Download Image</span>
                        </button>
                    </div>
                </div>

                <!-- ── Inline Office / Media Previews (docx / xlsx / pptx / video) ── -->
                <div v-else-if="isOfficeArtefact || isVideoArtefact" class="absolute inset-0 h-full overflow-y-auto custom-scrollbar bg-gray-50/50 dark:bg-gray-900/30">
                    <!-- PPTX: slide container. Mounted whenever the pptx
                         builder is armed, INDEPENDENT of the loading state,
                         so buildPptxPreview can find its DOM node while the
                         overlay is up (same pattern as the silurus viewer). -->
                    <div v-if="isPptxArtefact && pptxRenderActive" class="h-full flex flex-col">
                        <div class="grow overflow-auto custom-scrollbar p-4 flex justify-center">
                            <div ref="pptxContainerRef" class="pptx-preview-container"></div>
                        </div>
                    </div>

                    <!-- XLSX: @silurus/ooxml visual viewer (images + charts).
                         Mounted whenever the mode is silurus, INDEPENDENT of
                         the loading state, so the async builder can find its
                         DOM node while the overlay is up. -->
                    <div v-if="isXlsxArtefact && xlsxRenderMode === 'silurus'" class="h-full flex flex-col">
                        <div ref="xlsxViewerContainerRef" class="w-full h-full min-h-[400px]"></div>
                    </div>

                    <!-- Loading overlay (non-gating sibling: paints above the
                         viewer while WASM boots but never unmounts it) -->
                    <div v-if="officePreviewLoading" class="absolute inset-0 z-10 bg-white/50 dark:bg-gray-900/50 backdrop-blur-sm flex flex-col items-center justify-center text-center gap-3">
                        <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin" />
                        <p class="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Rendering preview...</p>
                    </div>

                    <!-- Error fallback -->
                    <div v-else-if="officePreviewError" class="h-full flex flex-col items-center justify-center text-center p-6 gap-4">
                        <IconError class="w-12 h-12 text-red-400 opacity-50" />
                        <p class="text-sm font-medium text-red-400">{{ officePreviewError }}</p>
                        <button @click="download" class="btn btn-primary btn-sm flex items-center gap-2">
                            <IconArrowDownTray class="w-4 h-4" />
                            <span>Download File</span>
                        </button>
                    </div>

                    <!-- PPTX / XLSX-silurus: slides are rendered by the armed
                         containers above. This empty branch terminates the
                         fallback chain so idle/error cards don't stack
                         underneath the live viewers. -->
                    <div v-else-if="(isPptxArtefact && pptxRenderActive) || (isXlsxArtefact && xlsxRenderMode === 'silurus')" class="h-0"></div>

                    <!-- DOCX: rendered HTML -->
                    <div v-else-if="isDocxArtefact && officePreviewHtml" class="p-4 sm:p-8">
                        <div class="max-w-4xl mx-auto bg-white dark:bg-gray-850 rounded-2xl shadow-lg border border-gray-200/80 dark:border-gray-700 p-6 sm:p-10 office-doc-preview">
                            <div class="prose prose-sm sm:prose-base dark:prose-invert max-w-none" v-html="officePreviewHtml"></div>
                        </div>
                    </div>

                    <!-- XLSX: @silurus/ooxml visual viewer (images + charts) -->
                    <div v-else-if="isXlsxArtefact && xlsxRenderMode === 'silurus'" class="h-full flex flex-col">
                        <div ref="xlsxViewerContainerRef" class="w-full h-full min-h-[400px]"></div>
                    </div>

                    <!-- XLSX: scrollable grid with sheet tabs (fallback tiers) -->
                    <div v-else-if="isXlsxArtefact && xlsxRows.length > 0" class="h-full flex flex-col">
                        <div v-if="xlsxSheets.length > 1" class="px-4 pt-3 flex gap-1 overflow-x-auto custom-scrollbar shrink-0">
                            <button v-for="sheet in xlsxSheets" :key="sheet"
                                    @click="loadXlsxSheet(sheet)"
                                    class="px-3 py-1.5 rounded-t-lg text-[11px] font-bold whitespace-nowrap transition-colors"
                                    :class="activeSheet === sheet ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'">
                                {{ sheet }}
                            </button>
                        </div>
                        <div class="grow overflow-auto custom-scrollbar p-4">
                            <table class="border-collapse text-xs font-mono">
                                <tbody>
                                    <tr v-for="(row, rowIndex) in xlsxRows" :key="rowIndex">
                                        <td class="border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 text-gray-400 px-2 py-1 text-[10px] sticky left-0 select-none">{{ rowIndex + 1 }}</td>
                                        <td v-for="(cell, colIndex) in row" :key="colIndex"
                                            class="border border-gray-200 dark:border-gray-700 px-2 py-1 whitespace-nowrap"
                                            :class="rowIndex === 0 ? 'bg-gray-50 dark:bg-gray-800 font-bold' : 'bg-white dark:bg-gray-850'">
                                            {{ cell }}
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- PPTX: rendered slides -->
                    <div v-else-if="isPptxArtefact && pptxSlideCount > 0" class="h-full flex flex-col">
                        <div class="grow overflow-auto custom-scrollbar p-4 flex justify-center">
                            <div ref="pptxContainerRef" class="pptx-preview-container"></div>
                        </div>
                    </div>

                    <!-- Video: blob-URL player (same lifecycle as audio) -->
                    <div v-else-if="isVideoArtefact && videoObjectUrl" class="h-full flex flex-col items-center justify-center p-6">
                        <video :src="videoObjectUrl" controls preload="metadata" class="max-w-full max-h-[80vh] rounded-xl shadow-lg"></video>
                    </div>

                    <!-- Idle / nothing rendered yet -->
                    <div v-else class="h-full flex flex-col items-center justify-center text-center p-6 gap-4">
                        <div class="w-16 h-16 rounded-2xl flex items-center justify-center shadow-inner" :class="officeIconClass">
                            <IconFileText class="w-8 h-8" />
                        </div>
                        <p class="text-xs text-gray-500 dark:text-gray-400">{{ officeHint }}</p>
                        <button @click="download" class="btn btn-primary btn-sm flex items-center gap-2">
                            <IconArrowDownTray class="w-4 h-4" />
                            <span>Download File</span>
                        </button>
                    </div>
                </div>

                <!-- AS-IS Native Binary File Card with Direct Download -->
                <div v-else-if="isAsIsFile" class="absolute inset-0 h-full overflow-y-auto custom-scrollbar p-6 flex flex-col items-center justify-center text-center bg-gray-50/50 dark:bg-gray-900/30">
                    <div class="max-w-md w-full p-8 bg-white dark:bg-gray-850 rounded-3xl border border-gray-200/80 dark:border-gray-700 shadow-xl space-y-5 animate-in fade-in">
                        <div class="w-20 h-20 rounded-2xl bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 flex items-center justify-center mx-auto shadow-inner">
                            <IconFileText class="w-10 h-10" />
                        </div>

                        <div class="space-y-1">
                            <span class="px-2.5 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 font-mono">
                                {{ asIsMetadata?.format || 'NATIVE' }} FILE
                            </span>
                            <h3 class="text-base font-black text-gray-900 dark:text-white break-all">
                                {{ asIsMetadata?.filename || title }}
                            </h3>
                            <p v-if="asIsMetadata?.size" class="text-xs font-mono text-gray-500 dark:text-gray-400">
                                {{ asIsMetadata.size }}
                            </p>
                        </div>

                        <div class="p-3 bg-gray-50 dark:bg-gray-900 rounded-xl text-left text-[11px] text-gray-600 dark:text-gray-400 space-y-1 border dark:border-gray-800">
                            <p class="font-semibold text-gray-800 dark:text-gray-200">Preserved in workspace:</p>
                            <p class="font-mono text-[10px] text-gray-500 break-all">{{ asIsMetadata?.location || title }}</p>
                            <p class="text-[10px] italic text-gray-400 pt-1">The AI interacts directly with this native document using document tools without cluttering your context window.</p>
                        </div>

                        <!-- Direct Download Native File Action Button -->
                        <button 
                            type="button" 
                            @click="download" 
                            class="w-full btn btn-primary py-3 rounded-2xl flex items-center justify-center gap-2 shadow-lg shadow-blue-500/20 text-xs font-bold uppercase tracking-wider cursor-pointer active:scale-98 transition-all"
                        >
                            <IconArrowDownTray class="w-4 h-4" />
                            <span>Download Native File</span>
                        </button>
                    </div>
                </div>

                <InteractiveDataGrid 
                    v-else-if="isDataArtifact"
                    :discussionId="discussionsStore.currentDiscussionId"
                    :title="title"
                    :version="selectedVersion"
                    class="absolute inset-0 h-full"
                />
                <CodeMirrorEditor 
                    v-else
                    v-model="dbContent" 
                    class="absolute inset-0 h-full" 
                    :initialMode="isRenderable ? 'view' : 'edit'"
                    :renderable="isRenderable"
                    :extensions="editorExtensions"
                    :contentType="detectedContentType"
                    :language="detectedLanguage"
                    placeholder="Start typing to add content or update the document..."
                />
            </template>
        </div>
        </div>
    </div>
</template>
