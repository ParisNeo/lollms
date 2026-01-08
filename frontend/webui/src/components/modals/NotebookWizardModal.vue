<script setup>
import { ref, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useNotebookStore } from '../../stores/notebooks';
import GenericModal from './GenericModal.vue';

// Icons
import IconArrowRight from '../../assets/icons/IconArrowRight.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconVideoCamera from '../../assets/icons/IconVideoCamera.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconUpload from '../../assets/icons/IconUpload.vue';

const uiStore = useUiStore();
const notebookStore = useNotebookStore();

const step = ref(1);
const isProcessing = ref(false);
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
    arxiv_queries: [],
    files: [],
    raw_text: ''
});

// UI helpers for inputs
const newUrl = ref('');
const newYoutube = ref('');
const newWiki = ref('');
const newGoogle = ref('');
const newArxiv = ref('');

const projectTypes = [
    { id: 'generic', label: 'General Research', icon: IconFileText, desc: 'A standard notebook for organizing research and notes.' },
    { id: 'slides_making', label: 'Presentation Deck', icon: IconPresentationChartBar, desc: 'Generate slides, visuals, and speaker notes.' },
    { id: 'youtube_video', label: 'Video Production', icon: IconVideoCamera, desc: 'Create scripts, storyboards, and asset lists for video.' },
    { id: 'book_building', label: 'Book / Long-form', icon: IconBookOpen, desc: 'Plan and write structured long-form content.' },
];

// Validation
const canProceedStep1 = computed(() => wizardData.value.title.trim().length > 0);
const canProceedStep2 = computed(() => true); // Sources are optional

const totalSources = computed(() => {
    return (wizardData.value.urls?.length || 0) +
           (wizardData.value.youtube_urls?.length || 0) +
           (wizardData.value.wikipedia_urls?.length || 0) +
           (wizardData.value.google_search_queries?.length || 0) +
           (wizardData.value.arxiv_queries?.length || 0) +
           (wizardData.value.files?.length || 0) +
           (wizardData.value.raw_text?.trim().length > 0 ? 1 : 0);
});

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
    // Reset state after transition
    setTimeout(() => {
        step.value = 1;
        wizardData.value = { 
            title: '', type: 'generic', initialPrompt: '', 
            urls: [], youtube_urls: [], wikipedia_urls: [], 
            google_search_queries: [], arxiv_queries: [], 
            files: [], raw_text: '' 
        };
        isProcessing.value = false;
        newUrl.value = '';
        newYoutube.value = '';
        newWiki.value = '';
        newGoogle.value = '';
        newArxiv.value = '';
    }, 300);
}

// URL validation helper
function isValidUrl(string) {
    try {
        const url = new URL(string);
        return url.protocol === 'http:' || url.protocol === 'https:';
    } catch (_) {
        return false;
    }
}

