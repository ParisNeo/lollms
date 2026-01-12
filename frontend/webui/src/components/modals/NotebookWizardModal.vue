<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useUiStore } from '../../stores/ui';
import { useNotebookStore } from '../../stores/notebooks';
import GenericModal from './GenericModal.vue';

// Icons
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconVideoCamera from '../../assets/icons/IconVideoCamera.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconUpload from '../../assets/icons/IconUpload.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';

const router = useRouter(); 
const uiStore = useUiStore();
const notebookStore = useNotebookStore();

const step = ref(1);
const isProcessing = ref(false);
const showStopConfirmation = ref(false);
const fileInput = ref(null);
const isDragging = ref(false);

const wizardData = ref({
    title: '',
    type: 'generic',
    initialPrompt: '',
    urls: [],
    youtube_urls: [],
    wikipedia_urls: [],
    google_search_queries: [],
    arxiv_selected: [], 
    files: [],
    raw_text: '',
    num_slides: 10,
    slide_format: 'TitleImageBody',
    style_preset: 'Corporate Vector',
    custom_style: ''
});

// UI helpers
const newUrl = ref('');
const newYoutube = ref('');
const newWiki = ref('');
const newGoogle = ref('');
const arxivQuery = ref('');
const arxivResults = ref([]);
const isSearchingArxiv = ref(false);

const projectTypes = [
    { id: 'generic', label: 'General Research', icon: IconFileText, desc: 'A standard notebook for organizing research and notes.' },
    { id: 'slides_making', label: 'Presentation Deck', icon: IconPresentationChartBar, desc: 'Generate slides, visuals, and speaker notes.' },
    { id: 'youtube_video', label: 'Video Production', icon: IconVideoCamera, desc: 'Create scripts, storyboards, and asset lists for video.' },
    { id: 'book_building', label: 'Book / Long-form', icon: IconBookOpen, desc: 'Plan and write structured long-form content.' },
];

const slideFormats = [
    { id: 'ImageOnly', label: 'Full Image Slides', desc: 'Cinematic full-screen visuals with voiceover.' },
    { id: 'TitleImageBody', label: 'Standard Hybrid', desc: 'Balanced mix of text, bullets, and images.' },
    { id: 'TextOnly', label: 'Text Heavy', desc: 'Information dense slides with titles and bullets.' },
    { id: 'HTML_Graph', label: 'Data & Graphs', desc: 'Includes instructions for HTML-based data visualization.' }
];

const stylePresets = [
    'Photorealistic', 'Corporate Vector', 'Hand Drawn Illustration', 'Minimalist Flat', 'Cyberpunk / Neon', 'Watercolor', 'Abstract 3D', 'Custom'
];

const canProceedStep1 = computed(() => wizardData.value.title.trim().length > 0);

function nextStep() {
    if (step.value === 1 && !canProceedStep1.value) {
        uiStore.addNotification("Please enter a project title", "error");
        return;
    }
    if (step.value < 3) step.value++;
}

function prevStep() {
    if (step.value > 1) step.value--;
}

function closeModal() {
    uiStore.closeModal('notebookWizard');
    setTimeout(() => {
        step.value = 1;
        wizardData.value = { 
            title: '', type: 'generic', initialPrompt: '', 
            urls: [], youtube_urls: [], wikipedia_urls: [], 
            google_search_queries: [], arxiv_selected: [], 
            files: [], raw_text: '',
            num_slides: 10, slide_format: 'TitleImageBody', style_preset: 'Corporate Vector', custom_style: ''
        };
        isProcessing.value = false;
        newUrl.value = '';
        newYoutube.value = '';
        newWiki.value = '';
        newGoogle.value = '';
        arxivQuery.value = '';
        arxivResults.value = [];
    }, 300);
}

function isValidUrl(string) {
    try { const url = new URL(string); return url.protocol === 'http:' || url.protocol === 'https:'; } catch (_) { return false; }
}

