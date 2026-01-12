<script setup>
import { ref, computed } from 'vue';
import { useNotebookStore } from '../../stores/notebooks';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';

// Icons
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconWeb from '../../assets/icons/IconWeb.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconVideoCamera from '../../assets/icons/IconVideoCamera.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconDocumentText from '../../assets/icons/IconDocumentText.vue';

const notebookStore = useNotebookStore();
const uiStore = useUiStore();

const modalData = computed(() => uiStore.modalData('artefactImportWizard'));
const notebookId = computed(() => modalData.value?.notebookId);

const activeTab = ref('files');
const isProcessing = ref(false);
const isSearchingArxiv = ref(false);

// Arxiv search state
const arxivQuery = ref('');
const arxivResults = ref([]);
const arxivSelected = ref([]);

const form = ref({
    urls: [],
    wikipedia_urls: [],
    youtube_configs: [], // { url: '', lang: 'en' }
    files: [],
    manual_title: '',
    manual_content: ''
});

const languages = [
    { code: 'en', name: 'English' },
    { code: 'fr', name: 'French' },
    { code: 'es', name: 'Spanish' },
    { code: 'de', name: 'German' },
    { code: 'it', name: 'Italian' },
    { code: 'pt', name: 'Portuguese' },
    { code: 'zh', name: 'Chinese' },
    { code: 'ja', name: 'Japanese' },
    { code: 'ru', name: 'Russian' }
];

// Temp inputs
const tempUrl = ref('');
const tempWiki = ref('');
const tempYt = ref({ url: '', lang: 'en' });
const fileInput = ref(null);

const addUrl = () => { if (tempUrl.value.trim()) { form.value.urls.push(tempUrl.value.trim()); tempUrl.value = ''; } };
const addWiki = () => { if (tempWiki.value.trim()) { form.value.wikipedia_urls.push(tempWiki.value.trim()); tempWiki.value = ''; } };
const addYt = () => { if (tempYt.value.url.trim()) { form.value.youtube_configs.push({ ...tempYt.value }); tempYt.value.url = ''; } };
const onFileChange = (e) => { form.value.files.push(...Array.from(e.target.files)); e.target.value = ''; };

// Arxiv functions
async function handleArxivSearch() {
    const q = arxivQuery.value.trim();
    if (!q) return;
    isSearchingArxiv.value = true;
    arxivResults.value = [];
    try {
        const results = await notebookStore.searchArxiv(q);
        arxivResults.value = results.map(r => ({
            ...r,
            selected: false,
            ingest_full: false
        }));
    } catch (e) {
        console.error(e);
    } finally {
        isSearchingArxiv.value = false;
    }
}

function toggleArxivSelection(result) {
    result.selected = !result.selected;
    updateArxivSelected();
}

function toggleArxivFullText(result) {
    result.ingest_full = !result.ingest_full;
    updateArxivSelected();
}

function updateArxivSelected() {
    // Update the selected list based on current results
    arxivSelected.value = arxivResults.value
        .filter(r => r.selected)
        .map(r => ({
            entry_id: r.entry_id,
            title: r.title,
            authors: r.authors,
            summary: r.summary,
            pdf_url: r.pdf_url,
            ingest_full: r.ingest_full
        }));
}

function isArxivSelected(id) {
    return arxivSelected.value.some(i => i.entry_id === id);
}

const hasContent = computed(() => {
    return form.value.urls.length > 0 ||
           form.value.wikipedia_urls.length > 0 ||
           form.value.youtube_configs.length > 0 ||
           form.value.files.length > 0 ||
           (form.value.manual_title.trim() && form.value.manual_content.trim()) ||
           arxivSelected.value.length > 0;
});

async function handleImport() {
    if (!notebookId.value) return;
    isProcessing.value = true;
    try {
        // 1. Process List-based imports (URLs, Wiki, YouTube)
        if (form.value.urls.length || form.value.wikipedia_urls.length || form.value.youtube_configs.length) {
            await notebookStore.importSources({
                urls: form.value.urls,
                wikipedia_urls: form.value.wikipedia_urls,
                youtube_configs: form.value.youtube_configs
            });
        }

        // 2. Process Files
        for (const file of form.value.files) {
            await notebookStore.uploadSource(file, true);
        }

        // 3. Process Manual Text
        if (form.value.manual_title && form.value.manual_content) {
            await notebookStore.createManualArtefact(form.value.manual_title, form.value.manual_content);
        }

        // 4. Process Arxiv selections
        if (arxivSelected.value.length > 0) {
            await notebookStore.importSources({
                arxiv_selected: arxivSelected.value
            });
        }

        uiStore.addNotification("Knowledge import tasks started.", "success");
        uiStore.closeModal('artefactImportWizard');
    } catch (e) {
        uiStore.addNotification("Import failed.", "error");
    } finally {
        isProcessing.value = false;
    }
}

