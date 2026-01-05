<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useNotebookStore } from '../../stores/notebooks';
import { useUiStore } from '../../stores/ui';
import { useTasksStore } from '../../stores/tasks';
import { useAuthStore } from '../../stores/auth'; 
import { storeToRefs } from 'pinia';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import AuthenticatedAudio from '../ui/AuthenticatedAudio.vue';
import AuthenticatedVideo from '../ui/AuthenticatedVideo.vue';
import apiClient from '../../services/api';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';

// Icons
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconMagic from '../../assets/icons/IconMagic.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconSave from '../../assets/icons/IconSave.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconSend from '../../assets/icons/IconSend.vue';
import IconChatBubbleLeftRight from '../../assets/icons/IconChatBubbleLeftRight.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconMicrophone from '../../assets/icons/IconMicrophone.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconFolder from '../../assets/icons/IconFolder.vue';
import IconVideoCamera from '../../assets/icons/IconVideoCamera.vue';
import IconChevronDown from '../../assets/icons/IconChevronDown.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconCode from '../../assets/icons/IconCode.vue';

const props = defineProps({
    notebook: { type: Object, required: true }
});

const notebookStore = useNotebookStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();
const authStore = useAuthStore(); 
const { tasks } = storeToRefs(tasksStore);
const user = computed(() => authStore.user); 

const activeTabIdx = ref(0);
const selectedSlideIdx = ref(0);
const fileInput = ref(null);
const logsContainerRef = ref(null);
const messagesContainerRef = ref(null);

// UI States
const isDiscussionVisible = ref(false);
const slideChatMessage = ref('');
const isSendingMessage = ref(false);
const isAnalyzingImage = ref(false);
const isExporting = ref(false);
const isTaskConsoleExpanded = ref(true);
const viewMode = ref('image'); // 'image' or 'html'

// Prompt Bar State
const aiPrompt = ref('');

// Task Tracking State
const trackedTaskId = ref(null);

// Improved Active Task Lookup
const activeTask = computed(() => {
    // 1. Try finding by ID if we are tracking one
    if (trackedTaskId.value) {
        const t = tasks.value.find(task => task.id === trackedTaskId.value);
        if (t) return t;
    }
    
    // 2. Try finding by name/description
    const t = tasks.value.find(t => 
        (t.name.includes(props.notebook.title) || t.description.includes(props.notebook.id)) && 
        (t.status === 'running' || t.status === 'pending')
    );
    
    // If found a new task via name match, track it for robustness
    if (t && t.id !== trackedTaskId.value) {
        trackedTaskId.value = t.id;
    }
    
    return t;
});

// Watch task status to clear tracked ID when done
watch(activeTask, (newTask) => {
    if (newTask && (newTask.status === 'completed' || newTask.status === 'failed')) {
        // Delay clearing to allow UI to show success state for a moment
        setTimeout(() => {
            if (trackedTaskId.value === newTask.id) {
                trackedTaskId.value = null;
            }
        }, 2000);
    }
});

// Artefact and Editor state
const selectedArtefactNames = ref([]);
const editingArtefact = ref(null);

// WIZARD STATE
const isWizardOpen = ref(false);
const wizardStep = ref(1); 
const isBrainstorming = ref(false);
const wizardData = ref({ topic: '', title: '', layout: 'TitleImageBody', bullets: [], image_prompt: '', selected_artefacts: [], author: '' }); 

// GENERATION MODAL STATE
const isGenModalOpen = ref(false);
const genModalMode = ref('images'); 
const genPrompt = ref('');
const isEnhancing = ref(false);

// DICTATION STATE
const isRecording = ref(false);
let recognition = null;

const languages = [
    { code: 'en', name: 'English' }, { code: 'fr', name: 'French' }, { code: 'es', name: 'Spanish' }, { code: 'de', name: 'German' }, { code: 'it', name: 'Italian' }, { code: 'pt', name: 'Portuguese' }, { code: 'zh', name: 'Chinese' }, { code: 'ja', name: 'Japanese' }, { code: 'ru', name: 'Russian' }, { code: 'ar', name: 'Arabic' }
];

const slidesTabs = computed(() => (props.notebook.tabs || []).filter(t => t.type === 'slides'));
const currentTab = computed(() => slidesTabs.value[activeTabIdx.value]);

const slideData = computed(() => {
    if (!currentTab.value || !currentTab.value.content) return { slides_data: [], mode: 'hybrid', summary: '' };
    try { return JSON.parse(currentTab.value.content); } catch (e) { return { slides_data: [], mode: 'hybrid', summary: '' }; }
});

const currentSlide = computed(() => slideData.value.slides_data[selectedSlideIdx.value] || null);

const currentImage = computed(() => {
    if (!currentSlide.value || !currentSlide.value.images || currentSlide.value.images.length === 0) return null;
    return currentSlide.value.images[currentSlide.value.selected_image_index] || currentSlide.value.images[0];
});

// HTML Graphic Source
const currentHtmlSrc = computed(() => {
    if (!currentSlide.value?.html_content) return null;
    const blob = new Blob([currentSlide.value.html_content], { type: 'text/html' });
    return URL.createObjectURL(blob);
});

// Auto-switch view mode when HTML content arrives
watch(() => currentSlide.value?.html_content, (newVal) => {
    if (newVal) viewMode.value = 'html';
});

const isSummaryGenerating = computed(() => activeTask.value && activeTask.value.name.includes("Summary"));
const isNotesGenerating = computed(() => activeTask.value && activeTask.value.name === 'AI Task: generate_notes');
const isTitleGenerating = computed(() => activeTask.value && activeTask.value.name === 'AI Task: generate_slide_title');
const isAudioGenerating = computed(() => activeTask.value && activeTask.value.name === 'AI Task: generate_audio');