function addUrl() {
    const trimmed = newUrl.value.trim();
    if (!trimmed) return;
    if (!isValidUrl(trimmed)) { uiStore.addNotification("Invalid URL", "error"); return; }
    if (!wizardData.value.urls) wizardData.value.urls = [];
    if (wizardData.value.urls.includes(trimmed)) return;
    wizardData.value.urls.push(trimmed);
    newUrl.value = '';
}

function addGoogle() {
    const trimmed = newGoogle.value.trim();
    if (!trimmed) return;
    if (!wizardData.value.google_search_queries) wizardData.value.google_search_queries = [];
    wizardData.value.google_search_queries.push(trimmed);
    newGoogle.value = '';
}

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

function selectArxivItem(item) {
    if (!wizardData.value.arxiv_selected.some(i => i.entry_id === item.entry_id)) {
        wizardData.value.arxiv_selected.push({
            entry_id: item.entry_id, title: item.title, authors: item.authors,
            summary: item.summary, pdf_url: item.pdf_url, ingest_full: item.ingest_full
        });
    }
}

function deselectArxivItem(entryId) {
    wizardData.value.arxiv_selected = wizardData.value.arxiv_selected.filter(i => i.entry_id !== entryId);
}

const isArxivSelected = (id) => wizardData.value.arxiv_selected.some(i => i.entry_id === id);

function handleArxivCheck(item) {
    if (isArxivSelected(item.entry_id)) deselectArxivItem(item.entry_id);
    else selectArxivItem(item);
}

function addYoutube() {
    const trimmed = newYoutube.value.trim();
    if (!trimmed) return;
    if (!trimmed.includes('youtube.com') && !trimmed.includes('youtu.be')) { uiStore.addNotification("Invalid YouTube URL", "error"); return; }
    if (!wizardData.value.youtube_urls) wizardData.value.youtube_urls = [];
    wizardData.value.youtube_urls.push(trimmed);
    newYoutube.value = '';
}

function addWiki() {
    const trimmed = newWiki.value.trim();
    if (!trimmed) return;
    if (!wizardData.value.wikipedia_urls) wizardData.value.wikipedia_urls = [];
    wizardData.value.wikipedia_urls.push(trimmed);
    newWiki.value = '';
}

function removeItem(listName, index) { wizardData.value[listName].splice(index, 1); }
function triggerFileUpload() { fileInput.value?.click(); }
function handleFiles(event) { addFilesToList(Array.from(event.target.files || [])); event.target.value = ''; }
function addFilesToList(files) {
    if (!wizardData.value.files) wizardData.value.files = [];
    const existingNames = new Set(wizardData.value.files.map(f => f.name));
    const newFiles = files.filter(f => !existingNames.has(f.name));
    wizardData.value.files.push(...newFiles);
}
function removeFile(index) { wizardData.value.files.splice(index, 1); }
function handleDragOver(event) { event.preventDefault(); isDragging.value = true; }
function handleDragLeave(event) { event.preventDefault(); isDragging.value = false; }
function handleDrop(event) { event.preventDefault(); isDragging.value = false; addFilesToList(Array.from(event.dataTransfer.files || [])); }

function getSuggestedPrompt() {
    const base = "Analyze the sources and generate content.";
    const prompts = {
        generic: "Create a comprehensive research summary with key findings.",
        slides_making: `Create a ${wizardData.value.num_slides}-slide deck about the topic.`,
        youtube_video: "Develop a video script with timestamps and B-roll.",
        book_building: "Generate a detailed chapter outline."
    };
    
    let final = prompts[wizardData.value.type] || base;
    if (['slides_making', 'youtube_video'].includes(wizardData.value.type)) {
        final += ` Use the '${wizardData.value.style_preset === 'Custom' ? wizardData.value.custom_style : wizardData.value.style_preset}' visual style.`;
        if (wizardData.value.slide_format === 'HTML_Graph') final += " Include data visualizations where appropriate.";
    }
    
    wizardData.value.initialPrompt = final;
}

