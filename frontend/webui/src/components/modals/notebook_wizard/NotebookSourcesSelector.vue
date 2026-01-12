<script setup>
import { ref } from 'vue';
import { useNotebookStore } from '../../../stores/notebooks';
import { useUiStore } from '../../../stores/ui';
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconUpload from '../../../assets/icons/IconUpload.vue';
import IconMagnifyingGlass from '../../../assets/icons/IconMagnifyingGlass.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';

const props = defineProps({
    data: { type: Object, required: true }
});

const notebookStore = useNotebookStore();
const uiStore = useUiStore();

// Local UI helpers
const newUrl = ref('');
const newYoutube = ref('');
const newWiki = ref('');
const newGoogle = ref('');
const arxivQuery = ref('');
const arxivResults = ref([]);
const isSearchingArxiv = ref(false);
const fileInput = ref(null);
const isDragging = ref(false);

function isValidUrl(string) {
    try { const url = new URL(string); return url.protocol === 'http:' || url.protocol === 'https:'; } catch (_) { return false; }
}

function addUrl() {
    const trimmed = newUrl.value.trim();
    if (!trimmed) return;
    if (!isValidUrl(trimmed)) { uiStore.addNotification("Invalid URL", "error"); return; }
    if (!props.data.urls) props.data.urls = [];
    if (!props.data.urls.includes(trimmed)) props.data.urls.push(trimmed);
    newUrl.value = '';
}

function addGoogle() {
    const trimmed = newGoogle.value.trim();
    if (!trimmed) return;
    if (!props.data.google_search_queries) props.data.google_search_queries = [];
    props.data.google_search_queries.push(trimmed);
    newGoogle.value = '';
}

function addYoutube() {
    const trimmed = newYoutube.value.trim();
    if (!trimmed) return;
    if (!trimmed.includes('youtube.com') && !trimmed.includes('youtu.be')) { uiStore.addNotification("Invalid YouTube URL", "error"); return; }
    if (!props.data.youtube_urls) props.data.youtube_urls = [];
    props.data.youtube_urls.push(trimmed);
    newYoutube.value = '';
}

function addWiki() {
    const trimmed = newWiki.value.trim();
    if (!trimmed) return;
    if (!props.data.wikipedia_urls) props.data.wikipedia_urls = [];
    props.data.wikipedia_urls.push(trimmed);
    newWiki.value = '';
}

function removeItem(listName, index) { props.data[listName].splice(index, 1); }

// Arxiv Logic
async function handleArxivSearch() {
    const q = arxivQuery.value.trim();
    if (!q) return;
    isSearchingArxiv.value = true;
    arxivResults.value = [];
    try {
        const results = await notebookStore.searchArxiv(q);
        arxivResults.value = results.map(r => ({ ...r, selected: false, ingest_full: false }));
    } catch (e) { console.error(e); } finally { isSearchingArxiv.value = false; }
}

function isArxivSelected(id) {
    return props.data.arxiv_selected.some(i => i.entry_id === id);
}

function handleArxivCheck(item) {
    if (isArxivSelected(item.entry_id)) {
        props.data.arxiv_selected = props.data.arxiv_selected.filter(i => i.entry_id !== item.entry_id);
    } else {
        props.data.arxiv_selected.push({
            entry_id: item.entry_id, title: item.title, authors: item.authors,
            summary: item.summary, pdf_url: item.pdf_url, ingest_full: item.ingest_full
        });
    }
}

function deselectArxivItem(entryId) {
    props.data.arxiv_selected = props.data.arxiv_selected.filter(i => i.entry_id !== entryId);
}

// File Logic
function triggerFileUpload() { fileInput.value?.click(); }
function handleFiles(event) { addFilesToList(Array.from(event.target.files || [])); event.target.value = ''; }
function addFilesToList(files) {
    if (!props.data.files) props.data.files = [];
    const existingNames = new Set(props.data.files.map(f => f.name));
    const newFiles = files.filter(f => !existingNames.has(f.name));
    props.data.files.push(...newFiles);
}
function removeFile(index) { props.data.files.splice(index, 1); }
function handleDragOver(event) { event.preventDefault(); isDragging.value = true; }
function handleDragLeave(event) { event.preventDefault(); isDragging.value = false; }
function handleDrop(event) { event.preventDefault(); isDragging.value = false; addFilesToList(Array.from(event.dataTransfer.files || [])); }
</script>

