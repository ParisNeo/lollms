<template>
    <div class="statusbar bg-gray-50 dark:bg-gray-700/50 p-1 border-t border-gray-300 dark:border-gray-600 flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 px-2 select-none">
        <div class="flex items-center gap-2 sm:gap-3">
            <div class="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 font-bold uppercase text-[9px] tracking-widest border border-blue-200 dark:border-blue-800" :title="`Active language: ${language}`">
                <span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
                {{ language }}
            </div>
            <span>{{ charCount }} characters</span>

            <!-- Actions Group -->
            <div class="flex items-center gap-0.5">
                <!-- Copy to Clipboard -->
                <button @click="copyContent" class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-all active:scale-90 text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200" title="Copy to clipboard">
                    <svg v-if="!justCopied" xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                    <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>
                </button>

                <!-- Download / Save to Disk -->
                <button @click="saveContentToDisk" class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-all active:scale-90 text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200" :title="`Download as '${synthesizedFileName}'`">
                    <svg v-if="!justDownloaded" xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
                    <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>
                </button>
            </div>
        </div>
        
        <div v-if="allowedModes === 'both'" class="flex items-center rounded-md border border-gray-300 dark:border-gray-500 bg-gray-200 dark:bg-gray-900/50 p-0.5">
            <button @click="$emit('set-mode', 'edit')" title="Edit Mode" :class="['mode-button', currentMode === 'edit' ? 'active' : 'inactive']">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.5L14.732 3.732z"></path></svg>
                <span>Edit</span>
            </button>
            <button @click="$emit('set-mode', 'view')" title="Render Mode" :class="['mode-button', currentMode === 'view' ? 'active' : 'inactive']">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
                <span>Render</span>
            </button>
        </div>
        <div v-else class="text-[10px] uppercase font-bold tracking-tight opacity-50 px-2">
            {{ allowedModes === 'edit_only' ? 'Editor Only' : 'Render Only' }}
        </div>
    </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { useUiStore } from '../../../stores/ui';

const props = defineProps({
    modelValue: { type: String, required: true },
    language: { type: String, default: 'markdown' },
    allowedModes: { type: String, default: 'both' },
    currentMode: { type: String, default: 'edit' }
});

defineEmits(['set-mode']);

const uiStore = useUiStore();
const justCopied = ref(false);
const justDownloaded = ref(false);

const charCount = computed(() => (props.modelValue || '').length);

// 1. Language to File Extension Mapping
function getFileExtension(lang) {
    const l = (lang || '').toLowerCase().trim();
    const map = {
        'markdown': 'md',
        'md': 'md',
        'python': 'py',
        'py': 'py',
        'javascript': 'js',
        'js': 'js',
        'typescript': 'ts',
        'ts': 'ts',
        'html': 'html',
        'htm': 'html',
        'css': 'css',
        'scss': 'scss',
        'json': 'json',
        'xml': 'xml',
        'yaml': 'yaml',
        'yml': 'yaml',
        'svg': 'svg',
        'mermaid': 'mmd',
        'latex': 'tex',
        'tex': 'tex',
        'sql': 'sql',
        'bash': 'sh',
        'sh': 'sh',
        'shell': 'sh',
        'powershell': 'ps1',
        'rust': 'rs',
        'go': 'go',
        'c++': 'cpp',
        'cpp': 'cpp',
        'c': 'c',
        'csharp': 'cs',
        'cs': 'cs',
        'java': 'java',
        'kotlin': 'kt',
        'ruby': 'rb',
        'php': 'php',
        'r': 'r',
        'swift': 'swift',
        'owl': 'owl',
        'ttl': 'ttl',
        'turtle': 'ttl',
        'rdf': 'rdf',
        'vue': 'vue',
        'txt': 'txt',
        'plaintext': 'txt'
    };
    return map[l] || 'txt';
}

