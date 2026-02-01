<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { useUiStore } from '../../stores/ui';
import { useNotebookStore } from '../../stores/notebooks';
import { useTasksStore } from '../../stores/tasks';
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
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconArrowRight from '../../assets/icons/IconArrowRight.vue';

const router = useRouter(); 
const uiStore = useUiStore();
const notebookStore = useNotebookStore();
const tasksStore = useTasksStore();

const currentStep = ref(1);
const isCreating = ref(false);
const fileInput = ref(null);
const isDragging = ref(false);

// Track the building task
const buildingTaskId = ref(null);
const buildingNotebookId = ref(null);
const generatingTabId = ref(null);

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
    custom_style: '',
    delay_processing: false
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

const canProceedToGenerate = computed(() => {
    const hasSources = 
        wizardData.value.urls.length > 0 ||
        wizardData.value.youtube_urls.length > 0 ||
        wizardData.value.wikipedia_urls.length > 0 ||
        wizardData.value.google_search_queries.length > 0 ||
        wizardData.value.arxiv_selected.length > 0 ||
        wizardData.value.files.length > 0 ||
        wizardData.value.raw_text?.trim();
    return hasSources;
});

const validationMessage = computed(() => {
    const hasSources = 
        wizardData.value.urls.length > 0 ||
        wizardData.value.youtube_urls.length > 0 ||
        wizardData.value.wikipedia_urls.length > 0 ||
        wizardData.value.google_search_queries.length > 0 ||
        wizardData.value.arxiv_selected.length > 0 ||
        wizardData.value.files.length > 0 ||
        wizardData.value.raw_text?.trim();

    if (!hasSources) {
        return "Please add at least one source before creating the notebook.";
    }
    return null;
});

// Get the current building task
const buildingTask = computed(() => {
    if (!buildingTaskId.value) return null;
    return tasksStore.tasks.find(t => t.id === buildingTaskId.value);
});

const isBuilding = computed(() => {
    const task = buildingTask.value;
    return task && (task.status === 'running' || task.status === 'pending');
});

const buildingProgress = computed(() => {
    return buildingTask.value?.progress || 0;
});

const buildingLogs = computed(() => {
    return buildingTask.value?.logs || [];
});

function closeModal() {
    uiStore.closeModal('notebookWizard');
    resetWizard();
}