async function createProject() {
    if (!wizardData.value.initialPrompt.trim()) {
        uiStore.addNotification("Instructions required", "error");
        return;
    }
    isProcessing.value = true;

    try {
        const payload = {
            title: wizardData.value.title,
            type: wizardData.value.type,
            initialPrompt: wizardData.value.initialPrompt,
            urls: wizardData.value.urls || [],
            youtube_configs: (wizardData.value.youtube_urls || []).map(url => ({ url, lang: 'en' })),
            wikipedia_urls: wizardData.value.wikipedia_urls || [],
            google_search_queries: wizardData.value.google_search_queries || [],
            arxiv_selected: wizardData.value.arxiv_selected || [],
            raw_text: wizardData.value.raw_text,
            metadata: {
                num_slides: wizardData.value.num_slides,
                slide_format: wizardData.value.slide_format,
                style_preset: wizardData.value.style_preset === 'Custom' ? wizardData.value.custom_style : wizardData.value.style_preset
            },
            delay_processing: true // Always delay backend trigger so we can do it manually here
        };

        // 1. Create the notebook (DB Entry + Tabs)
        const newNotebook = await notebookStore.createStructuredNotebook(payload);
        
        // Force Active Notebook
        notebookStore.setActiveNotebook(newNotebook);

        // 2. Upload Files (if any)
        if (wizardData.value.files?.length > 0) {
            for (const file of wizardData.value.files) {
                const useDocling = ['.pdf', '.docx', '.pptx'].some(ext => file.name.toLowerCase().endsWith(ext));
                await notebookStore.uploadSource(file, useDocling);
            }
        }

        // 3. Find the Target Tab for the output
        let targetTabId = null;
        if (newNotebook.tabs && newNotebook.tabs.length > 0) {
            const typePriority = ['slides', 'youtube_script', 'book_plan', 'markdown'];
            for (const type of typePriority) {
                const found = newNotebook.tabs.find(t => t.type === type);
                if (found) { targetTabId = found.id; break; }
            }
            if (!targetTabId) targetTabId = newNotebook.tabs[0].id;
        }

        // 4. Trigger Build Task
        // We ALWAYS trigger this if there is a prompt, regardless of whether we have external links.
        // The prompt drives the generation (using files if no links are present).
        if (payload.initialPrompt) {
            await notebookStore.importSources(newNotebook.id, {
                ...payload,
                initialPrompt: payload.initialPrompt, 
                target_tab_id: targetTabId
            });
        }

        uiStore.addNotification(`"${wizardData.value.title}" created!`, "success");
        closeModal();

        // 5. Redirect to Notebook View
        await router.push(`/notebooks/${newNotebook.id}`);

    } catch (e) {
        console.error(e);
        uiStore.addNotification("Failed to start project.", "error");
    } finally {
        isProcessing.value = false;
    }
}

function stopCreation() {
    showStopConfirmation.value = true;
}

async function confirmStopCreation() {
    showStopConfirmation.value = false;
    closeModal();
}
</script>