<template>
    <div class="h-full flex flex-col">
        <div class="text-center mb-6">
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">Knowledge Sources</h2>
            <p class="text-sm text-gray-500">Optional context for the AI</p>
        </div>
        
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- Left Column -->
            <div class="space-y-5">
                <!-- Arxiv Search -->
                <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg flex flex-col gap-3 border dark:border-gray-700">
                    <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase">📄 Arxiv Papers</label>
                    <div class="flex gap-2">
                        <input v-model="arxivQuery" @keyup.enter="handleArxivSearch" class="input-field flex-grow text-sm" placeholder="Search topic (e.g. 'transformer attention')..." />
                        <button @click="handleArxivSearch" class="btn btn-primary px-3" :disabled="isSearchingArxiv">
                            <IconAnimateSpin v-if="isSearchingArxiv" class="w-4 h-4 animate-spin"/>
                            <IconMagnifyingGlass v-else class="w-4 h-4"/>
                        </button>
                    </div>
                    <!-- Search Results -->
                    <div v-if="arxivResults.length > 0" class="max-h-60 overflow-y-auto custom-scrollbar space-y-2 border-t dark:border-gray-700 pt-2">
                        <div v-for="res in arxivResults" :key="res.entry_id" class="p-3 bg-white dark:bg-gray-700 rounded-lg text-xs shadow-sm border border-transparent hover:border-blue-300 transition-colors">
                            <div class="flex justify-between items-start gap-2">
                                <div class="flex items-start gap-2 flex-grow">
                                    <input type="checkbox" :checked="isArxivSelected(res.entry_id)" @change="handleArxivCheck(res)" class="mt-1 rounded text-blue-600 focus:ring-blue-500" />
                                    <div>
                                        <p class="font-bold text-gray-900 dark:text-white leading-tight">{{ res.title }}</p>
                                        <p class="text-[10px] text-gray-500 mt-0.5">{{ res.authors.slice(0,2).join(', ') }}{{ res.authors.length > 2 ? ' et al.' : '' }} • {{ res.published }}</p>
                                    </div>
                                </div>
                            </div>
                            <div class="mt-2 pl-6 flex items-center justify-between">
                                <label class="flex items-center gap-2 cursor-pointer select-none">
                                    <div class="relative inline-block w-8 h-4 align-middle select-none transition duration-200 ease-in">
                                        <input type="checkbox" v-model="res.ingest_full" class="toggle-checkbox absolute block w-4 h-4 rounded-full bg-white border-4 appearance-none cursor-pointer" :class="res.ingest_full ? 'right-0 border-blue-600' : 'left-0 border-gray-300'"/>
                                        <div class="toggle-label block overflow-hidden h-4 rounded-full cursor-pointer bg-gray-300" :class="res.ingest_full ? 'bg-blue-600' : ''"></div>
                                    </div>
                                    <span class="text-[10px] font-bold uppercase" :class="res.ingest_full ? 'text-blue-600' : 'text-gray-400'">{{ res.ingest_full ? 'Full PDF' : 'Abstract' }}</span>
                                </label>
                                <a :href="res.pdf_url" target="_blank" class="text-blue-500 hover:underline text-[10px]">View PDF ↗</a>
                            </div>
                        </div>
                    </div>
                    <!-- Selected List -->
                    <div v-if="data.arxiv_selected.length > 0" class="border-t dark:border-gray-700 pt-2">
                        <p class="text-[10px] uppercase font-bold text-gray-500 mb-1">Selected Papers ({{ data.arxiv_selected.length }})</p>
                        <ul class="space-y-1 max-h-32 overflow-y-auto custom-scrollbar">
                            <li v-for="item in data.arxiv_selected" :key="item.entry_id" class="flex justify-between items-center text-xs bg-blue-50 dark:bg-blue-900/20 px-2 py-1.5 rounded">
                                <span class="truncate pr-2 font-medium">{{ item.title }} <span v-if="item.ingest_full" class="text-[9px] bg-blue-200 text-blue-800 px-1 rounded ml-1">PDF</span></span>
                                <button @click="deselectArxivItem(item.entry_id)" class="text-red-500 hover:text-red-700"><IconTrash class="w-3 h-3"/></button>
                            </li>
                        </ul>
                    </div>
                </div>

                <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg border dark:border-gray-700">
                    <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase">🌐 Web Links</label>
                    <div class="flex gap-2 my-2"><input v-model="newUrl" @keyup.enter="addUrl" class="input-field flex-grow text-sm" placeholder="https://..." /><button @click="addUrl" class="btn btn-primary px-3"><IconPlus class="w-4 h-4"/></button></div>
                    <ul class="space-y-2 max-h-32 overflow-y-auto custom-scrollbar"><li v-for="(item, idx) in data.urls" :key="idx" class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg border dark:border-gray-600"><span class="truncate pr-2">{{ item }}</span><button @click="removeItem('urls', idx)" class="text-red-500"><IconTrash class="w-4 h-4"/></button></li></ul>
                </div>
            </div>

            <!-- Right Column -->
            <div class="space-y-5">
                <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg border dark:border-gray-700">
                    <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase">🔍 Google Search</label>
                    <div class="flex gap-2 my-2"><input v-model="newGoogle" @keyup.enter="addGoogle" class="input-field flex-grow text-sm" placeholder="Query..." /><button @click="addGoogle" class="btn btn-primary px-3"><IconPlus class="w-4 h-4"/></button></div>
                    <ul class="space-y-2 max-h-32 overflow-y-auto custom-scrollbar"><li v-for="(item, idx) in data.google_search_queries" :key="idx" class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg border dark:border-gray-600"><span class="truncate pr-2">{{ item }}</span><button @click="removeItem('google_search_queries', idx)" class="text-red-500"><IconTrash class="w-4 h-4"/></button></li></ul>
                </div>

                <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg border dark:border-gray-700">
                    <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase">🎥 YouTube Videos</label>
                    <div class="flex gap-2 my-2"><input v-model="newYoutube" @keyup.enter="addYoutube" class="input-field flex-grow text-sm" placeholder="URL..." /><button @click="addYoutube" class="btn btn-primary px-3"><IconPlus class="w-4 h-4"/></button></div>
                    <ul class="space-y-2 max-h-32 overflow-y-auto custom-scrollbar"><li v-for="(item, idx) in data.youtube_urls" :key="idx" class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg border dark:border-gray-600"><span class="truncate pr-2">{{ item }}</span><button @click="removeItem('youtube_urls', idx)" class="text-red-500"><IconTrash class="w-4 h-4"/></button></li></ul>
                </div>

                <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg border dark:border-gray-700">
                    <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase">📚 Wikipedia</label>
                    <div class="flex gap-2 my-2"><input v-model="newWiki" @keyup.enter="addWiki" class="input-field flex-grow text-sm" placeholder="Article Title..." /><button @click="addWiki" class="btn btn-primary px-3"><IconPlus class="w-4 h-4"/></button></div>
                    <ul class="space-y-2 max-h-32 overflow-y-auto custom-scrollbar"><li v-for="(item, idx) in data.wikipedia_urls" :key="idx" class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg border dark:border-gray-600"><span class="truncate pr-2">{{ item }}</span><button @click="removeItem('wikipedia_urls', idx)" class="text-red-500"><IconTrash class="w-4 h-4"/></button></li></ul>
                </div>

                <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg border dark:border-gray-700">
                    <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase">📎 Local Files</label>
                    <div @click="triggerFileUpload" @dragover="handleDragOver" @dragleave="handleDragLeave" @drop="handleDrop" class="border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center text-gray-400 cursor-pointer transition-all h-24 mt-2" :class="isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'">
                        <IconUpload class="w-6 h-6 mb-1"/>
                        <span class="text-xs">Drag & Drop</span>
                    </div>
                    <input type="file" ref="fileInput" @change="handleFiles" multiple class="hidden" />
                    <ul class="mt-3 space-y-2 max-h-32 overflow-y-auto custom-scrollbar"><li v-for="(file, idx) in data.files" :key="idx" class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg border dark:border-gray-600"><span class="truncate pr-2">{{ file.name }}</span><button @click="removeFile(idx)" class="text-red-500"><IconTrash class="w-4 h-4"/></button></li></ul>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
.toggle-checkbox:checked { @apply right-0 border-blue-600; }
.toggle-checkbox:checked + .toggle-label { @apply bg-blue-600; }
</style>