const layoutOptions = [
    { value: 'TitleImageBody', label: 'Standard (Text + Image)', desc: 'Split screen with content and visual.' },
    { value: 'ImageOnly', label: 'Big Visual (Image only)', desc: 'High-impact full-screen image focus.' },
    { value: 'TextOnly', label: 'Bullet Points (Text only)', desc: 'Detailed factual information layout.' },
    { value: 'TitleOnly', label: 'Hero / Title', desc: 'Minimalist title for section breaks.' },
    { value: 'TwoColumn', label: 'Comparison / Dual', desc: 'Two columns for contrast or comparison.' }
];

// FIXED: Safety check for scrollHeight
watch(() => activeTask.value?.logs?.length, () => {
    nextTick(() => {
        if (logsContainerRef.value) {
            logsContainerRef.value.scrollTop = logsContainerRef.value.scrollHeight;
        }
    });
});

watch(() => currentSlide.value?.messages?.length, () => {
    nextTick(() => {
        if (messagesContainerRef.value) {
            messagesContainerRef.value.scrollTop = messagesContainerRef.value.scrollHeight;
        }
    });
});

async function updateContent(newObj) {
    if (!currentTab.value) return;
    const tabIdxInFullList = props.notebook.tabs.findIndex(t => t.id === currentTab.value.id);
    if (tabIdxInFullList === -1) return;
    props.notebook.tabs[tabIdxInFullList].content = JSON.stringify(newObj);
    await notebookStore.saveActive();
}

async function handleLanguageChange(newLang) {
    props.notebook.language = newLang;
    await notebookStore.saveActive();
}

async function handleAutoTitle() { await notebookStore.generateTitle(); }

async function handleProcess() {
    const p = (aiPrompt.value || '').trim();
    if (!p || !currentTab.value) return;
    
    // Default processing for slides: Refine or add content
    await notebookStore.processWithAi(p, [], 'generate_slides_text', currentTab.value.id, false, selectedArtefactNames.value);
    aiPrompt.value = '';
}

async function analyzeVariant(variant) {
    if (isAnalyzingImage.value) return;
    isAnalyzingImage.value = true;
    try {
        const filename = variant.path.split('/').pop();
        const description = await notebookStore.describeAsset(filename);
        const { confirmed } = await uiStore.showConfirmation({ title: 'Image Analysis', message: `The AI described this image as: "${description}". Use this as the slide prompt?`, confirmText: 'Update' });
        if (confirmed) await updateSlideField('image_prompt', description);
    } finally { isAnalyzingImage.value = false; }
}

async function sendSlideChat() {
    const msg = (slideChatMessage.value || '').trim();
    if (!msg || isSendingMessage.value) return;
    isSendingMessage.value = true;
    try {
        await notebookStore.sendSlideMessage(currentTab.value.id, currentSlide.value.id, msg, selectedArtefactNames.value);
        slideChatMessage.value = '';
    } finally { isSendingMessage.value = false; }
}

function toggleArtefact(name) {
    const idx = selectedArtefactNames.value.indexOf(name);
    if (idx === -1) selectedArtefactNames.value.push(name);
    else selectedArtefactNames.value.splice(idx, 1);
}

function openArtefactEditor(art) {
    editingArtefact.value = { originalName: art.filename, name: art.filename, content: art.content };
}

function viewArtefact(art) {
    uiStore.openModal('artefactViewer', { 
        artefact: { 
            title: art.filename, 
            content: art.content 
        } 
    });
}

async function deleteArtefact(filename) {
    await notebookStore.deleteArtefact(filename);
}

async function saveArtefactEdit() {
    if (!editingArtefact.value) return;
    try {
        await notebookStore.updateArtefact(editingArtefact.value.originalName, editingArtefact.value.name, editingArtefact.value.content);
        editingArtefact.value = null;
    } catch (e) { console.error(e); }
}

const isResearchActive = computed(() => selectedArtefactNames.value.length > 0);

function openWizard() {
    wizardData.value = { topic: '', title: '', layout: 'TitleImageBody', bullets: [], image_prompt: '', selected_artefacts: [...selectedArtefactNames.value], author: user.value ? user.value.username : '' };
    wizardStep.value = 1; isWizardOpen.value = true;
}

function toggleWizardArtefact(name) {
    const idx = wizardData.value.selected_artefacts.indexOf(name);
    if (idx === -1) wizardData.value.selected_artefacts.push(name);
    else wizardData.value.selected_artefacts.splice(idx, 1);
}

async function brainstormSlide() {
    const topic = (wizardData.value.topic || '').trim();
    if (!topic) return;
    isBrainstorming.value = true;
    try {
        const res = await notebookStore.brainstormSlide(topic, wizardData.value.layout, wizardData.value.selected_artefacts, wizardData.value.author);
        Object.assign(wizardData.value, res);
        wizardStep.value = 3;
    } finally { isBrainstorming.value = false; }
}

async function finalizeAddSlide() {
    isWizardOpen.value = false;
    await notebookStore.processWithAi(JSON.stringify(wizardData.value), [], 'add_full_slide', currentTab.value.id, false, wizardData.value.selected_artefacts);
}

function openImportWizard() {
    uiStore.openModal('artefactImportWizard', { notebookId: props.notebook.id });
}

function openGenModal(mode) {
    if (!currentSlide.value) return;
    genModalMode.value = mode;
    if (mode === 'refine_image') genPrompt.value = currentSlide.value.last_edit_prompt || currentSlide.value.image_prompt || '';
    else genPrompt.value = currentSlide.value.last_prompt || currentSlide.value.image_prompt || '';
    isGenModalOpen.value = true;
}

async function enhanceGenPrompt() {
    const p = (genPrompt.value || '').trim();
    if (!p) return;
    isEnhancing.value = true;
    try {
        const enhanced = await notebookStore.enhancePrompt(p, isResearchActive.value ? `Using ${selectedArtefactNames.value.length} selected artefacts.` : "");
        genPrompt.value = enhanced;
    } finally { isEnhancing.value = false; }
}