<template>
    <GenericModal modalName="notebookWizard" title="New Production Wizard" maxWidthClass="max-w-6xl" :showCloseButton="true" @close="closeModal">
        <div class="flex flex-col h-full max-h-[85vh]">
            
            <!-- Progress Stepper -->
            <div class="flex items-center justify-center mb-8 flex-shrink-0">
                <div class="flex items-center">
                    <div class="relative"><div class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300" :class="step >= 1 ? 'bg-blue-600 text-white shadow-lg' : 'bg-gray-200 text-gray-500'"><IconCheckCircle v-if="step > 1" class="w-5 h-5" /><span v-else>1</span></div></div>
                    <div class="w-20 h-1 bg-gray-200 mx-2"><div class="h-full bg-blue-600 transition-all duration-500" :style="{width: step > 1 ? '100%' : '0%'}"></div></div>
                    <div class="relative"><div class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300" :class="step >= 2 ? 'bg-blue-600 text-white shadow-lg' : 'bg-gray-200 text-gray-500'"><IconCheckCircle v-if="step > 2" class="w-5 h-5" /><span v-else>2</span></div></div>
                    <div class="w-20 h-1 bg-gray-200 mx-2"><div class="h-full bg-blue-600 transition-all duration-500" :style="{width: step > 2 ? '100%' : '0%'}"></div></div>
                    <div class="relative"><div class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300" :class="step >= 3 ? 'bg-blue-600 text-white shadow-lg' : 'bg-gray-200 text-gray-500'">3</div></div>
                </div>
            </div>

            <!-- STEP 1: Type & Title -->
            <div v-if="step === 1" class="flex-grow overflow-y-auto custom-scrollbar px-2 mt-4">
                <div class="text-center mb-8"><h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">Choose Project Type</h2></div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
                    <div v-for="type in projectTypes" :key="type.id" @click="wizardData.type = type.id"
                         class="group p-6 rounded-xl border-2 cursor-pointer transition-all hover:shadow-lg flex flex-col items-center text-center gap-3"
                         :class="wizardData.type === type.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 shadow-md' : 'border-gray-200 dark:border-gray-700 hover:border-blue-300'">
                        <component :is="type.icon" class="w-12 h-12 transition-transform group-hover:scale-110" :class="wizardData.type === type.id ? 'text-blue-600' : 'text-gray-400'" />
                        <div><h3 class="font-bold text-base text-gray-900 dark:text-white mb-1">{{ type.label }}</h3><p class="text-xs text-gray-500">{{ type.desc }}</p></div>
                    </div>
                </div>
                <div class="space-y-3 max-w-2xl mx-auto">
                    <label class="block text-sm font-bold text-gray-700 dark:text-gray-300">Project Title <span class="text-red-500">*</span></label>
                    <input v-model="wizardData.title" class="input-field w-full text-lg px-4 py-3 border-2 transition-colors focus:border-blue-500" placeholder="e.g. 'Project Mars'" @keyup.enter="canProceedStep1 && nextStep()" />
                </div>
            </div>

            <!-- STEP 2: Sources -->
            <div v-if="step === 2" class="flex-grow overflow-y-auto custom-scrollbar px-2">
                <div class="text-center mb-6"><h2 class="text-2xl font-bold text-gray-900 dark:text-white">Knowledge Sources</h2><p class="text-sm text-gray-500">Optional context for the AI</p></div>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- Left Column -->
                    <div class="space-y-5">
                        
                        <!-- Arxiv Search -->
                        <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg flex flex-col gap-3">
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
                            <div v-if="wizardData.arxiv_selected.length > 0" class="border-t dark:border-gray-700 pt-2">
                                <p class="text-[10px] uppercase font-bold text-gray-500 mb-1">Selected Papers ({{ wizardData.arxiv_selected.length }})</p>
                                <ul class="space-y-1 max-h-32 overflow-y-auto custom-scrollbar">
                                    <li v-for="item in wizardData.arxiv_selected" :key="item.entry_id" class="flex justify-between items-center text-xs bg-blue-50 dark:bg-blue-900/20 px-2 py-1.5 rounded">
                                        <span class="truncate pr-2 font-medium">{{ item.title }} <span v-if="item.ingest_full" class="text-[9px] bg-blue-200 text-blue-800 px-1 rounded ml-1">PDF</span></span>
                                        <button @click="deselectArxivItem(item.entry_id)" class="text-red-500 hover:text-red-700"><IconTrash class="w-3 h-3"/></button>
                                    </li>
                                </ul>
                            </div>
                        </div>

                        <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg">
                            <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase">🌐 Web Links</label>
                            <div class="flex gap-2 my-2"><input v-model="newUrl" @keyup.enter="addUrl" class="input-field flex-grow text-sm" placeholder="https://..." /><button @click="addUrl" class="btn btn-primary px-3"><IconPlus class="w-4 h-4"/></button></div>
                            <ul class="space-y-2 max-h-32 overflow-y-auto custom-scrollbar"><li v-for="(item, idx) in wizardData.urls" :key="idx" class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg"><span class="truncate pr-2">{{ item }}</span><button @click="removeItem('urls', idx)" class="text-red-500"><IconTrash class="w-4 h-4"/></button></li></ul>
                        </div>
                    </div>

                    <!-- Right Column -->
                    <div class="space-y-5">
                        <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg">
                            <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase">🔍 Google Search</label>
                            <div class="flex gap-2 my-2"><input v-model="newGoogle" @keyup.enter="addGoogle" class="input-field flex-grow text-sm" placeholder="Query..." /><button @click="addGoogle" class="btn btn-primary px-3"><IconPlus class="w-4 h-4"/></button></div>
                            <ul class="space-y-2 max-h-32 overflow-y-auto custom-scrollbar"><li v-for="(item, idx) in wizardData.google_search_queries" :key="idx" class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg"><span class="truncate pr-2">{{ item }}</span><button @click="removeItem('google_search_queries', idx)" class="text-red-500"><IconTrash class="w-4 h-4"/></button></li></ul>
                        </div>

                        <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg">
                            <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase">🎥 YouTube Videos</label>
                            <div class="flex gap-2 my-2"><input v-model="newYoutube" @keyup.enter="addYoutube" class="input-field flex-grow text-sm" placeholder="URL..." /><button @click="addYoutube" class="btn btn-primary px-3"><IconPlus class="w-4 h-4"/></button></div>
                            <ul class="space-y-2 max-h-32 overflow-y-auto custom-scrollbar"><li v-for="(item, idx) in wizardData.youtube_urls" :key="idx" class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg"><span class="truncate pr-2">{{ item }}</span><button @click="removeItem('youtube_urls', idx)" class="text-red-500"><IconTrash class="w-4 h-4"/></button></li></ul>
                        </div>
                        <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg">
                            <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase">📚 Wikipedia</label>
                            <div class="flex gap-2 my-2"><input v-model="newWiki" @keyup.enter="addWiki" class="input-field flex-grow text-sm" placeholder="Article Title..." /><button @click="addWiki" class="btn btn-primary px-3"><IconPlus class="w-4 h-4"/></button></div>
                            <ul class="space-y-2 max-h-32 overflow-y-auto custom-scrollbar"><li v-for="(item, idx) in wizardData.wikipedia_urls" :key="idx" class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg"><span class="truncate pr-2">{{ item }}</span><button @click="removeItem('wikipedia_urls', idx)" class="text-red-500"><IconTrash class="w-4 h-4"/></button></li></ul>
                        </div>
                        <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg">
                            <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase">📎 Local Files</label>
                            <div @click="triggerFileUpload" @dragover="handleDragOver" @dragleave="handleDragLeave" @drop="handleDrop" class="border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center text-gray-400 cursor-pointer transition-all h-24 mt-2" :class="isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'"><IconUpload class="w-6 h-6 mb-1"/><span class="text-xs">Drag & Drop</span></div>
                            <input type="file" ref="fileInput" @change="handleFiles" multiple class="hidden" />
                            <ul class="mt-3 space-y-2 max-h-32 overflow-y-auto custom-scrollbar"><li v-for="(file, idx) in wizardData.files" :key="idx" class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg"><span class="truncate pr-2">{{ file.name }}</span><button @click="removeFile(idx)" class="text-red-500"><IconTrash class="w-4 h-4"/></button></li></ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- STEP 3: Configuration & Prompt -->
            <div v-if="step === 3" class="flex-grow flex flex-col px-2 overflow-y-auto custom-scrollbar">
                <div class="text-center mb-6"><h2 class="text-2xl font-bold text-gray-900 dark:text-white">Configuration</h2></div>

                <!-- SLIDES CONFIG -->
                <div v-if="['slides_making', 'youtube_video'].includes(wizardData.type)" class="mb-6 grid grid-cols-1 md:grid-cols-2 gap-6 bg-white dark:bg-gray-800 p-6 rounded-xl border dark:border-gray-700">
                    <div>
                        <label class="block text-xs font-bold uppercase text-gray-500 mb-2">Target Quantity</label>
                        <div class="flex items-center gap-2">
                             <input type="number" v-model="wizardData.num_slides" min="1" max="50" class="input-field w-24 text-center font-bold" />
                             <span class="text-sm text-gray-500">{{ wizardData.type === 'youtube_video' ? 'Scenes' : 'Slides' }}</span>
                        </div>
                    </div>
                    <div>
                        <label class="block text-xs font-bold uppercase text-gray-500 mb-2">Visual Style</label>
                        <select v-model="wizardData.style_preset" class="input-field w-full">
                            <option v-for="s in stylePresets" :key="s" :value="s">{{ s }}</option>
                        </select>
                        <input v-if="wizardData.style_preset === 'Custom'" v-model="wizardData.custom_style" class="input-field w-full mt-2" placeholder="Describe style (e.g. '8-bit pixel art')" />
                    </div>
                    <div class="md:col-span-2">
                        <label class="block text-xs font-bold uppercase text-gray-500 mb-2">Structure Format</label>
                        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
                            <div v-for="fmt in slideFormats" :key="fmt.id" 
                                 @click="wizardData.slide_format = fmt.id"
                                 class="p-3 border rounded-lg cursor-pointer transition-all hover:bg-gray-50 dark:hover:bg-gray-700"
                                 :class="wizardData.slide_format === fmt.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-200 dark:border-gray-700'">
                                <div class="font-bold text-sm mb-1">{{ fmt.label }}</div>
                                <div class="text-[10px] text-gray-500 leading-tight">{{ fmt.desc }}</div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="flex-grow flex flex-col bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4">
                    <div class="flex justify-between items-center mb-2">
                         <label class="text-xs font-bold uppercase text-gray-500">Instructions for AI</label>
                         <button @click="getSuggestedPrompt" class="text-xs text-blue-600 font-bold hover:underline">✨ Auto-Fill</button>
                    </div>
                    <textarea v-model="wizardData.initialPrompt" class="input-field w-full min-h-[120px] p-4 text-base resize-none leading-relaxed" placeholder="Detailed instructions..."></textarea>
                </div>
            </div>

            <!-- Footer Buttons -->
            <div class="mt-6 pt-4 border-t dark:border-gray-700 flex justify-between items-center flex-shrink-0">
                <button v-if="step > 1" @click="prevStep" class="btn btn-secondary px-5 py-2">← Back</button>
                <div v-else></div>
                <div class="flex gap-3">
                    <button @click="closeModal" class="btn btn-secondary px-5 py-2">Cancel</button>
                    <button v-if="step < 3" @click="nextStep" class="btn btn-primary px-6 py-2" :disabled="step === 1 && !canProceedStep1">Next →</button>
                    <button v-else-if="!isProcessing" @click="createProject" class="btn btn-primary px-8 py-2 font-bold flex items-center gap-2" :disabled="isProcessing || !wizardData.initialPrompt?.trim()">
                        Create Production
                    </button>
                    <div v-else class="flex gap-2">
                        <button class="btn btn-primary px-8 py-2 font-bold flex items-center gap-2" disabled>
                            <IconAnimateSpin class="w-4 h-4 animate-spin"/>
                            Starting Build...
                        </button>
                    </div>
                </div>
            </div>

            <!-- Stop Confirmation Modal -->
            <transition enter-active-class="transition ease-out duration-200" enter-from-class="opacity-0 translate-y-4" enter-to-class="opacity-100 translate-y-0" leave-active-class="transition ease-in duration-150" leave-from-class="opacity-100 translate-y-0" leave-to-class="opacity-0 translate-y-4">
                <div v-if="showStopConfirmation" class="fixed inset-0 z-[100] bg-gray-900/60 backdrop-blur-sm p-6 flex items-center justify-center">
                    <div class="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md p-6 border dark:border-gray-800">
                        <h3 class="text-lg font-bold text-gray-900 dark:text-white mb-4">Stop Creation?</h3>
                        <p class="text-gray-600 dark:text-gray-300 mb-6">
                            This will cancel the process.
                        </p>
                        <div class="flex justify-end gap-3">
                            <button @click="showStopConfirmation = false" class="btn btn-secondary">Go Back</button>
                            <button @click="confirmStopCreation" class="btn btn-warning">Stop</button>
                        </div>
                    </div>
                </div>
            </transition>

        </div>
    </GenericModal>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
.toggle-checkbox:checked { @apply right-0 border-blue-600; }
.toggle-checkbox:checked + .toggle-label { @apply bg-blue-600; }
</style>