function resetWizard() {
    setTimeout(() => {
        currentStep.value = 1;
        wizardData.value = { 
            title: '', type: 'generic', initialPrompt: '', 
            urls: [], youtube_urls: [], wikipedia_urls: [], 
            google_search_queries: [], arxiv_selected: [], 
            files: [], raw_text: '',
            num_slides: 10, slide_format: 'TitleImageBody', style_preset: 'Corporate Vector', custom_style: '',
            delay_processing: false
        };
        isCreating.value = false;
        buildingTaskId.value = null;
        buildingNotebookId.value = null;
        generatingTabId.value = null;
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
        arxivResults.value = results.map(r => ({ ...r, selected: false, ingest_full: true }));
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

async function handleCreateNotebook() {
    isCreating.value = true;

    try {
        const payload = {
            title: wizardData.value.title,
            type: wizardData.value.type,
            initialPrompt: "", 
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
            delay_processing: true 
        };

        // 1. Create the notebook with empty tabs
        const newNotebook = await notebookStore.createStructuredNotebook(payload);
        buildingNotebookId.value = newNotebook.id;
        notebookStore.setActiveNotebook(newNotebook);

        // 2. Upload Files
        if (wizardData.value.files?.length > 0) {
            for (const file of wizardData.value.files) {
                const useDocling = ['.pdf', '.docx', '.pptx'].some(ext => file.name.toLowerCase().endsWith(ext));
                await notebookStore.uploadSource(file, useDocling);
            }
        }

        // 3. Trigger Generation if a prompt is provided
        const prompt = wizardData.value.initialPrompt?.trim();
        if (prompt && !wizardData.value.delay_processing) {
            // Always create a new tab for generation - the "Update Active" logic is removed
            // We create a "Generating..." tab first, then the backend will replace it or we update it
            
            // Create a temporary "Generating" tab
            const generatingTab = await notebookStore.addTab('markdown');
            generatingTab.title = "Generating...";
            generatingTab.content = `<!-- GENERATING_PLACEHOLDER_${Date.now()} -->`;
            generatingTabId.value = generatingTab.id;
            await notebookStore.saveActive();

            const taskResult = await notebookStore.importSources(newNotebook.id, {
                ...payload,
                initialPrompt: prompt, 
                target_tab_id: generatingTab.id // Always target the new generating tab
            });

            // Track the building task
            if (taskResult && taskResult.id) {
                buildingTaskId.value = taskResult.id;
            }
        }

        uiStore.addNotification(`"${wizardData.value.title}" created!`, "success");
        
        // Navigate to notebook studio
        await router.push(`/notebooks/${newNotebook.id}`);
        
        // Don't close modal immediately if building, let user see progress in the modal
        if (!buildingTaskId.value) {
            closeModal();
        }

    } catch (e) {
        console.error(e);
        uiStore.addNotification("Failed to start project.", "error");
    } finally {
        isCreating.value = false;
    }
}

async function stopBuilding() {
    if (!buildingTaskId.value) return;
    
    try {
        await tasksStore.cancelTask(buildingTaskId.value);
        uiStore.addNotification("Building stopped. Showing partial results.", "info");
    } catch (e) {
        console.error("Failed to stop task:", e);
    }
    
    // Refresh notebook to show partial results
    if (buildingNotebookId.value) {
        await notebookStore.selectNotebook(buildingNotebookId.value);
    }
    
    closeModal();
}

// Watch for task completion
watch(buildingTask, async (newTask, oldTask) => {
    if (!newTask) return;
    
    console.log(`[NotebookWizard] Task status changed: ${newTask.status}`);
    
    // Task finished successfully
    if (newTask.status === 'completed') {
        uiStore.addNotification("Notebook building complete!", "success");
        
        // Refresh to show final results
        if (buildingNotebookId.value) {
            await notebookStore.selectNotebook(buildingNotebookId.value);
        }
        
        // Small delay to let user see completion
        setTimeout(() => {
            closeModal();
        }, 500);
    }
    
    // Task failed or was cancelled
    if (newTask.status === 'failed' || newTask.status === 'cancelled') {
        // Refresh to show partial results
        if (buildingNotebookId.value) {
            await notebookStore.selectNotebook(buildingNotebookId.value);
        }
        
        setTimeout(() => {
            closeModal();
        }, 500);
    }
}, { immediate: true, deep: true });

// Also watch the tasks array directly for any updates
watch(() => tasksStore.tasks, (newTasks) => {
    if (!buildingTaskId.value) return;
    
    const task = newTasks.find(t => t.id === buildingTaskId.value);
    if (task && ['completed', 'failed', 'cancelled'].includes(task.status)) {
        console.log(`[NotebookWizard] Detected task completion via tasks array: ${task.status}`);
        // The watch on buildingTask should handle this, but force a check
        if (buildingNotebookId.value) {
            notebookStore.selectNotebook(buildingNotebookId.value);
        }
    }
}, { deep: true });
</script>

<template>
    <GenericModal modalName="notebookWizard" title="New Production Wizard" maxWidthClass="max-w-6xl" :showCloseButton="!isBuilding" @close="closeModal">
        <div class="flex flex-col h-full max-h-[85vh]">
            
            <!-- BUILDING PROGRESS OVERLAY (when task is running) -->
            <div v-if="isBuilding" class="flex flex-col h-full p-4">
                <!-- Header -->
                <div class="flex items-center justify-between mb-6 p-4 bg-gradient-to-r from-blue-600 to-indigo-700 rounded-xl text-white shadow-lg">
                    <div class="flex items-center gap-4">
                        <div class="p-3 bg-white/20 rounded-xl">
                            <IconAnimateSpin class="w-8 h-8 animate-spin" />
                        </div>
                        <div>
                            <h2 class="text-xl font-black uppercase tracking-tight">{{ wizardData.title }}</h2>
                            <p class="text-sm font-medium opacity-80">Generating in new tab...</p>
                        </div>
                    </div>
                    <div class="text-right">
                        <div class="text-4xl font-black font-mono">{{ buildingProgress }}%</div>
                    </div>
                </div>

                <!-- Progress Bar -->
                <div class="w-full bg-gray-200 dark:bg-gray-800 h-4 rounded-full overflow-hidden mb-6 shadow-inner">
                    <div class="h-full bg-gradient-to-r from-blue-500 to-indigo-600 transition-all duration-500 progress-bar-animated" 
                         :style="{ width: buildingProgress + '%' }"></div>
                </div>

                <!-- Logs Console -->
                <div class="flex-grow bg-black rounded-2xl overflow-hidden flex flex-col shadow-2xl border border-gray-800">
                    <div class="px-4 py-3 bg-gray-900 border-b border-gray-800 flex items-center justify-between">
                        <span class="text-[10px] font-black uppercase text-gray-500 tracking-widest">Build Log</span>
                        <div class="flex gap-1.5">
                            <div class="w-2 h-2 rounded-full bg-red-500/50"></div>
                            <div class="w-2 h-2 rounded-full bg-yellow-500/50"></div>
                            <div class="w-2 h-2 rounded-full bg-green-500/50"></div>
                        </div>
                    </div>
                    <div class="flex-grow overflow-y-auto p-4 font-mono text-xs space-y-1 custom-scrollbar">
                        <div v-for="(log, i) in buildingLogs" :key="i" class="flex gap-3">
                            <span class="text-gray-600 shrink-0">[{{ new Date(log.timestamp).toLocaleTimeString() }}]</span>
                            <span :class="{
                                'text-red-400 font-bold': log.level === 'ERROR',
                                'text-yellow-400': log.level === 'WARNING',
                                'text-blue-400': log.level === 'INFO',
                                'text-green-400': log.level === 'SUCCESS'
                            }">{{ log.message }}</span>
                        </div>
                        <div v-if="buildingLogs.length === 0" class="text-gray-600 italic">Initializing...</div>
                    </div>
                </div>

                <!-- Stop Button -->
                <div class="flex justify-center mt-6">
                    <button 
                        @click="stopBuilding" 
                        class="btn btn-danger px-8 py-3 flex items-center gap-3 text-base font-bold shadow-xl"
                    >
                        <IconStopCircle class="w-5 h-5" />
                        Stop Generation
                    </button>
                </div>
            </div>

            <!-- NORMAL WIZARD FLOW -->
            <template v-else>
                <!-- Progress Stepper -->
                <div class="flex items-center justify-center mb-8 flex-shrink-0">
                    <div class="flex items-center">
                        <div class="relative"><div class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300" :class="currentStep >= 1 ? 'bg-blue-600 text-white shadow-lg' : 'bg-gray-200 text-gray-500'"><IconCheckCircle v-if="currentStep > 1" class="w-5 h-5" /><span v-else>1</span></div></div>
                        <div class="w-20 h-1 bg-gray-200 mx-2"><div class="h-full bg-blue-600 transition-all duration-500" :style="{width: currentStep > 1 ? '100%' : '0%'}"></div></div>
                        <div class="relative"><div class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300" :class="currentStep >= 2 ? 'bg-blue-600 text-white shadow-lg' : 'bg-gray-200 text-gray-500'"><IconCheckCircle v-if="currentStep > 2" class="w-5 h-5" /><span v-else>2</span></div></div>
                        <div class="w-20 h-1 bg-gray-200 mx-2"><div class="h-full bg-blue-600 transition-all duration-500" :style="{width: currentStep > 2 ? '100%' : '0%'}"></div></div>
                        <div class="relative"><div class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300" :class="currentStep >= 3 ? 'bg-blue-600 text-white shadow-lg' : 'bg-gray-200 text-gray-500'">3</div></div>
                    </div>
                </div>

                <!-- STEP 1: Type & Title -->
                <div v-if="currentStep === 1" class="flex-grow overflow-y-auto custom-scrollbar px-2 mt-4">
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
                        <input v-model="wizardData.title" class="input-field w-full text-lg px-4 py-3 border-2 transition-colors focus:border-blue-500" placeholder="e.g. 'Project Mars'" @keyup.enter="canProceedStep1 && (currentStep++)" />
                    </div>
                </div>

                <!-- STEP 2: Sources -->
                <div v-if="currentStep === 2" class="flex-grow overflow-y-auto custom-scrollbar px-2">
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
                                                <span class="text-[10px] font-bold uppercase" :class="res.ingest_full ? 'text-blue-600' : 'text-gray-400'">{{ res.ingest_full ? 'Full PDF' : 'Abstract Only' }}</span>
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
                                            <span class="truncate pr-2 font-medium">{{ item.title }} <span v-if="item.ingest_full" class="text-[9px] bg-blue-200 text-blue-800 px-1 rounded ml-1">PDF</span><span v-else class="text-[9px] bg-gray-200 text-gray-600 px-1 rounded ml-1">Abstract</span></span>
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

                            <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg border dark:border-gray-700">
                                <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase">📝 Raw Text / Notes</label>
                                <textarea v-model="wizardData.raw_text" class="input-field w-full h-32 mt-2 p-3 text-xs resize-none" placeholder="Paste or type additional context here..."></textarea>
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
                <div v-if="currentStep === 3" class="flex-grow flex flex-col px-2 overflow-y-auto custom-scrollbar">
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
                             <label class="text-xs font-bold uppercase text-gray-500">Instructions for AI (Optional)</label>
                             <button @click="getSuggestedPrompt" class="text-xs text-blue-600 font-bold hover:underline">✨ Auto-Fill</button>
                        </div>
                        <textarea v-model="wizardData.initialPrompt" class="input-field w-full min-h-[120px] p-4 text-base resize-none leading-relaxed" placeholder="Detailed instructions..."></textarea>
                        <p class="text-[10px] text-gray-400 mt-2 italic">Leave empty to just create a notebook with the selected materials.</p>
                    </div>
                </div>

                <!-- Footer Buttons -->
                <div class="p-4 border-t dark:border-gray-800 flex justify-between gap-3 bg-gray-50 dark:bg-gray-900/50">
                    <button v-if="currentStep > 1" @click="currentStep--" class="btn btn-secondary">Back</button>
                    <div v-else></div>
                    
                    <div class="flex items-center gap-3">
                        <p v-if="validationMessage && currentStep === 3" class="text-xs text-red-500 italic">
                            {{ validationMessage }}
                        </p>
                        <button @click="closeModal" class="btn btn-secondary">Cancel</button>
                        <button 
                            v-if="currentStep < 3" 
                            @click="currentStep++" 
                            class="btn btn-primary"
                            :disabled="currentStep === 1 && !canProceedStep1"
                        >
                            Next
                        </button>
                        <button 
                            v-else 
                            @click="handleCreateNotebook" 
                            class="btn btn-primary"
                            :disabled="!canProceedToGenerate || isCreating"
                        >
                            <IconAnimateSpin v-if="isCreating" class="w-4 h-4 mr-2 animate-spin" />
                            {{ wizardData.initialPrompt?.trim() ? 'Create & Generate' : 'Create Empty Notebook' }}
                        </button>
                    </div>
                </div>
            </template>
        </div>
    </GenericModal>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
.toggle-checkbox:checked { @apply right-0 border-blue-600; }
.toggle-checkbox:checked + .toggle-label { @apply bg-blue-600; }

@keyframes progress-bar-stripes {
    from { background-position: 1rem 0; }
    to { background-position: 0 0; }
}
.progress-bar-animated {
    background-image: linear-gradient(45deg, rgba(255, 255, 255, .15) 25%, transparent 25%, transparent 50%, rgba(255, 255, 255, .15) 50%, rgba(255, 255, 255, .15) 75%, transparent 75%, transparent);
    background-size: 1rem 1rem;
    animation: progress-bar-stripes 1s linear infinite;
}
</style>