const tabs = [
    { id: 'files', label: 'Documents', icon: IconFileText },
    { id: 'web', label: 'Links', icon: IconWeb },
    { id: 'wiki', label: 'Wikipedia', icon: IconBookOpen },
    { id: 'youtube', label: 'YouTube', icon: IconVideoCamera },
    { id: 'arxiv', label: 'Arxiv', icon: IconDocumentText },
    { id: 'manual', label: 'Manual Text', icon: IconPencil }
];
</script>

<template>
    <GenericModal modalName="artefactImportWizard" title="Knowledge Import Wizard" maxWidthClass="max-w-2xl">
        <template #body>
            <div class="flex flex-col h-[500px]">
                <!-- Tab Navigation -->
                <div class="flex border-b dark:border-gray-700 overflow-x-auto no-scrollbar bg-gray-50 dark:bg-gray-800/50 p-1">
                    <button v-for="tab in tabs" :key="tab.id" @click="activeTab = tab.id"
                        class="flex items-center gap-2 px-4 py-2 text-[10px] font-black uppercase tracking-widest transition-all rounded-lg"
                        :class="activeTab === tab.id ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'">
                        <component :is="tab.icon" class="w-4 h-4" />
                        {{ tab.label }}
                    </button>
                </div>

                <!-- Tab Content -->
                <div class="flex-grow p-6 overflow-y-auto custom-scrollbar">

                    <!-- FILES -->
                    <div v-if="activeTab === 'files'" class="space-y-4">
                        <div @click="fileInput.click()" class="border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-3xl p-12 text-center cursor-pointer hover:bg-blue-50 dark:hover:bg-blue-900/10 transition-all group">
                            <IconPlus class="w-12 h-12 mx-auto text-gray-300 group-hover:text-blue-500 mb-4 transition-colors" />
                            <p class="text-sm font-black uppercase tracking-tighter text-gray-500">Drop Documents Here</p>
                            <p class="text-[10px] text-gray-400 mt-1 uppercase tracking-widest">PDF, DOCX, PPTX, TXT, MD</p>
                            <input type="file" ref="fileInput" @change="onFileChange" multiple class="hidden" />
                        </div>
                        <div class="flex flex-wrap gap-2">
                            <div v-for="(f, i) in form.files" :key="i" class="px-3 py-1.5 bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded-xl text-[10px] font-bold flex items-center gap-2 border border-purple-100 dark:border-purple-800">
                                <span class="truncate max-w-[200px]">{{ f.name }}</span>
                                <button @click="form.files.splice(i,1)" class="hover:text-red-500"><IconXMark class="w-3 h-3"/></button>
                            </div>
                        </div>
                    </div>

                    <!-- WEB URLS -->
                    <div v-if="activeTab === 'web'" class="space-y-4">
                        <div class="flex gap-2">
                            <input v-model="tempUrl" @keyup.enter="addUrl" placeholder="Enter link (https://...)" class="input-field flex-grow" />
                            <button @click="addUrl" class="btn btn-secondary"><IconPlus class="w-5 h-5" /></button>
                        </div>
                        <div class="space-y-2">
                            <div v-for="(u, i) in form.urls" :key="i" class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-xl text-xs border dark:border-gray-700">
                                <span class="truncate pr-4 font-medium">{{ u }}</span>
                                <button @click="form.urls.splice(i,1)" class="text-red-500 hover:scale-110 transition-transform"><IconXMark class="w-4 h-4"/></button>
                            </div>
                        </div>
                    </div>

                    <!-- WIKIPEDIA -->
                    <div v-if="activeTab === 'wiki'" class="space-y-4">
                        <div class="p-4 bg-blue-50 dark:bg-blue-900/10 rounded-2xl border border-blue-100 dark:border-blue-900/30 text-[10px] text-blue-700 dark:text-blue-300 font-bold uppercase tracking-widest">
                            Ground your notebook with full Wikipedia articles.
                        </div>
                        <div class="flex gap-2">
                            <input v-model="tempWiki" @keyup.enter="addWiki" placeholder="Article Title or Wiki URL..." class="input-field flex-grow" />
                            <button @click="addWiki" class="btn btn-secondary"><IconPlus class="w-5 h-5" /></button>
                        </div>
                        <div class="space-y-2">
                            <div v-for="(u, i) in form.wikipedia_urls" :key="i" class="flex items-center justify-between p-3 bg-gray-100 dark:bg-gray-850 rounded-xl text-xs border-l-4 border-gray-400">
                                <span class="truncate pr-4 font-bold">{{ u }}</span>
                                <button @click="form.wikipedia_urls.splice(i,1)" class="text-red-500 hover:scale-110"><IconXMark class="w-4 h-4"/></button>
                            </div>
                        </div>
                    </div>

                    <!-- YOUTUBE -->
                    <div v-if="activeTab === 'youtube'" class="space-y-4">
                        <div class="flex gap-2">
                            <input v-model="tempYt.url" placeholder="YouTube Video URL..." class="input-field flex-grow" />
                            <select v-model="tempYt.lang" class="input-field w-32">
                                <option v-for="l in languages" :key="l.code" :value="l.code">{{ l.name }}</option>
                            </select>
                            <button @click="addYt" class="btn btn-secondary"><IconPlus class="w-5 h-5" /></button>
                        </div>
                        <div class="space-y-2">
                            <div v-for="(y, i) in form.youtube_configs" :key="i" class="flex items-center justify-between p-3 bg-red-50 dark:bg-red-900/10 rounded-xl text-xs border-l-4 border-red-500">
                                <span class="truncate pr-4 font-bold text-red-700 dark:text-red-400">{{ y.url }}</span>
                                <div class="flex items-center gap-3">
                                    <span class="text-[9px] font-black uppercase px-2 py-1 bg-white dark:bg-gray-800 rounded border border-red-200">{{ y.lang }}</span>
                                    <button @click="form.youtube_configs.splice(i,1)" class="text-red-500 hover:scale-110"><IconXMark class="w-4 h-4"/></button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- ARXIV -->
                    <div v-if="activeTab === 'arxiv'" class="space-y-4">
                        <div class="p-4 bg-orange-50 dark:bg-orange-900/10 rounded-2xl border border-orange-100 dark:border-orange-900/30 text-[10px] text-orange-700 dark:text-orange-300 font-bold uppercase tracking-widest">
                            Search and import research papers from Arxiv.
                        </div>

                        <div class="flex gap-2">
                            <input v-model="arxivQuery" @keyup.enter="handleArxivSearch" placeholder="Search Arxiv (e.g. 'transformer attention')..." class="input-field flex-grow" />
                            <button @click="handleArxivSearch" class="btn btn-secondary" :disabled="isSearchingArxiv">
                                <IconAnimateSpin v-if="isSearchingArxiv" class="w-4 h-4 animate-spin"/>
                                <IconMagnifyingGlass v-else class="w-4 h-4"/>
                            </button>
                        </div>

                        <!-- Search Results -->
                        <div v-if="arxivResults.length > 0" class="space-y-2 max-h-80 overflow-y-auto custom-scrollbar border-t dark:border-gray-700 pt-2">
                            <div v-for="res in arxivResults" :key="res.entry_id" class="p-3 bg-white dark:bg-gray-700 rounded-lg text-xs shadow-sm border border-transparent hover:border-blue-300 transition-colors">
                                <div class="flex justify-between items-start gap-2">
                                    <div class="flex items-start gap-2 flex-grow">
                                        <input type="checkbox" :checked="isArxivSelected(res.entry_id)" @change="toggleArxivSelection(res)" class="mt-1 rounded text-blue-600 focus:ring-blue-500" />
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
                        <div v-if="arxivSelected.length > 0" class="border-t dark:border-gray-700 pt-2">
                            <p class="text-[10px] uppercase font-bold text-gray-500 mb-1">Selected Papers ({{ arxivSelected.length }})</p>
                            <ul class="space-y-1 max-h-32 overflow-y-auto custom-scrollbar">
                                <li v-for="item in arxivSelected" :key="item.entry_id" class="flex justify-between items-center text-xs bg-blue-50 dark:bg-blue-900/20 px-2 py-1.5 rounded">
                                    <span class="truncate pr-2 font-medium">{{ item.title }} <span v-if="item.ingest_full" class="text-[9px] bg-blue-200 text-blue-800 px-1 rounded ml-1">PDF</span></span>
                                    <button @click="toggleArxivSelection(arxivResults.find(r => r.entry_id === item.entry_id))" class="text-red-500 hover:text-red-700"><IconXMark class="w-3 h-3"/></button>
                                </li>
                            </ul>
                        </div>
                    </div>

                    <!-- MANUAL TEXT -->
                    <div v-if="activeTab === 'manual'" class="space-y-4 h-full flex flex-col">
                        <input v-model="form.manual_title" placeholder="Artefact Title (e.g. Brainstorming Notes)" class="input-field font-bold" />
                        <textarea v-model="form.manual_content" placeholder="Paste or type content here..." class="flex-grow input-field text-sm leading-relaxed min-h-[200px] resize-none"></textarea>
                    </div>

                </div>

                <!-- Footer -->
                <div class="p-6 border-t dark:border-gray-700 flex justify-end items-center gap-3 bg-gray-50 dark:bg-gray-800/30">
                    <button @click="uiStore.closeModal('artefactImportWizard')" class="btn btn-secondary px-6">Cancel</button>
                    <button @click="handleImport" :disabled="!hasContent || isProcessing" class="btn btn-primary px-10 relative shadow-lg shadow-blue-500/20 font-black uppercase text-xs tracking-widest">
                        <IconAnimateSpin v-if="isProcessing" class="w-4 h-4 mr-2 animate-spin" />
                        Start Ingestion
                    </button>
                </div>
            </div>
        </template>
    </GenericModal>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }

/* Toggle Checkbox Styling */
.toggle-checkbox:checked {
  @apply: right-0 border-blue-600;
  right: 0;
  border-color: #2563EB;
}
.toggle-checkbox:checked + .toggle-label {
  @apply: bg-blue-600;
  background-color: #2563EB;
}
</style>