// Specific Add Handlers with validation
function addUrl() {
    const trimmed = newUrl.value.trim();
    if (!trimmed) return;
    
    if (!isValidUrl(trimmed)) {
        uiStore.addNotification("Please enter a valid URL (starting with http:// or https://)", "error");
        return;
    }
    
    if (!wizardData.value.urls) wizardData.value.urls = [];
    if (wizardData.value.urls.includes(trimmed)) {
        uiStore.addNotification("This URL has already been added", "error");
        return;
    }
    
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

function addArxiv() {
    const trimmed = newArxiv.value.trim();
    if (!trimmed) return;
    if (!wizardData.value.arxiv_queries) wizardData.value.arxiv_queries = [];
    wizardData.value.arxiv_queries.push(trimmed);
    newArxiv.value = '';
}

function addYoutube() {
    const trimmed = newYoutube.value.trim();
    if (!trimmed) return;
    
    if (!trimmed.includes('youtube.com') && !trimmed.includes('youtu.be')) {
        uiStore.addNotification("Please enter a valid YouTube URL", "error");
        return;
    }
    
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

function removeItem(listName, index) {
    wizardData.value[listName].splice(index, 1);
}

function triggerFileUpload() {
    fileInput.value?.click();
}

function handleFiles(event) {
    const files = Array.from(event.target.files || []);
    addFilesToList(files);
    event.target.value = '';
}

function addFilesToList(files) {
    if (!wizardData.value.files) wizardData.value.files = [];
    
    // Check for duplicates
    const existingNames = new Set(wizardData.value.files.map(f => f.name));
    const newFiles = files.filter(f => !existingNames.has(f.name));
    
    if (newFiles.length < files.length) {
        uiStore.addNotification("Some files were already added", "warning");
    }
    
    wizardData.value.files.push(...newFiles);
}

function removeFile(index) {
    wizardData.value.files.splice(index, 1);
}

// Drag and drop handlers
function handleDragOver(event) {
    event.preventDefault();
    isDragging.value = true;
}

function handleDragLeave(event) {
    event.preventDefault();
    isDragging.value = false;
}

function handleDrop(event) {
    event.preventDefault();
    isDragging.value = false;
    
    const files = Array.from(event.dataTransfer.files || []);
    addFilesToList(files);
}

// Get suggested prompts based on project type
function getSuggestedPrompt() {
    const prompts = {
        generic: "Analyze all the sources and create a comprehensive research summary with key findings and insights.",
        slides_making: "Create a detailed outline for a presentation deck with 10-15 slides, including suggested visuals and talking points for each slide.",
        youtube_video: "Develop a complete video script with timestamps, B-roll suggestions, and key talking points based on the research materials.",
        book_building: "Generate a detailed chapter outline with summaries and key points to cover in each section."
    };
    wizardData.value.initialPrompt = prompts[wizardData.value.type] || prompts.generic;
}

async function createProject() {
    if (!wizardData.value.initialPrompt.trim()) {
        uiStore.addNotification("Please provide an initial instruction for the AI", "error");
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
            arxiv_queries: wizardData.value.arxiv_queries || [],
            raw_text: wizardData.value.raw_text
        };

        const newNotebook = await notebookStore.createStructuredNotebook(payload);

        if (wizardData.value.files && wizardData.value.files.length > 0) {
            for (const file of wizardData.value.files) {
                const useDocling = ['.pdf', '.docx', '.pptx'].some(ext => file.name.toLowerCase().endsWith(ext));
                notebookStore.setActiveNotebook(newNotebook);
                await notebookStore.uploadSource(file, useDocling);
            }
        }

        uiStore.addNotification(`"${wizardData.value.title}" created successfully!`, "success");
        closeModal();
        await notebookStore.selectNotebook(newNotebook.id);

    } catch (e) {
        console.error(e);
        uiStore.addNotification("Failed to create project. Please try again.", "error");
    } finally {
        isProcessing.value = false;
    }
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}
</script>

<template>
    <GenericModal modalName="notebookWizard" title="New Production Wizard" maxWidthClass="max-w-5xl" :showCloseButton="true" @close="closeModal">
        <div class="flex flex-col h-full max-h-[85vh]">
            
            <!-- Progress Stepper -->
            <div class="flex items-center justify-center mb-8 flex-shrink-0">
                <div class="flex items-center">
                    <div class="relative">
                        <div class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300" 
                             :class="step >= 1 ? 'bg-blue-600 text-white shadow-lg' : 'bg-gray-200 text-gray-500'">
                            <IconCheckCircle v-if="step > 1" class="w-5 h-5" />
                            <span v-else>1</span>
                        </div>
                        <div class="absolute -bottom-6 left-1/2 transform -translate-x-1/2 text-xs font-medium whitespace-nowrap" :class="step === 1 ? 'text-blue-600' : 'text-gray-500'">
                            Project Setup
                        </div>
                    </div>
                    <div class="w-20 h-1 bg-gray-200 mx-2">
                        <div class="h-full bg-blue-600 transition-all duration-500" :style="{width: step > 1 ? '100%' : '0%'}"></div>
                    </div>
                    <div class="relative">
                        <div class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300" 
                             :class="step >= 2 ? 'bg-blue-600 text-white shadow-lg' : 'bg-gray-200 text-gray-500'">
                            <IconCheckCircle v-if="step > 2" class="w-5 h-5" />
                            <span v-else>2</span>
                        </div>
                        <div class="absolute -bottom-6 left-1/2 transform -translate-x-1/2 text-xs font-medium whitespace-nowrap" :class="step === 2 ? 'text-blue-600' : 'text-gray-500'">
                            Add Sources
                        </div>
                    </div>
                    <div class="w-20 h-1 bg-gray-200 mx-2">
                        <div class="h-full bg-blue-600 transition-all duration-500" :style="{width: step > 2 ? '100%' : '0%'}"></div>
                    </div>
                    <div class="relative">
                        <div class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300" 
                             :class="step >= 3 ? 'bg-blue-600 text-white shadow-lg' : 'bg-gray-200 text-gray-500'">
                            3
                        </div>
                        <div class="absolute -bottom-6 left-1/2 transform -translate-x-1/2 text-xs font-medium whitespace-nowrap" :class="step === 3 ? 'text-blue-600' : 'text-gray-500'">
                            Instructions
                        </div>
                    </div>
                </div>
            </div>

            <!-- STEP 1: Type & Title -->
            <div v-if="step === 1" class="flex-grow overflow-y-auto custom-scrollbar px-2 mt-4">
                <div class="text-center mb-8">
                    <h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">Choose Your Project Type</h2>
                    <p class="text-sm text-gray-500">Select a template that matches your goal</p>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
                    <div v-for="type in projectTypes" :key="type.id" 
                         @click="wizardData.type = type.id"
                         class="group p-6 rounded-xl border-2 cursor-pointer transition-all hover:shadow-lg flex flex-col items-center text-center gap-3"
                         :class="wizardData.type === type.id 
                             ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 shadow-md' 
                             : 'border-gray-200 dark:border-gray-700 hover:border-blue-300'">
                        <component :is="type.icon" 
                                   class="w-12 h-12 transition-transform group-hover:scale-110" 
                                   :class="wizardData.type === type.id ? 'text-blue-600' : 'text-gray-400'" />
                        <div>
                            <h3 class="font-bold text-base text-gray-900 dark:text-white mb-1">{{ type.label }}</h3>
                            <p class="text-xs text-gray-500 leading-relaxed">{{ type.desc }}</p>
                        </div>
                    </div>
                </div>

                <div class="space-y-3 max-w-2xl mx-auto">
                    <label class="block text-sm font-bold text-gray-700 dark:text-gray-300">
                        Project Title <span class="text-red-500">*</span>
                    </label>
                    <input 
                        v-model="wizardData.title" 
                        class="input-field w-full text-lg px-4 py-3 border-2 transition-colors focus:border-blue-500" 
                        placeholder="e.g. 'Mars Exploration History' or 'Q3 Financial Report'"
                        @keyup.enter="canProceedStep1 && nextStep()" />
                    <p class="text-xs text-gray-500 mt-1">
                        <span v-if="!wizardData.title.trim()" class="text-orange-500">⚠️ Title is required to continue</span>
                        <span v-else class="text-green-600">✓ Looking good!</span>
                    </p>
                </div>
            </div>

            <!-- STEP 2: Sources -->
            <div v-if="step === 2" class="flex-grow overflow-y-auto custom-scrollbar px-2">
                <div class="text-center mb-6 flex-shrink-0">
                    <h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">Add Knowledge Sources</h2>
                    <p class="text-sm text-gray-500 mb-1">Ground your content with research materials (optional)</p>
                    <div v-if="totalSources > 0" class="inline-flex items-center px-3 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full text-xs font-medium mt-2">
                        {{ totalSources }} source{{ totalSources !== 1 ? 's' : '' }} added
                    </div>
                </div>

                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- Left Column: Links & Queries -->
                    <div class="space-y-5">
                        <!-- WEB LINKS -->
                        <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg">
                            <div class="flex justify-between items-center mb-3">
                                <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase tracking-wide">🌐 Web Links</label>
                                <span class="text-xs text-gray-500">{{ wizardData.urls?.length || 0 }}</span>
                            </div>
                            <div class="flex gap-2 mb-2">
                                <input v-model="newUrl" @keyup.enter="addUrl" 
                                       class="input-field flex-grow text-sm" 
                                       placeholder="https://example.com/article" />
                                <button @click="addUrl" 
                                        class="btn btn-primary px-3 py-2 flex items-center text-sm whitespace-nowrap">
                                    <IconPlus class="w-4 h-4"/>
                                </button>
                            </div>
                            <ul class="space-y-2 max-h-32 overflow-y-auto custom-scrollbar">
                                <li v-for="(item, idx) in wizardData.urls" :key="idx" 
                                    class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg shadow-sm">
                                    <span class="truncate pr-2 flex-grow">{{ item }}</span>
                                    <button @click="removeItem('urls', idx)" 
                                            class="text-red-500 hover:text-red-700 transition-colors flex-shrink-0">
                                        <IconTrash class="w-4 h-4"/>
                                    </button>
                                </li>
                                <li v-if="!wizardData.urls?.length" class="text-xs text-gray-400 italic text-center py-2">No URLs added yet</li>
                            </ul>
                        </div>

                        <!-- GOOGLE SEARCH -->
                        <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg">
                            <div class="flex justify-between items-center mb-3">
                                <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase tracking-wide">🔍 Google Search</label>
                                <span class="text-xs text-gray-500">{{ wizardData.google_search_queries?.length || 0 }}</span>
                            </div>
                            <div class="flex gap-2 mb-2">
                                <input v-model="newGoogle" @keyup.enter="addGoogle" 
                                       class="input-field flex-grow text-sm" 
                                       placeholder="e.g. 'Latest AI Research 2025'" />
                                <button @click="addGoogle" class="btn btn-primary px-3 py-2">
                                    <IconPlus class="w-4 h-4"/>
                                </button>
                            </div>
                            <ul class="space-y-2 max-h-32 overflow-y-auto custom-scrollbar">
                                <li v-for="(item, idx) in wizardData.google_search_queries" :key="idx" 
                                    class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg shadow-sm">
                                    <span class="truncate pr-2 flex-grow">{{ item }}</span>
                                    <button @click="removeItem('google_search_queries', idx)" 
                                            class="text-red-500 hover:text-red-700 transition-colors">
                                        <IconTrash class="w-4 h-4"/>
                                    </button>
                                </li>
                                <li v-if="!wizardData.google_search_queries?.length" class="text-xs text-gray-400 italic text-center py-2">No searches added yet</li>
                            </ul>
                        </div>

                        <!-- ARXIV SEARCH -->
                        <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg">
                            <div class="flex justify-between items-center mb-3">
                                <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase tracking-wide">📄 Arxiv Papers</label>
                                <span class="text-xs text-gray-500">{{ wizardData.arxiv_queries?.length || 0 }}</span>
                            </div>
                            <div class="flex gap-2 mb-2">
                                <input v-model="newArxiv" @keyup.enter="addArxiv" 
                                       class="input-field flex-grow text-sm" 
                                       placeholder="e.g. 'LLM Agents'" />
                                <button @click="addArxiv" class="btn btn-primary px-3 py-2">
                                    <IconPlus class="w-4 h-4"/>
                                </button>
                            </div>
                            <ul class="space-y-2 max-h-32 overflow-y-auto custom-scrollbar">
                                <li v-for="(item, idx) in wizardData.arxiv_queries" :key="idx" 
                                    class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg shadow-sm">
                                    <span class="truncate pr-2 flex-grow">{{ item }}</span>
                                    <button @click="removeItem('arxiv_queries', idx)" 
                                            class="text-red-500 hover:text-red-700 transition-colors">
                                        <IconTrash class="w-4 h-4"/>
                                    </button>
                                </li>
                                <li v-if="!wizardData.arxiv_queries?.length" class="text-xs text-gray-400 italic text-center py-2">No queries added yet</li>
                            </ul>
                        </div>

                        <!-- YOUTUBE -->
                        <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg">
                            <div class="flex justify-between items-center mb-3">
                                <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase tracking-wide">🎥 YouTube Videos</label>
                                <span class="text-xs text-gray-500">{{ wizardData.youtube_urls?.length || 0 }}</span>
                            </div>
                            <div class="flex gap-2 mb-2">
                                <input v-model="newYoutube" @keyup.enter="addYoutube" 
                                       class="input-field flex-grow text-sm" 
                                       placeholder="https://youtube.com/watch?v=..." />
                                <button @click="addYoutube" class="btn btn-primary px-3 py-2">
                                    <IconPlus class="w-4 h-4"/>
                                </button>
                            </div>
                            <ul class="space-y-2 max-h-32 overflow-y-auto custom-scrollbar">
                                <li v-for="(item, idx) in wizardData.youtube_urls" :key="idx" 
                                    class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg shadow-sm">
                                    <span class="truncate pr-2 flex-grow">{{ item }}</span>
                                    <button @click="removeItem('youtube_urls', idx)" 
                                            class="text-red-500 hover:text-red-700 transition-colors">
                                        <IconTrash class="w-4 h-4"/>
                                    </button>
                                </li>
                                <li v-if="!wizardData.youtube_urls?.length" class="text-xs text-gray-400 italic text-center py-2">No videos added yet</li>
                            </ul>
                        </div>

                        <!-- WIKIPEDIA -->
                        <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg">
                            <div class="flex justify-between items-center mb-3">
                                <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase tracking-wide">📚 Wikipedia Topics</label>
                                <span class="text-xs text-gray-500">{{ wizardData.wikipedia_urls?.length || 0 }}</span>
                            </div>
                            <div class="flex gap-2 mb-2">
                                <input v-model="newWiki" @keyup.enter="addWiki" 
                                       class="input-field flex-grow text-sm" 
                                       placeholder="e.g. 'Quantum Mechanics'" />
                                <button @click="addWiki" class="btn btn-primary px-3 py-2">
                                    <IconPlus class="w-4 h-4"/>
                                </button>
                            </div>
                            <ul class="space-y-2 max-h-32 overflow-y-auto custom-scrollbar">
                                <li v-for="(item, idx) in wizardData.wikipedia_urls" :key="idx" 
                                    class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg shadow-sm">
                                    <span class="truncate pr-2 flex-grow">{{ item }}</span>
                                    <button @click="removeItem('wikipedia_urls', idx)" 
                                            class="text-red-500 hover:text-red-700 transition-colors">
                                        <IconTrash class="w-4 h-4"/>
                                    </button>
                                </li>
                                <li v-if="!wizardData.wikipedia_urls?.length" class="text-xs text-gray-400 italic text-center py-2">No topics added yet</li>
                            </ul>
                        </div>
                    </div>

                    <!-- Right Column: Files & Text -->
                    <div class="space-y-5">
                        <!-- FILES -->
                        <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg">
                            <div class="flex justify-between items-center mb-3">
                                <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase tracking-wide">📎 Local Files</label>
                                <span class="text-xs text-gray-500">{{ wizardData.files?.length || 0 }}</span>
                            </div>
                            <div 
                                @click="triggerFileUpload" 
                                @dragover="handleDragOver"
                                @dragleave="handleDragLeave"
                                @drop="handleDrop"
                                class="border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center text-gray-400 cursor-pointer transition-all h-32"
                                :class="isDragging 
                                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' 
                                    : 'border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700/50'">
                                <IconUpload class="w-8 h-8 mb-2" :class="isDragging ? 'text-blue-500' : ''"/>
                                <span class="text-sm font-medium">{{ isDragging ? 'Drop files here' : 'Click or drag files' }}</span>
                                <span class="text-xs text-gray-400 mt-1">PDF, DOCX, PPTX, TXT, etc.</span>
                            </div>
                            <input type="file" ref="fileInput" @change="handleFiles" multiple class="hidden" />
                            
                            <ul class="mt-3 space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
                                <li v-for="(file, idx) in wizardData.files" :key="idx" 
                                    class="flex justify-between items-center text-xs bg-white dark:bg-gray-700 px-3 py-2 rounded-lg shadow-sm">
                                    <div class="flex-grow truncate pr-2">
                                        <div class="font-medium truncate">{{ file.name }}</div>
                                        <div class="text-gray-400 text-xs">{{ formatFileSize(file.size) }}</div>
                                    </div>
                                    <button @click="removeFile(idx)" 
                                            class="text-red-500 hover:text-red-700 transition-colors flex-shrink-0">
                                        <IconTrash class="w-4 h-4"/>
                                    </button>
                                </li>
                                <li v-if="!wizardData.files?.length" class="text-xs text-gray-400 italic text-center py-2">No files uploaded yet</li>
                            </ul>
                        </div>

                        <!-- RAW TEXT -->
                        <div class="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg flex flex-col" style="min-height: 250px;">
                            <div class="flex justify-between items-center mb-3">
                                <label class="text-xs font-black text-gray-600 dark:text-gray-400 uppercase tracking-wide">✍️ Raw Text / Notes</label>
                                <span class="text-xs text-gray-500">{{ wizardData.raw_text?.length || 0 }} chars</span>
                            </div>
                            <textarea 
                                v-model="wizardData.raw_text" 
                                class="input-field flex-grow resize-none text-sm font-mono leading-relaxed" 
                                placeholder="Paste snippets, research notes, data, or any text content here...

Examples:
• Research findings
• Key statistics
• Interview transcripts
• Meeting notes"></textarea>
                        </div>

                        <!-- Quick Tip -->
                        <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
                            <div class="flex items-start gap-2">
                                <span class="text-blue-600 text-lg">💡</span>
                                <div class="text-xs text-blue-700 dark:text-blue-300">
                                    <strong class="font-bold">Pro tip:</strong> The more quality sources you add, the better the AI can help you. Mix different source types for comprehensive coverage!
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- STEP 3: Initial Prompt -->
            <div v-if="step === 3" class="flex-grow flex flex-col px-2">
                <div class="text-center mb-6">
                    <h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">Set Your Initial Instructions</h2>
                    <p class="text-sm text-gray-500 mb-3">Tell the AI what to do with your sources</p>
                    <button 
                        @click="getSuggestedPrompt" 
                        class="text-xs text-blue-600 hover:text-blue-700 underline font-medium">
                        ✨ Generate suggested prompt for {{ projectTypes.find(t => t.id === wizardData.type)?.label }}
                    </button>
                </div>

                <div class="flex-grow flex flex-col bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4">
                    <textarea 
                        v-model="wizardData.initialPrompt" 
                        class="input-field w-full h-full p-4 text-base resize-none leading-relaxed" 
                        placeholder="Example instructions:

📊 For Research: 'Analyze all sources and create a comprehensive summary with key findings, trends, and actionable insights.'

🎨 For Presentations: 'Create a 10-slide deck outline with talking points, suggested visuals, and speaker notes for each slide.'

🎬 For Videos: 'Write a complete video script with timestamps, B-roll suggestions, and key messages for a 5-minute explainer video.'

📖 For Books: 'Develop a detailed chapter-by-chapter outline with summaries and key points to cover in each section.'

Be specific about:
• Output format you want
• Key points to emphasize
• Target audience
• Tone and style"></textarea>
                </div>

                <!-- Character count and validation -->
                <div class="mt-3 flex justify-between items-center text-xs">
                    <span class="text-gray-500">{{ wizardData.initialPrompt?.length || 0 }} characters</span>
                    <span v-if="!wizardData.initialPrompt?.trim()" class="text-orange-500 font-medium">
                        ⚠️ Instructions required to create project
                    </span>
                    <span v-else class="text-green-600 font-medium">
                        ✓ Ready to create!
                    </span>
                </div>

                <!-- Summary Card -->
                <div class="mt-4 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                    <h4 class="text-sm font-bold text-gray-900 dark:text-white mb-3">📋 Project Summary</h4>
                    <div class="grid grid-cols-2 gap-3 text-xs">
                        <div>
                            <span class="text-gray-500 font-medium">Title:</span>
                            <span class="ml-2 text-gray-900 dark:text-white font-semibold">{{ wizardData.title }}</span>
                        </div>
                        <div>
                            <span class="text-gray-500 font-medium">Type:</span>
                            <span class="ml-2 text-gray-900 dark:text-white font-semibold">{{ projectTypes.find(t => t.id === wizardData.type)?.label }}</span>
                        </div>
                        <div>
                            <span class="text-gray-500 font-medium">Sources:</span>
                            <span class="ml-2 text-gray-900 dark:text-white font-semibold">{{ totalSources }} added</span>
                        </div>
                        <div>
                            <span class="text-gray-500 font-medium">Status:</span>
                            <span class="ml-2 font-semibold" :class="wizardData.initialPrompt?.trim() ? 'text-green-600' : 'text-orange-500'">
                                {{ wizardData.initialPrompt?.trim() ? 'Ready' : 'Pending' }}
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Footer Buttons -->
            <div class="mt-6 pt-4 border-t dark:border-gray-700 flex justify-between items-center flex-shrink-0">
                <button 
                    v-if="step > 1" 
                    @click="prevStep" 
                    class="btn btn-secondary flex items-center px-5 py-2 transition-all hover:bg-gray-200">
                    ← Back
                </button>
                <div v-else></div>

                <div class="flex gap-3">
                    <button 
                        @click="closeModal" 
                        class="btn btn-secondary px-5 py-2 hover:bg-gray-200 transition-all">
                        Cancel
                    </button>
                    
                    <button 
                        v-if="step < 3" 
                        @click="nextStep" 
                        class="btn btn-primary px-6 py-2 flex items-center gap-2 shadow-md hover:shadow-lg transition-all"
                        :disabled="step === 1 && !canProceedStep1"
                        :class="step === 1 && !canProceedStep1 ? 'opacity-50 cursor-not-allowed' : 'hover:bg-blue-700'">
                        <span>Next Step</span>
                        <IconArrowRight class="w-4 h-4" />
                    </button>
                    
                    <button 
                        v-else 
                        @click="createProject" 
                        class="btn btn-primary px-8 py-2 flex items-center gap-2 shadow-lg hover:shadow-xl transition-all font-bold"
                        :disabled="isProcessing || !wizardData.initialPrompt?.trim()"
                        :class="isProcessing || !wizardData.initialPrompt?.trim() ? 'opacity-50 cursor-not-allowed' : 'hover:bg-blue-700 hover:scale-105'">
                        <span v-if="isProcessing" class="flex items-center gap-2">
                            <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Creating...
                        </span>
                        <span v-else class="flex items-center gap-2">
                            Create Project
                            <IconCheckCircle class="w-5 h-5" />
                        </span>
                    </button>
                </div>
            </div>

        </div>
    </GenericModal>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
    background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
    background: rgba(156, 163, 175, 0.5);
    border-radius: 3px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
    background: rgba(107, 114, 128, 0.7);
}
</style>