async function submitGenModal() {
    const p = (genPrompt.value || '').trim();
    if (!p) return;
    const newData = { ...slideData.value };
    if (genModalMode.value === 'refine_image') newData.slides_data[selectedSlideIdx.value].last_edit_prompt = p;
    else newData.slides_data[selectedSlideIdx.value].last_prompt = p;
    await updateContent(newData);
    await notebookStore.processWithAi(`SLIDE_INDEX:${selectedSlideIdx.value}| ${p}`, [], genModalMode.value, currentTab.value.id, false, selectedArtefactNames.value);
    isGenModalOpen.value = false;
}

async function handleGenerateSummary() { await notebookStore.generateSummary(); }
async function selectVariant(index) { const newData = { ...slideData.value }; newData.slides_data[selectedSlideIdx.value].selected_image_index = index; await updateContent(newData); }
async function deleteVariant(index) {
    const confirmed = await uiStore.showConfirmation({ title: 'Delete Variant', message: 'Remove image?', confirmText: 'Delete' });
    if (confirmed.confirmed) {
        const newData = { ...slideData.value }; newData.slides_data[selectedSlideIdx.value].images.splice(index, 1);
        if (newData.slides_data[selectedSlideIdx.value].selected_image_index >= newData.slides_data[selectedSlideIdx.value].images.length) newData.slides_data[selectedSlideIdx.value].selected_image_index = Math.max(0, newData.slides_data[selectedSlideIdx.value].images.length - 1);
        await updateContent(newData);
    }
}
async function updateSlideField(field, value) { const newData = { ...slideData.value }; newData.slides_data[selectedSlideIdx.value][field] = value; await updateContent(newData); }
async function playSlideshow() { const deck = slideData.value.slides_data.map(s => ({ src: s.images?.[s.selected_image_index || 0]?.path || '', title: s.title })).filter(s => !!s.src); if (deck.length === 0) return; uiStore.openSlideshow({ slides: deck, title: props.notebook.title, startIndex: selectedSlideIdx.value }); }

function triggerImport() { fileInput.value?.click(); }
async function handleFileUpload(e) {
    const file = e.target.files[0]; if (!file) return;
    try {
        const res = await notebookStore.uploadSource(file, false);
        const path = `/api/notebooks/${props.notebook.id}/assets/${res.filename}`;
        const newData = { ...slideData.value };
        const slide = newData.slides_data[selectedSlideIdx.value];
        if (!slide.images) slide.images = [];
        slide.images.push({ path, prompt: 'Manual Import', created_at: Date.now().toString() });
        slide.selected_image_index = slide.images.length - 1;
        await updateContent(newData);
    } catch (err) {}
    e.target.value = '';
}

function toggleDictation(field) {
    if (isRecording.value) { if (recognition) recognition.stop(); isRecording.value = false; return; }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) { uiStore.addNotification("Speech recognition not supported.", "error"); return; }
    recognition = new SpeechRecognition();
    recognition.lang = props.notebook.language === 'zh' ? 'zh-CN' : (props.notebook.language || 'en-US');
    recognition.continuous = true;
    recognition.onstart = () => { isRecording.value = true; };
    recognition.onresult = (event) => {
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                const transcript = (event.results[i][0].transcript || '').trim();
                if (transcript) {
                    const currentText = currentSlide.value[field] || '';
                    updateSlideField(field, currentText + (currentText ? ' ' : '') + transcript);
                }
            }
        }
    };
    recognition.start();
}

function viewImage(index) { if (!currentSlide.value?.images) return; const images = currentSlide.value.images.map(img => ({ src: img.path, prompt: img.prompt || 'Variant' })); uiStore.openImageViewer({ imageList: images, startIndex: index }); }

async function downloadImage(image) {
    if (!image?.path) return;
    try {
        const response = await apiClient.get(image.path, { responseType: 'blob' });
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', image.path.split('/').pop() || 'image.png');
        document.body.appendChild(link);
        link.click(); document.body.removeChild(link);
    } catch (error) { uiStore.addNotification('Download failed.', 'error'); }
}

async function handleExport(format) {
    isExporting.value = true;
    try {
        const response = await apiClient.get(`/api/notebooks/${props.notebook.id}/export`, { params: { format }, responseType: 'blob' });
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a'); link.href = url;
        link.setAttribute('download', `${props.notebook.title || 'presentation'}.${format}`);
        document.body.appendChild(link); link.click(); document.body.removeChild(link);
    } finally { isExporting.value = false; }
}

async function handleGenerateVideo() {
    const { confirmed } = await uiStore.showConfirmation({ title: 'Generate Video', message: 'Render video using slide images and TTS voice-over?', confirmText: 'Generate' });
    if (confirmed) { try { await apiClient.post(`/api/notebooks/${props.notebook.id}/generate_video`); } catch (e) { uiStore.addNotification('Failed to start.', 'error'); } }
}

async function handleDeleteVideo() {
    const { confirmed } = await uiStore.showConfirmation({ title: 'Delete Video?', message: 'This action cannot be undone.', confirmText: 'Delete' });
    if (confirmed) await notebookStore.deleteGeneratedAsset('video', currentTab.value.id);
}

async function handleAutoNotes() {
    const { confirmed, value } = await uiStore.showConfirmation({ title: 'Generate Notes', message: 'AI will analyze slide context to write a script. Instructions:', confirmText: 'Generate', inputType: 'text' });
    if (confirmed) await notebookStore.generateSlideNotes(selectedSlideIdx.value, value || "", currentTab.value.id);
}

async function handleGenerateSlideTitle() { await notebookStore.generateSlideTitle(selectedSlideIdx.value, "", currentTab.value.id); }
async function handleGenerateAudio() { await notebookStore.generateSlideAudio(selectedSlideIdx.value, currentTab.value.id); }
async function handleDeleteAudio() {
    const { confirmed } = await uiStore.showConfirmation({ title: 'Delete Audio?', message: 'Remove generated voice-over?', confirmText: 'Delete' });
    if (confirmed) await notebookStore.deleteGeneratedAsset('audio', currentTab.value.id, currentSlide.value.id);
}