// 2. MIME Type Mapping
function getMimeType(ext) {
    const map = {
        'md': 'text/markdown;charset=utf-8',
        'py': 'text/x-python;charset=utf-8',
        'js': 'text/javascript;charset=utf-8',
        'ts': 'text/typescript;charset=utf-8',
        'html': 'text/html;charset=utf-8',
        'css': 'text/css;charset=utf-8',
        'json': 'application/json;charset=utf-8',
        'xml': 'application/xml;charset=utf-8',
        'svg': 'image/svg+xml;charset=utf-8',
        'yaml': 'text/yaml;charset=utf-8',
        'yml': 'text/yaml;charset=utf-8',
        'tex': 'application/x-tex;charset=utf-8',
        'sql': 'text/x-sql;charset=utf-8',
        'sh': 'application/x-sh;charset=utf-8',
        'txt': 'text/plain;charset=utf-8'
    };
    return map[ext] || 'text/plain;charset=utf-8';
}

// 3. Synthesized Title Extraction Engine
function sanitizeFileName(name) {
    if (!name) return '';
    return name
        .trim()
        .replace(/[\\/:*?"<>|#`$@!%^&*()+={}\[\];,~]/g, '_')
        .replace(/\s+/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_+|_+$/g, '');
}

const synthesizedTitle = computed(() => {
    const raw = (props.modelValue || '').trim();
    if (!raw) return 'document';

    const lang = (props.language || '').toLowerCase().trim();
    const lines = raw.split('\n');

    // Strategy A: Explicit File Name Annotations (e.g. [CREATE] path/to/file.ext or --- Document: title ---)
    for (let i = 0; i < Math.min(lines.length, 5); i++) {
        const line = lines[i].trim();
        const createMatch = line.match(/^(?:#|\/\/|\/\*|<!--)?\s*\[(?:CREATE|UPDATE)\]\s*([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)/i);
        if (createMatch) {
            const base = createMatch[1].split(/[/\\]/).pop();
            return base.replace(/\.[^/.]+$/, '');
        }
        const docBlockMatch = line.match(/^---\s*(?:Document|Note|Skill|Artefact):\s*(.*?)\s*---/i);
        if (docBlockMatch) {
            return docBlockMatch[1].replace(/\.[^/.]+$/, '');
        }
    }

    // Strategy B: JSON Structure Extraction
    if (lang === 'json' || (raw.startsWith('{') && raw.endsWith('}'))) {
        try {
            const parsed = JSON.parse(raw);
            if (typeof parsed === 'object' && parsed !== null) {
                const candidate = parsed.name || parsed.title || parsed.id || parsed.label;
                if (candidate && typeof candidate === 'string') {
                    return candidate;
                }
            }
        } catch (e) { /* ignore JSON parse error */ }
    }

    // Strategy C: HTML / XML / SVG Titles
    if (['html', 'xml', 'svg'].includes(lang) || raw.startsWith('<')) {
        const titleTagMatch = raw.match(/<title\b[^>]*>(.*?)<\/title>/i);
        if (titleTagMatch && titleTagMatch[1].trim()) {
            return titleTagMatch[1].trim();
        }
        const h1TagMatch = raw.match(/<h1\b[^>]*>(.*?)<\/h1>/i);
        if (h1TagMatch && h1TagMatch[1].trim()) {
            const cleanH1 = h1TagMatch[1].replace(/<[^>]+>/g, '').trim();
            if (cleanH1) return cleanH1;
        }
    }

    // Strategy D: Markdown Headings & YAML Frontmatter
    if (lang === 'markdown' || lang === 'md' || !lang) {
        const frontmatterMatch = raw.match(/^---\s*\n([\s\S]*?)\n---/);
        if (frontmatterMatch) {
            const titleLine = frontmatterMatch[1].split('\n').find(l => l.trim().toLowerCase().startsWith('title:'));
            if (titleLine) {
                const val = titleLine.split(':').slice(1).join(':').trim().replace(/^['"]|['"]$/g, '');
                if (val) return val;
            }
        }

        for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith('#')) {
                const clean = trimmed.replace(/^#+\s*/, '').trim();
                if (clean) return clean;
            }
        }
    }

    // Strategy E: Python / Code Comments & Definitions
    if (['python', 'py', 'sh', 'bash', 'yaml', 'yml'].includes(lang)) {
        for (let i = 0; i < Math.min(lines.length, 10); i++) {
            const trimmed = lines[i].trim();
            if (trimmed.startsWith('#') && !trimmed.startsWith('#!')) {
                const clean = trimmed.replace(/^#+\s*/, '').replace(/^(title|file|filename|description):\s*/i, '').trim();
                if (clean && clean.length > 2 && clean.length < 60) return clean;
            }
            if (trimmed.startsWith('class ') || trimmed.startsWith('def ')) {
                const defMatch = trimmed.match(/(?:class|def)\s+([a-zA-Z0-9_]+)/);
                if (defMatch) return defMatch[1];
            }
        }
    }

    // Strategy F: JS / TS / C / C++ / Java / C# Comments & Classes
    if (['javascript', 'js', 'typescript', 'ts', 'java', 'c', 'cpp', 'cs', 'php', 'rust', 'go'].includes(lang)) {
        for (let i = 0; i < Math.min(lines.length, 10); i++) {
            const trimmed = lines[i].trim();
            if (trimmed.startsWith('//') || trimmed.startsWith('/*')) {
                const clean = trimmed.replace(/^\/\/[/*\s]*/, '').replace(/\*\/$/, '').replace(/^(title|file|filename|description):\s*/i, '').trim();
                if (clean && clean.length > 2 && clean.length < 60) return clean;
            }
            if (trimmed.match(/^(?:export\s+)?(?:default\s+)?(?:class|function|const|interface|struct|enum)\s+([a-zA-Z0-9_]+)/)) {
                const defMatch = trimmed.match(/(?:class|function|const|interface|struct|enum)\s+([a-zA-Z0-9_]+)/);
                if (defMatch) return defMatch[1];
            }
        }
    }

    // Strategy G: First meaningful non-empty text line (up to 5 words)
    for (const line of lines) {
        const trimmed = line.trim().replace(/^[^a-zA-Z0-9]+/, '');
        if (trimmed.length > 2) {
            const words = trimmed.split(/\s+/).slice(0, 5).join('_');
            if (words) return words.substring(0, 40);
        }
    }

    return 'document';
});

const synthesizedFileName = computed(() => {
    const ext = getFileExtension(props.language);
    const safeTitle = sanitizeFileName(synthesizedTitle.value) || 'document';
    return `${safeTitle}.${ext}`;
});

async function copyContent() {
    const success = await uiStore.copyToClipboard(props.modelValue, null);
    if (success) {
        justCopied.value = true;
        setTimeout(() => justCopied.value = false, 2000);
    }
}

function saveContentToDisk() {
    const content = props.modelValue || '';
    if (!content) {
        uiStore.addNotification('Editor content is empty.', 'warning');
        return;
    }

    const filename = synthesizedFileName.value;
    const ext = getFileExtension(props.language);
    const mime = getMimeType(ext);

    try {
        const blob = new Blob([content], { type: mime });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        justDownloaded.value = true;
        uiStore.addNotification(`Saved as '${filename}'`, 'success', 2500);
        setTimeout(() => justDownloaded.value = false, 2000);
    } catch (e) {
        console.error('Failed to save file:', e);
        uiStore.addNotification('Could not save file to disk.', 'error');
    }
}
</script>

<style scoped>
@reference "tailwindcss";

.mode-button {
    @apply flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold transition-all cursor-pointer select-none;
}
.mode-button.active {
    @apply bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-xs font-bold;
}
.mode-button.inactive {
    @apply text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200;
}
</style>