// NEW: Trigger HTML generation
async function handleGenerateHtml() {
    const { confirmed, value } = await uiStore.showConfirmation({ 
        title: 'Generate Graphic', 
        message: 'Create an HTML/SVG graphic for this slide. Describe the desired visual (e.g., "A bar chart showing growth"):', 
        confirmText: 'Generate', 
        inputType: 'text' 
    });
    if (confirmed) {
        await notebookStore.processWithAi(`SLIDE_INDEX:${selectedSlideIdx.value}| ${value || 'Create a relevant visual'}`, [], 'generate_slide_html', currentTab.value.id, false, selectedArtefactNames.value);
    }
}

onUnmounted(() => { if (recognition && isRecording.value) recognition.stop(); });
</script>

<template>
    <div class="flex flex-col h-full overflow-hidden bg-gray-100 dark:bg-gray-950 relative">
        
        <!-- PRODUCTION CONSOLE OVERLAY -->
        <transition enter-active-class="transition ease-out duration-300" enter-from-class="opacity-0" enter-to-class="opacity-100" leave-active-class="transition ease-in duration-200" leave-from-class="opacity-100" leave-to-class="opacity-0">
            <div v-if="activeTask" class="absolute inset-0 z-50 bg-white/95 dark:bg-gray-900/95 backdrop-blur-md flex flex-col p-10">
                <div class="max-w-4xl mx-auto w-full flex flex-col h-full animate-in fade-in zoom-in-95 duration-500">
                    <div class="flex items-center justify-between mb-8">
                        <div class="flex items-center gap-6">
                            <div class="p-4 bg-blue-600 rounded-3xl shadow-xl shadow-blue-500/20">
                                <IconAnimateSpin class="w-10 h-10 animate-spin text-white"/>
                            </div>
                            <div>
                                <h2 class="text-2xl font-black text-gray-900 dark:text-white uppercase tracking-tighter">{{ activeTask.name }}</h2>
                                <p class="text-sm font-bold text-blue-500 opacity-80 uppercase tracking-widest">{{ activeTask.description }}</p>
                            </div>
                        </div>
                        <div class="text-4xl font-black text-blue-600 font-mono">{{ activeTask.progress }}%</div>
                    </div>
                    
                    <div class="w-full bg-gray-200 dark:bg-gray-800 h-3 rounded-full overflow-hidden mb-10 shadow-inner">
                        <div class="h-full bg-blue-600 transition-all duration-500 progress-bar-animated" :style="{width: activeTask.progress + '%'}"></div>
                    </div>

                    <div class="flex-grow flex flex-col min-h-0 bg-black rounded-3xl shadow-2xl border border-gray-800 overflow-hidden">
                        <div class="px-6 py-3 bg-gray-900 border-b border-gray-800 flex items-center justify-between">
                            <span class="text-[10px] font-black uppercase text-gray-500 tracking-widest">Presentation Production Terminal</span>
                            <div class="flex gap-1.5">
                                <div class="w-2 h-2 rounded-full bg-red-500/50"></div>
                                <div class="w-2 h-2 rounded-full bg-yellow-500/50"></div>
                                <div class="w-2 h-2 rounded-full bg-green-500/50"></div>
                            </div>
                        </div>
                        <div ref="logsContainerRef" class="flex-grow overflow-y-auto p-6 font-mono text-xs text-gray-400 space-y-1.5 custom-scrollbar">
                            <div v-for="(log, i) in activeTask.logs" :key="i" class="flex gap-4">
                                <span class="text-gray-700 shrink-0 select-none">[{{ new Date(log.timestamp).toLocaleTimeString() }}]</span> 
                                <span :class="{'text-red-400 font-bold': log.level === 'ERROR', 'text-blue-400': log.level === 'INFO', 'text-yellow-400': log.level === 'WARNING'}">{{ log.message }}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </transition>

        <!-- HEADER FUSED INTO GLOBAL HEADER -->
        <Teleport to="#global-header-title-target">
            <div class="flex flex-col items-center">
                <div class="flex items-center gap-2 group cursor-pointer" @click="handleAutoTitle" title="Click to auto-title">
                    <span class="text-sm font-bold text-gray-800 dark:text-gray-100">{{ notebook.title }}</span>
                    <IconSparkles class="w-3 h-3 text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <div class="flex items-center gap-2 text-[10px] text-gray-500 dark:text-gray-400">
                    <IconPresentationChartBar class="w-3 h-3" />
                    <span class="uppercase tracking-wide font-medium">{{ currentTab?.title }}</span>
                </div>
            </div>
        </Teleport>

        <Teleport to="#global-header-actions-target">
            <div class="flex items-center gap-1">
                <div class="relative group/lang mr-2">
                    <select :value="notebook.language" @change="handleLanguageChange($event.target.value)" 
                            class="bg-gray-100 dark:bg-gray-800 border-none rounded-lg text-[10px] font-black uppercase tracking-widest px-2 py-1 outline-none cursor-pointer focus:ring-1 ring-blue-500 transition-all">
                        <option v-for="l in languages" :key="l.code" :value="l.code">{{ l.code }}</option>
                    </select>
                </div>
                <button @click="handleExport('pptx')" class="btn-icon-flat text-orange-600" title="Export PPTX"><IconPresentationChartBar class="w-4 h-4" /></button>
                <button @click="handleExport('pdf')" class="btn-icon-flat text-red-600" title="Export PDF"><IconFileText class="w-4 h-4" /></button>
                <button @click="handleExport('zip')" class="btn-icon-flat text-blue-600" title="Export ZIP"><IconFolder class="w-4 h-4" /></button>
                <button @click="handleGenerateVideo" class="btn-icon-flat text-pink-500" title="Gen Video"><IconVideoCamera class="w-4 h-4" /></button>
                <div class="w-px h-4 bg-gray-300 dark:bg-gray-700 mx-1"></div>
                <button @click="handleGenerateSummary" class="btn-icon-flat" title="Summary" :disabled="isSummaryGenerating"><IconSparkles class="w-4 h-4 text-purple-500" /></button>
                <button @click="isDiscussionVisible = !isDiscussionVisible" class="btn-icon-flat relative" :class="{'bg-blue-50 dark:bg-blue-900/20 text-blue-500': isDiscussionVisible}"><IconChatBubbleLeftRight class="w-4 h-4" /></button>
                <button @click="playSlideshow" class="btn-primary-flat"><IconPresentationChartBar class="w-4 h-4" /><span class="hidden sm:inline ml-1">Play</span></button>
            </div>
        </Teleport>

        <!-- MAIN VIEWPORT SWITCHER -->
        <div class="flex-grow flex flex-col md:flex-row overflow-hidden relative">
            
            <!-- EMPTY STATE -->
            <div v-if="!currentSlide" class="flex-grow flex items-center justify-center text-center">
                <div class="max-w-xs animate-in fade-in zoom-in duration-700">
                    <IconPresentationChartBar class="w-16 h-16 mx-auto mb-4 text-gray-300 opacity-20" />
                    <p class="text-sm text-gray-400 font-bold uppercase tracking-widest mb-6">Empty Presentation Deck</p>
                    <button @click="openWizard" class="btn btn-secondary w-full rounded-2xl border-2 shadow-lg hover:shadow-blue-500/10 transition-all">
                        <IconPlus class="w-4 h-4 mr-2" /> Initialize Studio
                    </button>
                </div>
            </div>

            <!-- WORKSPACE (IF SLIDES EXIST) -->
            <template v-else>
                <!-- SIDEBAR -->
                <div class="w-full md:w-64 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col flex-shrink-0">
                    <div class="p-3 text-[10px] font-black uppercase text-gray-400 tracking-tighter border-b dark:border-gray-800 flex justify-between items-center">
                        <span>Slides</span>
                        <div class="flex gap-1">
                            <button @click="handleGenerateSummary" class="p-1 text-purple-500 hover:bg-purple-50 rounded" title="Update Summary"><IconSparkles class="w-4 h-4"/></button>
                            <button @click="openWizard" class="p-1 text-blue-500 hover:bg-blue-50 rounded" title="Add Slide"><IconPlus class="w-4 h-4" /></button>
                        </div>
                    </div>
                    <div class="flex-grow overflow-y-auto custom-scrollbar p-3 space-y-3 max-h-[50%] border-b dark:border-gray-800 bg-gray-50 dark:bg-gray-950">
                        <button v-for="(slide, idx) in slideData.slides_data" :key="slide.id" @click="selectedSlideIdx = idx" 
                            class="w-full relative rounded-xl overflow-hidden border-2 transition-all block p-0 aspect-video"
                            :class="selectedSlideIdx === idx ? 'border-blue-500 ring-2 ring-blue-500/20' : 'border-transparent hover:border-gray-300'">
                            <AuthenticatedImage v-if="slide.images?.length" :src="slide.images[slide.selected_image_index || 0].path" img-class="object-cover" class="w-full h-full" />
                            <div v-else class="w-full h-full bg-gray-200 dark:bg-gray-800 flex items-center justify-center text-gray-400"><IconPhoto class="w-8 h-8 opacity-20" /></div>
                            <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-80"></div>
                            <div class="absolute bottom-1 left-2 right-2 text-left pointer-events-none"><p class="text-white text-[10px] font-black truncate uppercase tracking-tighter">{{ slide.title }}</p></div>
                            <div class="absolute top-1 left-1 bg-black/50 text-white text-[8px] px-1.5 py-0.5 rounded font-mono">{{ idx + 1 }}</div>
                        </button>
                    </div>
                    <!-- ARTEFACTS -->
                    <div class="p-3 text-[10px] font-black uppercase text-gray-400 tracking-tighter border-b dark:border-gray-800 flex justify-between items-center">
                        <span>Artefacts</span>
                        <button @click="openImportWizard" class="p-1 text-green-500 hover:bg-green-50 rounded"><IconPlus class="w-3 h-3" /></button>
                    </div>
                    <div v-for="art in notebook.artefacts" :key="art.filename" 
                         @click="toggleArtefact(art.filename)"
                         class="flex items-center gap-2 p-2 rounded-lg text-[10px] cursor-pointer group"
                         :class="selectedArtefactNames.includes(art.filename) ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 font-bold' : 'text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800'">
                        <IconCheckCircle v-if="selectedArtefactNames.includes(art.filename)" class="w-3 h-3 flex-shrink-0 text-green-500" />
                        <IconFileText v-else class="w-3 h-3 flex-shrink-0 opacity-50" />
                        <span class="truncate flex-grow">{{ art.filename }}</span>
                        
                        <!-- Actions -->
                        <div class="flex items-center opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 bg-white/50 dark:bg-black/50 rounded px-1 backdrop-blur-sm">
                            <button @click.stop="viewArtefact(art)" class="p-1 hover:text-blue-500" title="View"><IconEye class="w-3 h-3" /></button>
                            <button @click.stop="openArtefactEditor(art)" class="p-1 hover:text-orange-500" title="Edit"><IconPencil class="w-3 h-3" /></button>
                            <button @click.stop="deleteArtefact(art.filename)" class="p-1 hover:text-red-500" title="Delete"><IconTrash class="w-3 h-3" /></button>
                        </div>
                    </div>
                </div>

                <!-- EDITOR -->
                <div class="flex-grow overflow-y-auto custom-scrollbar p-6 bg-gray-50/50 dark:bg-gray-950 relative">
                    <div class="max-w-6xl mx-auto space-y-6 pb-20">
                        <div v-if="slideData.video_src" class="relative group/video">
                            <AuthenticatedVideo :src="slideData.video_src" />
                            <button @click="handleDeleteVideo" class="absolute top-4 right-4 btn btn-danger btn-sm opacity-0 group-hover/video:opacity-100 transition-opacity z-10 shadow-xl"><IconTrash class="w-4 h-4 mr-1"/> Delete Video</button>
                        </div>

                        <div class="bg-white dark:bg-gray-900 p-4 rounded-xl shadow-sm border dark:border-gray-800 flex items-center gap-3">
                            <div class="flex-grow"><label class="text-[10px] font-black uppercase text-gray-400 block mb-1">Slide Title</label><input :value="currentSlide.title" @change="updateSlideField('title', $event.target.value)" class="text-xl md:text-2xl font-bold bg-transparent border-none outline-none w-full text-gray-900 dark:text-white" /></div>
                            <button @click="handleGenerateSlideTitle" class="btn btn-secondary btn-sm h-10 w-10 p-0 rounded-full" :disabled="isTitleGenerating"><IconAnimateSpin v-if="isTitleGenerating" class="w-5 h-5 animate-spin" /><IconSparkles v-else class="w-5 h-5 text-blue-500" /></button>
                        </div>
                        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            <div class="lg:col-span-2 aspect-video bg-black rounded-2xl relative group overflow-hidden shadow-lg border dark:border-gray-800">
                                <div class="absolute top-3 left-3 z-10 flex gap-1">
                                    <button @click="viewMode = 'image'" class="px-2 py-1 text-[10px] font-bold rounded uppercase transition-colors" :class="viewMode === 'image' ? 'bg-white text-black' : 'bg-black/50 text-white hover:bg-black/80'">Image</button>
                                    <button v-if="currentSlide.html_content" @click="viewMode = 'html'" class="px-2 py-1 text-[10px] font-bold rounded uppercase transition-colors" :class="viewMode === 'html' ? 'bg-white text-black' : 'bg-black/50 text-white hover:bg-black/80'">Graphic</button>
                                </div>

                                <template v-if="viewMode === 'html' && currentSlide.html_content">
                                    <iframe :src="currentHtmlSrc" class="w-full h-full border-none bg-white"></iframe>
                                </template>
                                <template v-else>
                                    <AuthenticatedImage v-if="currentImage" :src="currentImage.path" img-class="object-contain" class="w-full h-full" />
                                    <div v-else class="w-full h-full bg-gray-200 dark:bg-gray-800 flex items-center justify-center text-gray-400"><IconPhoto class="w-8 h-8 opacity-20" /></div>
                                </template>

                                <div class="absolute top-3 right-3 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button @click="handleGenerateHtml" class="p-2 bg-black/60 rounded-lg text-white hover:bg-blue-600" title="Generate Graphic"><IconCode class="w-4 h-4" /></button>
                                    <button @click="openGenModal('refine_image')" class="p-2 bg-black/60 rounded-lg text-white hover:bg-purple-600" title="Edit Image"><IconMagic class="w-4 h-4" /></button>
                                    <button @click="openGenModal('images')" class="p-2 bg-black/60 rounded-lg text-white hover:bg-green-600" title="New Variant"><IconRefresh class="w-4 h-4" /></button>
                                </div>
                                <div class="absolute bottom-3 left-3 bg-black/60 text-white text-[10px] px-2 py-1 rounded-full font-mono pointer-events-none">{{ currentSlide.layout }}</div>
                            </div>
                            <div class="bg-white dark:bg-gray-900 rounded-2xl p-5 border dark:border-gray-800 shadow-sm flex flex-col">
                                <h3 class="text-xs font-black uppercase text-gray-400 mb-4">Slide Content</h3>
                                <div class="flex-grow space-y-4 overflow-y-auto max-h-[300px] custom-scrollbar pr-2">
                                    <div v-for="(bullet, bIdx) in (currentSlide.bullets || [])" :key="bIdx" class="flex items-start gap-2"><span class="text-lg font-bold text-blue-500 mt-0.5">•</span><textarea :value="bullet" @change="updateSlideField('bullets', currentSlide.bullets.map((b, i) => i === bIdx ? $event.target.value : b))" class="flex-grow bg-transparent border-b border-dashed border-gray-200 dark:border-gray-700 outline-none text-sm resize-none"></textarea></div>
                                    <button @click="updateSlideField('bullets', [...(currentSlide.bullets || []), ''])" class="flex items-center gap-2 text-xs font-bold text-blue-500 mt-2"><IconPlus class="w-3 h-3" /> Add Point</button>
                                </div>
                            </div>
                        </div>
                        <div class="bg-white dark:bg-gray-900 rounded-2xl p-5 border dark:border-gray-800 shadow-sm relative group/notes">
                            <div class="flex items-center justify-between mb-2">
                                <div class="flex items-center gap-2">
                                    <h3 class="text-xs font-black uppercase tracking-widest text-gray-400">Speaker Notes</h3>
                                    <button @click="toggleDictation('notes')" class="p-1 rounded-full transition-all" :class="isRecording ? 'text-red-600 bg-red-100' : 'text-blue-500'"><IconMicrophone class="w-4 h-4" /></button>
                                </div>
                                <div class="flex items-center gap-2">
                                    <button @click="handleGenerateAudio" class="btn btn-secondary btn-sm" :disabled="isAudioGenerating">Audio</button>
                                    <button @click="handleAutoNotes" class="btn btn-secondary btn-sm" :disabled="isNotesGenerating">Generate Text</button>
                                </div>
                            </div>
                            <textarea :value="currentSlide.notes" @change="updateSlideField('notes', $event.target.value)" class="input-field w-full h-24 resize-none text-sm mb-2" placeholder="Presenter script..."></textarea>
                            <div v-if="currentSlide.audio_src" class="mt-2 bg-gray-100 dark:bg-gray-800 rounded p-2 flex items-center gap-2"><AuthenticatedAudio :src="currentSlide.audio_src" /><button @click="handleDeleteAudio" class="text-red-500 p-1 flex-shrink-0"><IconTrash class="w-4 h-4" /></button></div>
                        </div>
                    </div>
                </div>
            </template>
        </div>

        <!-- DISCUSSION PANEL -->
        <transition enter-active-class="transition ease-out duration-300" enter-from-class="translate-x-full" enter-to-class="translate-x-0" leave-active-class="transition ease-in duration-200" leave-from-class="translate-x-0" leave-to-class="translate-x-full">
            <div v-if="isDiscussionVisible" class="absolute top-0 right-0 h-full w-80 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 shadow-2xl z-50 flex flex-col">
                <div class="p-4 border-b dark:border-gray-800 flex justify-between items-center bg-gray-50 dark:bg-gray-800/50"><div class="flex items-center gap-2"><IconChatBubbleLeftRight class="w-4 h-4 text-blue-500" /><h3 class="font-black text-xs uppercase tracking-widest">Intelligence</h3></div><button @click="isDiscussionVisible = false" class="btn-icon-flat"><IconXMark class="w-5 h-5"/></button></div>
                <div class="flex-grow overflow-y-auto p-4 space-y-4 custom-scrollbar" ref="messagesContainerRef">
                    <div v-for="(msg, mIdx) in currentSlide?.messages" :key="mIdx" class="flex flex-col gap-1" :class="{'items-end': msg.role === 'user'}">
                        <div class="p-3 rounded-2xl text-xs max-w-[90%]" :class="msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300'">
                            <MessageContentRenderer :content="msg.content" />
                        </div>
                    </div>
                    <div v-if="isSendingMessage" class="flex flex-col gap-1">
                            <div class="p-3 rounded-2xl text-xs max-w-[90%] bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">
                                <div class="flex items-center gap-2">
                                    <IconAnimateSpin class="w-4 h-4 animate-spin text-blue-500" />
                                    <span>Thinking...</span>
                                </div>
                            </div>
                    </div>
                </div>
                <div class="p-4 border-t dark:border-gray-800 flex gap-2">
                    <textarea v-model="slideChatMessage" @keyup.enter.exact="sendSlideChat" class="input-field w-full text-xs h-20 resize-none" placeholder="Ask AI..." :disabled="isSendingMessage"></textarea>
                    <button @click="sendSlideChat" class="btn btn-primary h-20" :disabled="isSendingMessage">
                        <IconAnimateSpin v-if="isSendingMessage" class="w-4 h-4 animate-spin"/>
                        <IconSend v-else class="w-4 h-4"/>
                    </button>
                </div>
            </div>
        </transition>

        <!-- GLOBAL OVERLAYS (ROOT LEVEL) -->
        <transition enter-active-class="transition ease-out duration-200" enter-from-class="opacity-0 translate-y-4" enter-to-class="opacity-100 translate-y-0" leave-active-class="transition ease-in duration-150" leave-from-class="opacity-100 translate-y-0" leave-to-class="opacity-0 translate-y-4">
            <div v-if="isWizardOpen" class="fixed inset-0 z-[100] bg-gray-900/60 backdrop-blur-sm p-6 flex items-center justify-center" @click.self="isWizardOpen = false">
                <div class="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-3xl flex flex-col overflow-hidden border dark:border-gray-800">
                    <div class="p-4 border-b dark:border-gray-800 flex justify-between items-center bg-gray-50 dark:bg-gray-800/50"><h3 class="font-black text-sm uppercase tracking-widest flex items-center gap-2"><IconPlus class="w-4 h-4" /> New Slide</h3><button @click="isWizardOpen = false" class="btn-icon-flat"><IconXMark class="w-5 h-5"/></button></div>
                    <div class="p-8 overflow-y-auto custom-scrollbar min-h-[450px]">
                        <div v-if="wizardStep === 1" class="space-y-6">
                            <div><label class="text-[10px] font-black uppercase text-blue-500 mb-2 block tracking-widest">1. Topic</label><textarea v-model="wizardData.topic" class="input-field w-full h-24 font-bold text-lg" placeholder="Slide topic..."></textarea></div>
                            <div><label class="text-[10px] font-black uppercase text-blue-500 mb-2 block tracking-widest">Author (Optional)</label><input v-model="wizardData.author" class="input-field w-full" placeholder="Author Name" /></div>
                            <div><label class="text-[10px] font-black uppercase text-gray-500 mb-2 block tracking-widest">2. Context Sources</label><div class="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto p-2 border rounded-xl dark:border-gray-800">
                                <button v-for="art in notebook.artefacts" :key="art.filename" @click="toggleWizardArtefact(art.filename)" class="p-2 rounded-lg text-[10px] flex items-center gap-2 text-left transition-all border" :class="wizardData.selected_artefacts.includes(art.filename) ? 'bg-green-50 border-green-500 text-green-700' : 'border-transparent hover:bg-gray-50 text-gray-500'"><IconCheckCircle v-if="wizardData.selected_artefacts.includes(art.filename)" class="w-3 h-3 flex-shrink-0" /><IconFileText v-else class="w-3 h-3 opacity-30 flex-shrink-0" /><span class="truncate">{{ art.filename }}</span></button>
                            </div></div>
                        </div>
                        <div v-if="wizardStep === 2" class="space-y-6"><label class="text-[10px] font-black uppercase text-blue-500 mb-4 block tracking-widest">3. Architecture</label><div class="grid grid-cols-3 gap-4"><button v-for="opt in layoutOptions" :key="opt.value" @click="wizardData.layout = opt.value" class="p-4 rounded-xl border-2 transition-all text-left flex flex-col gap-3" :class="wizardData.layout === opt.value ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-100 dark:border-gray-800'"><p class="text-xs font-black truncate">{{ opt.label }}</p></button></div></div>
                        <div v-if="wizardStep === 3" class="space-y-4"><div><label class="text-[10px] font-black text-gray-500 mb-1 block">Title</label><input v-model="wizardData.title" class="input-field w-full font-bold" /></div><div v-if="wizardData.layout !== 'TextOnly'"><label class="text-[10px] font-black text-gray-500 mb-1 block">Visual Strategy</label><textarea v-model="wizardData.image_prompt" class="input-field w-full h-20 text-xs italic resize-none"></textarea></div></div>
                    </div>
                    <div class="p-4 border-t dark:border-gray-800 flex justify-between gap-3 bg-gray-50 dark:bg-gray-900/50"><button v-if="wizardStep > 1" @click="wizardStep--" class="btn btn-secondary">Back</button><div v-else></div><div class="flex gap-2"><button @click="isWizardOpen = false" class="btn btn-secondary">Cancel</button><button v-if="wizardStep === 1" @click="wizardStep = 2" class="btn btn-primary" :disabled="!wizardData.topic">Next</button><button v-if="wizardStep === 2" @click="brainstormSlide" class="btn btn-primary" :disabled="isBrainstorming"><IconAnimateSpin v-if="isBrainstorming" class="w-4 h-4 mr-2 animate-spin" />Brainstorm</button><button v-if="wizardStep === 3" @click="finalizeAddSlide" class="btn btn-primary">Add</button></div></div>
                </div>
            </div>
        </transition>

        <!-- ARTEFACT EDITOR MODAL -->
        <transition enter-active-class="transition ease-out duration-200" enter-from-class="opacity-0 translate-y-4" enter-to-class="opacity-100 translate-y-0" leave-active-class="transition ease-in duration-150" leave-from-class="opacity-100 translate-y-0" leave-to-class="opacity-0 translate-y-4">
            <div v-if="editingArtefact" class="fixed inset-0 z-[100] bg-gray-900/60 backdrop-blur-sm p-6 flex items-center justify-center">
                <div class="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-4xl h-full max-h-[80vh] flex flex-col overflow-hidden border dark:border-gray-800">
                    <div class="p-4 border-b dark:border-gray-800 flex justify-between items-center bg-gray-50 dark:bg-gray-800/50"><h3 class="font-black text-sm uppercase tracking-widest">Edit Source</h3><button @click="editingArtefact = null" class="btn-icon-flat"><IconXMark class="w-5 h-5"/></button></div>
                    <div class="flex-grow p-6 flex flex-col gap-4 overflow-hidden">
                        <div><label class="text-[10px] font-bold uppercase text-gray-500 mb-1 block">Title</label><input v-model="editingArtefact.name" class="input-field w-full font-bold" /></div>
                        <div class="flex-grow flex flex-col"><label class="text-[10px] font-bold uppercase text-gray-500 mb-1 block">Content</label><textarea v-model="editingArtefact.content" class="flex-grow input-field w-full font-mono text-xs resize-none"></textarea></div>
                    </div>
                    <div class="p-4 border-t dark:border-gray-800 flex justify-end gap-3"><button @click="editingArtefact = null" class="btn btn-secondary">Cancel</button><button @click="saveArtefactEdit" class="btn btn-primary"><IconSave class="w-4 h-4 mr-2" /> Save</button></div>
                </div>
            </div>
        </transition>

        <!-- IMAGE GEN MODAL -->
        <transition enter-active-class="transition ease-out duration-200" enter-from-class="opacity-0 translate-y-4" enter-to-class="opacity-100 translate-y-0" leave-active-class="transition ease-in duration-150" leave-from-class="opacity-100 translate-y-0" leave-to-class="opacity-0 translate-y-4">
            <div v-if="isGenModalOpen" class="fixed inset-0 z-[100] bg-gray-900/60 backdrop-blur-sm p-6 flex items-center justify-center" @click.self="isGenModalOpen = false">
                <div class="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden border dark:border-gray-800 flex flex-col">
                    <div class="p-4 border-b dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50 flex justify-between items-center"><h3 class="font-black text-sm uppercase tracking-widest text-blue-600">{{ genModalMode === 'refine_image' ? 'Refine Image' : 'New Variant' }}</h3><button @click="isGenModalOpen = false" class="btn-icon-flat"><IconXMark class="w-5 h-5"/></button></div>
                    <div class="p-6 space-y-4">
                        <div><label class="text-[10px] font-bold uppercase text-gray-500 mb-1 block">Prompt</label><textarea v-model="genPrompt" class="input-field w-full h-32 resize-none" placeholder="Describe the image..."></textarea></div>
                        <div class="flex items-center justify-between"><div class="flex items-center gap-2"><span class="text-xs font-bold text-gray-500">Research Context:</span><span v-if="isResearchActive" class="px-2 py-0.5 bg-green-100 text-green-700 rounded text-[10px] font-bold">{{ selectedArtefactNames.length }} Active</span><span v-else class="text-[10px] text-gray-400 italic">None selected</span></div><button @click="enhanceGenPrompt" class="btn btn-secondary btn-sm" :disabled="isEnhancing || !(genPrompt || '').trim()"><IconSparkles class="w-3 h-3 mr-1" /> Enhance Prompt</button></div>
                    </div>
                    <div class="p-4 border-t dark:border-gray-800 flex justify-end gap-2 bg-gray-50 dark:bg-gray-900/50"><button @click="isGenModalOpen = false" class="btn btn-secondary">Cancel</button><button @click="submitGenModal" class="btn btn-primary" :disabled="!(genPrompt || '').trim()">Generate</button></div>
                </div>
            </div>
        </transition>

        <!-- FOOTER PROMPT -->
        <div class="p-4 border-t dark:border-gray-800 bg-white dark:bg-gray-900 flex gap-4 shadow-2xl z-20">
            <input v-model="aiPrompt" @keyup.enter="handleProcess" placeholder="Describe additional slides or deck refinements..." class="input-field flex-grow h-12 rounded-2xl" />
            <button @click="handleProcess" class="btn btn-primary px-8 h-12 rounded-2xl" :disabled="!(aiPrompt || '').trim() || activeTask">
                <IconSparkles class="w-4 h-4 mr-2"/> Go
            </button>
        </div>
    </div>
</template>

<style scoped>
.progress-bar-animated {
  background-image: linear-gradient(45deg, rgba(255, 255, 255, .15) 25%, transparent 25%, transparent 50%, rgba(255, 255, 255, .15) 50%, rgba(255, 255, 255, .15) 75%, transparent 75%, transparent);
  background-size: 1rem 1rem;
  animation: progress-animation 1s linear infinite;
}
@keyframes progress-animation { from { background-position: 1rem 0; } to { background-position: 0 0; } }
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>
