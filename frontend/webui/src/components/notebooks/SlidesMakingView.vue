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
import IconChevronLeft from '../../assets/icons/IconChevronLeft.vue';
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
const aiPrompt = ref('');
const trackedTaskId = ref(null);

// Improved Active Task Lookup
const activeTask = computed(() => {
    if (trackedTaskId.value) {
        const t = tasks.value.find(task => task.id === trackedTaskId.value);
        if (t) return t;
    }
    const t = tasks.value.find(t => 
        (t.name.includes(props.notebook.title) || t.description.includes(props.notebook.id)) && 
        (t.status === 'running' || t.status === 'pending')
    );
    if (t && t.id !== trackedTaskId.value) trackedTaskId.value = t.id;
    return t;
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
const genNegativePrompt = ref('text, words, blurry, deformed, low quality, watermark');
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
    const idx = currentSlide.value.selected_image_index || 0;
    return currentSlide.value.images[idx] || currentSlide.value.images[0];
});

const currentHtmlSrc = computed(() => {
    if (!currentSlide.value?.html_content) return null;
    const blob = new Blob([currentSlide.value.html_content], { type: 'text/html' });
    return URL.createObjectURL(blob);
});

watch(() => currentSlide.value?.html_content, (newVal) => { if (newVal) viewMode.value = 'html'; });

const isSummaryGenerating = computed(() => activeTask.value && activeTask.value.name.includes("Summary"));
const isNotesGenerating = computed(() => activeTask.value && activeTask.value.name === 'AI Task: generate_notes');
const isTitleGenerating = computed(() => activeTask.value && activeTask.value.name === 'AI Task: generate_slide_title');
const isAudioGenerating = computed(() => activeTask.value && activeTask.value.name === 'AI Task: generate_audio');

const layoutOptions = [
    { value: 'TitleImageBody', label: 'Standard Hybrid', desc: 'Split screen content.' },
    { value: 'ImageOnly', label: 'Impact Visual', desc: 'Full image focus.' },
    { value: 'TextOnly', label: 'Factual List', desc: 'Bullet points only.' },
    { value: 'TitleOnly', label: 'Section Hero', desc: 'Minimalist break.' },
    { value: 'TwoColumn', label: 'Comparison', desc: 'Dual column content.' }
];

watch(() => activeTask.value?.logs?.length, () => {
    nextTick(() => { if (logsContainerRef.value) logsContainerRef.value.scrollTop = logsContainerRef.value.scrollHeight; });
});

watch(() => currentSlide.value?.messages?.length, () => {
    nextTick(() => { if (messagesContainerRef.value) messagesContainerRef.value.scrollTop = messagesContainerRef.value.scrollHeight; });
});


function viewArtefact(art) {
    uiStore.openModal('artefactViewer', {
        artefact: {
            title: art.filename,
            content: art.content
        }
    });
}

async function updateContent(newObj) {
    if (!currentTab.value) return;
    const tabIdxInFullList = props.notebook.tabs.findIndex(t => t.id === currentTab.value.id);
    if (tabIdxInFullList === -1) return;
    props.notebook.tabs[tabIdxInFullList].content = JSON.stringify(newObj);
    await notebookStore.saveActive();
}

async function updateSlideField(field, value) {
    if (!currentSlide.value) return;
    const newData = { ...slideData.value };
    newData.slides_data[selectedSlideIdx.value][field] = value;
    await updateContent(newData);
}

async function handleLanguageChange(newLang) {
    props.notebook.language = newLang;
    await notebookStore.saveActive();
}

async function handleAutoTitle() { await notebookStore.generateTitle(); }

async function handleProcess() {
    const p = (aiPrompt.value || '').trim();
    if (!p || !currentTab.value) return;
    await notebookStore.processWithAi(p, [], 'generate_slides_text', currentTab.value.id, false, selectedArtefactNames.value);
    aiPrompt.value = '';
}

async function analyzeVariant(variant) {
    if (isAnalyzingImage.value) return;
    isAnalyzingImage.value = true;
    try {
        const filename = variant.path.split('/').pop();
        const description = await notebookStore.describeAsset(filename);
        const { confirmed } = await uiStore.showConfirmation({ title: 'Image Analysis', message: `AI description: "${description}". Update slide prompt?`, confirmText: 'Update' });
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


async function deleteArtefact(filename) { await notebookStore.deleteArtefact(filename); }

async function saveArtefactEdit() {
    if (!editingArtefact.value) return;
    try {
        await notebookStore.updateArtefact(editingArtefact.value.originalName, editingArtefact.value.name, editingArtefact.value.content);
        editingArtefact.value = null;
    } catch (e) { console.error(e); }
}

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

function openImportWizard() { uiStore.openModal('artefactImportWizard', { notebookId: props.notebook.id }); }

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
        const enhanced = await notebookStore.enhancePrompt(p, selectedArtefactNames.value.length ? `Using ${selectedArtefactNames.value.length} selected artefacts.` : "");
        genPrompt.value = enhanced;
    } finally { isEnhancing.value = false; }
}

async function submitGenModal() {
    const p = (genPrompt.value || '').trim();
    const np = (genNegativePrompt.value || '').trim();
    if (!p) return;
    const newData = { ...slideData.value };
    if (genModalMode.value === 'refine_image') newData.slides_data[selectedSlideIdx.value].last_edit_prompt = p;
    else newData.slides_data[selectedSlideIdx.value].last_prompt = p;
    newData.slides_data[selectedSlideIdx.value].negative_prompt = np;
    await updateContent(newData);
    await notebookStore.processWithAi(`SLIDE_INDEX:${selectedSlideIdx.value}|${p}|${np}`, [], genModalMode.value, currentTab.value.id, false, selectedArtefactNames.value);
    isGenModalOpen.value = false;
}

async function handleGenerateSummary() { await notebookStore.generateSummary(); }
async function selectVariant(index) { updateSlideField('selected_image_index', index); }

async function deleteVariant(index) {
    const confirmed = await uiStore.showConfirmation({ title: 'Delete Variant', message: 'Remove image version?', confirmText: 'Delete' });
    if (confirmed) await notebookStore.deleteSlideImage(currentTab.value.id, currentSlide.value.id, index);
}

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

async function handleGenerateSlideTitle() { await notebookStore.generateSlideTitle(selectedSlideIdx.value, "", currentTab.value.id); }
async function handleGenerateAudio() { await notebookStore.generateSlideAudio(selectedSlideIdx.value, currentTab.value.id); }
async function handleDeleteAudio() {
    const { confirmed } = await uiStore.showConfirmation({ title: 'Delete Audio?', message: 'Remove generated voice-over?', confirmText: 'Delete' });
    if (confirmed) await notebookStore.deleteGeneratedAsset('audio', currentTab.value.id, currentSlide.value.id);
}

async function handleGenerateHtml() {
    const { confirmed, value } = await uiStore.showConfirmation({ title: 'Generate Graphic', message: 'Create an HTML/SVG graphic for this slide:', confirmText: 'Generate', inputType: 'text' });
    if (confirmed) await notebookStore.processWithAi(`SLIDE_INDEX:${selectedSlideIdx.value}| ${value || 'Create visual'}`, [], 'generate_slide_html', currentTab.value.id, false, selectedArtefactNames.value);
}

// --- MISSING FUNCTIONS ADDED BELOW ---

async function handleAutoNotes() {
    await notebookStore.generateSlideNotes(selectedSlideIdx.value, "", currentTab.value.id);
}

function navImage(dir) {
    if (!currentSlide.value?.images?.length) return;
    const total = currentSlide.value.images.length;
    const current = currentSlide.value.selected_image_index || 0;
    const next = (current + dir + total) % total;
    updateSlideField('selected_image_index', next);
}

function playSlideshow() {
    if (!slideData.value.slides_data || slideData.value.slides_data.length === 0) {
        uiStore.addNotification("No slides to play.", "warning");
        return;
    }

    const slides = slideData.value.slides_data.map(s => ({
        src: s.images?.length ? s.images[s.selected_image_index || 0].path : null,
        prompt: s.title || 'Untitled Slide',
        id: s.id,
        notes: s.notes,
        audio_src: s.audio_src,
        html_content: s.html_content
    }));

    uiStore.openSlideshow({
        slides,
        startIndex: selectedSlideIdx.value,
        title: props.notebook.title
    });
}

onUnmounted(() => { if (recognition && isRecording.value) recognition.stop(); });
</script>

<template>
    <div class="h-full flex flex-col bg-slate-50 dark:bg-slate-950 overflow-hidden relative">
        
        <!-- PRODUCTION CONSOLE OVERLAY (PRO VERSION) -->
        <transition enter-active-class="transition duration-300" enter-from-class="opacity-0 scale-95" enter-to-class="opacity-100 scale-100" leave-active-class="transition duration-200" leave-from-class="opacity-100 scale-100" leave-to-class="opacity-0 scale-95">
            <div v-if="activeTask" class="absolute inset-0 z-[70] bg-slate-900/90 backdrop-blur-md flex flex-col items-center justify-center p-12">
                <div class="max-w-3xl w-full">
                    <div class="flex items-center justify-between mb-8">
                        <div class="flex items-center gap-6">
                            <div class="p-5 bg-blue-600 rounded-2xl shadow-xl shadow-blue-500/30"><IconAnimateSpin class="w-12 h-12 animate-spin text-white"/></div>
                            <div>
                                <h2 class="text-3xl font-black text-white uppercase tracking-tighter">{{ activeTask.name }}</h2>
                                <p class="text-blue-400 font-bold uppercase tracking-widest text-xs">{{ activeTask.description }}</p>
                            </div>
                        </div>
                        <div class="text-5xl font-black text-blue-500 font-mono">{{ activeTask.progress }}%</div>
                    </div>
                    <div class="w-full bg-slate-800 h-3 rounded-full overflow-hidden mb-10"><div class="h-full bg-blue-500 transition-all duration-500 progress-bar-animated" :style="{width: activeTask.progress + '%'}"></div></div>
                    <div class="bg-black rounded-2xl border border-slate-800 overflow-hidden h-64 flex flex-col">
                        <div class="px-4 py-2 bg-slate-800 text-[10px] font-black uppercase text-slate-400 tracking-widest border-b border-slate-700">Studio Log Output</div>
                        <div ref="logsContainerRef" class="flex-grow overflow-y-auto p-4 font-mono text-[11px] text-slate-400 space-y-1 custom-scrollbar">
                            <div v-for="(log, i) in activeTask.logs" :key="i" class="flex gap-4">
                                <span class="opacity-30 shrink-0">[{{ new Date(log.timestamp).toLocaleTimeString() }}]</span>
                                <span :class="{'text-red-400': log.level === 'ERROR', 'text-blue-400': log.level === 'INFO'}">{{ log.message }}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </transition>

        <!-- GLOBAL HEADER TELEPORTS -->
        <Teleport to="#global-header-title-target">
            <div class="flex flex-col items-center">
                <div class="flex items-center gap-2 group cursor-pointer" @click="handleAutoTitle" title="Click to auto-title">
                    <span class="text-sm font-bold text-slate-800 dark:text-slate-100">{{ notebook.title }}</span>
                    <IconSparkles class="w-3 h-3 text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <div class="flex items-center gap-2 text-[10px] text-slate-500"><IconPresentationChartBar class="w-3 h-3" /><span class="uppercase tracking-wide font-medium">{{ currentTab?.title || 'Studio' }}</span></div>
            </div>
        </Teleport>

        <Teleport to="#global-header-actions-target">
            <div class="flex items-center gap-1">
                <select :value="notebook.language" @change="handleLanguageChange($event.target.value)" class="bg-slate-100 dark:bg-slate-800 border-none rounded px-2 py-1 text-[10px] font-black uppercase outline-none mr-2">
                    <option v-for="l in languages" :key="l.code" :value="l.code">{{ l.code }}</option>
                </select>
                <button @click="handleExport('pptx')" class="btn-icon-flat text-orange-600" title="PPTX"><IconPresentationChartBar class="w-4 h-4" /></button>
                <button @click="handleExport('pdf')" class="btn-icon-flat text-red-600" title="PDF"><IconFileText class="w-4 h-4" /></button>
                <button @click="handleExport('zip')" class="btn-icon-flat text-blue-600" title="Export ZIP"><IconFolder class="w-4 h-4" /></button>
                <button @click="handleGenerateVideo" class="btn-icon-flat text-pink-500" title="Gen Video"><IconVideoCamera class="w-4 h-4" /></button>
                <button @click="handleGenerateSummary" class="btn-icon-flat" title="Summary" :disabled="isSummaryGenerating"><IconSparkles class="w-4 h-4 text-purple-500" /></button>
                <button @click="isDiscussionVisible = !isDiscussionVisible" class="btn-icon-flat relative" :class="{'bg-blue-50 dark:bg-blue-900/20 text-blue-500': isDiscussionVisible}"><IconChatBubbleLeftRight class="w-4 h-4" /></button>
                <button @click="playSlideshow" class="btn-primary-flat ml-2"><IconPresentationChartBar class="w-4 h-4" /><span class="hidden sm:inline ml-1">Play</span></button>
            </div>
        </Teleport>

        <!-- TOP THUMBNAILS NAV -->
        <div class="h-28 flex-shrink-0 bg-white dark:bg-slate-900 border-b dark:border-slate-800 flex items-center px-4 gap-3 overflow-x-auto no-scrollbar shadow-sm z-20">
            <div v-for="(s, i) in slideData.slides_data" :key="s.id" @click="selectedSlideIdx = i"
                 class="h-20 aspect-video flex-shrink-0 rounded-lg border-2 cursor-pointer overflow-hidden transition-all relative group shadow-sm"
                 :class="selectedSlideIdx === i ? 'border-blue-500 ring-2 ring-blue-500/20' : 'border-slate-200 dark:border-slate-800 opacity-60 hover:opacity-100'">
                <AuthenticatedImage v-if="s.images?.length" :src="s.images[s.selected_image_index || 0].path" img-class="object-cover" class="w-full h-full" />
                <div v-else class="w-full h-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-300 font-mono text-xs">{{ i + 1 }}</div>
                <div class="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[9px] px-1 truncate py-0.5 font-bold">{{ s.title || 'Untitled' }}</div>
            </div>
            <button @click="openWizard" class="h-20 aspect-video border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-lg flex flex-col items-center justify-center text-slate-400 hover:border-blue-500 hover:text-blue-500 transition-colors"><IconPlus class="w-6 h-6 mb-1"/><span class="text-[9px] font-black uppercase">Add Slide</span></button>
        </div>

        <div class="flex-grow flex overflow-hidden">
            <!-- THE STAGE (16:9) -->
            <div class="flex-grow flex flex-col items-center p-6 md:p-10 overflow-hidden relative">
                
                <!-- Deck Video Overlay -->
                <div v-if="slideData.video_src" class="w-full max-w-5xl mb-4 bg-black rounded-xl overflow-hidden shadow-2xl relative group/video">
                    <AuthenticatedVideo :src="slideData.video_src" />
                    <div class="absolute top-4 right-4 opacity-0 group-hover/video:opacity-100 transition-opacity flex gap-2">
                        <button @click="handleDeleteVideo" class="btn btn-danger btn-sm shadow-xl"><IconTrash class="w-4 h-4 mr-1"/> Delete Video</button>
                    </div>
                </div>

                <div v-if="currentSlide" class="w-full max-w-5xl aspect-video bg-white shadow-2xl rounded-xl overflow-hidden flex flex-col border border-slate-200 dark:border-slate-800 relative group/canvas">
                    <div class="flex-grow flex p-12 gap-10 overflow-hidden relative">
                        <!-- Switchable Mode: Graphic or Image -->
                        <template v-if="viewMode === 'html' && currentSlide.html_content">
                            <iframe :src="currentHtmlSrc" class="w-full h-full border-none bg-white"></iframe>
                        </template>
                        <template v-else>
                            <template v-if="currentSlide.layout === 'ImageOnly'">
                                <div class="absolute inset-0 z-0"><AuthenticatedImage v-if="currentImage" :src="currentImage.path" img-class="object-cover" class="w-full h-full" /></div>
                                <div class="absolute bottom-0 left-0 right-0 p-12 bg-gradient-to-t from-black/90 to-transparent z-10"><h1 class="text-4xl font-black text-white uppercase tracking-tight">{{ currentSlide.title }}</h1></div>
                            </template>
                            <template v-else-if="currentSlide.layout === 'TitleImageBody' || currentSlide.layout === 'TwoColumn'">
                                <div class="w-1/2 flex flex-col z-10"><h1 class="text-3xl font-black text-slate-900 mb-8 border-b-4 border-blue-500 pb-2 inline-block self-start">{{ currentSlide.title }}</h1><ul class="space-y-4"><li v-for="(b, i) in currentSlide.bullets" :key="i" class="flex gap-4 text-xl text-slate-700 font-medium leading-snug"><span class="text-blue-500 font-black">•</span><span>{{ b }}</span></li></ul></div>
                                <div class="w-1/2 rounded-2xl overflow-hidden shadow-xl border-8 border-white dark:border-slate-800 bg-slate-50 relative">
                                    <AuthenticatedImage v-if="currentImage" :src="currentImage.path" img-class="object-cover" class="w-full h-full" />
                                    <div v-if="currentImage" class="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2 opacity-0 group-hover/canvas:opacity-100 transition-opacity"><button @click.stop="navImage(-1)" class="p-2 bg-black/60 rounded-full text-white hover:bg-black"><IconChevronLeft class="w-4 h-4"/></button><button @click.stop="navImage(1)" class="p-2 bg-black/60 rounded-full text-white hover:bg-black"><IconChevronRight class="w-4 h-4"/></button></div>
                                </div>
                            </template>
                            <template v-else><div class="flex-grow flex flex-col"><h1 class="text-5xl font-black text-slate-900 mb-12 border-b-8 border-blue-500 pb-4 inline-block self-start uppercase tracking-tighter">{{ currentSlide.title }}</h1><ul v-if="currentSlide.layout === 'TextOnly'" class="space-y-6"><li v-for="(b, i) in currentSlide.bullets" :key="i" class="flex gap-6 text-2xl text-slate-800 font-bold leading-tight"><span class="text-blue-600 font-black">▶</span><span>{{ b }}</span></li></ul></div></template>
                        </template>
                    </div>
                    <!-- Controls Overlay on Stage -->
                    <div class="absolute top-4 right-4 flex gap-2 opacity-0 group-hover/canvas:opacity-100 transition-opacity z-20">
                         <button @click="openGenModal('images')" class="p-2 bg-white/90 dark:bg-slate-800/90 rounded-lg shadow hover:text-blue-500 transition-colors" title="Gen Variant"><IconRefresh class="w-4 h-4" /></button>
                         <button @click="openGenModal('refine_image')" class="p-2 bg-white/90 dark:bg-slate-800/90 rounded-lg shadow hover:text-purple-500 transition-colors" title="AI Edit"><IconMagic class="w-4 h-4" /></button>
                         <button @click="handleGenerateHtml" class="p-2 bg-white/90 dark:bg-slate-800/90 rounded-lg shadow hover:text-green-500 transition-colors" title="Create HTML Graphic"><IconCode class="w-4 h-4" /></button>
                         <button v-if="currentSlide.html_content" @click="viewMode = viewMode === 'image' ? 'html' : 'image'" class="p-2 bg-white/90 dark:bg-slate-800/90 rounded-lg shadow hover:text-orange-500 transition-colors" title="Toggle Graphic/Image">
                            <IconPhoto v-if="viewMode === 'html'" class="w-4 h-4" />
                            <IconCode v-else class="w-4 h-4" />
                         </button>
                         <button v-if="currentImage" @click="downloadImage(currentImage)" class="p-2 bg-white/90 dark:bg-slate-800/90 rounded-lg shadow hover:text-blue-500 transition-colors" title="Download Image"><IconArrowDownTray class="w-4 h-4"/></button>
                    </div>
                    <div class="h-10 bg-slate-50 dark:bg-slate-900 border-t flex items-center justify-between px-8 text-[10px] font-black uppercase text-slate-400"><span>Layout: {{ currentSlide.layout }}</span><span>Slide {{ selectedSlideIdx + 1 }} / {{ slideData.slides_data.length }}</span></div>
                </div>
                <!-- VERSION STRIP & ACTIONS -->
                <div v-if="currentSlide" class="w-full max-w-5xl mt-4 flex items-end gap-4 overflow-x-auto no-scrollbar pb-2">
                    <div v-if="currentSlide.images?.length" class="flex gap-2">
                        <div v-for="(img, idx) in currentSlide.images" :key="idx" @click="selectVariant(idx)" 
                             class="h-14 w-24 flex-shrink-0 rounded border-2 transition-all relative group/thumb overflow-hidden cursor-pointer" 
                             :class="idx === (currentSlide.selected_image_index || 0) ? 'border-blue-500' : 'border-transparent opacity-50'">
                            <AuthenticatedImage :src="img.path" class="w-full h-full object-cover" />
                            <div class="absolute inset-0 flex items-center justify-center gap-1 opacity-0 group-hover/thumb:opacity-100 bg-black/40 transition-opacity">
                                <button @click.stop="analyzeVariant(img)" class="text-white p-0.5 bg-blue-600 rounded" title="Analyze AI"><IconInfo class="w-3 h-3"/></button>
                                <button @click.stop="deleteVariant(idx)" class="text-white p-0.5 bg-red-600 rounded" title="Delete"><IconTrash class="w-3 h-3"/></button>
                            </div>
                        </div>
                    </div>
                    <button @click="triggerImport" class="h-14 w-24 flex-shrink-0 rounded border-2 border-dashed border-slate-300 dark:border-slate-800 flex items-center justify-center text-slate-400 hover:text-blue-500 hover:border-blue-500 transition-colors"><IconArrowDownTray class="w-5 h-5"/></button>
                    <input type="file" ref="fileInput" @change="handleFileUpload" class="hidden" accept="image/*" />
                </div>
            </div>

            <!-- RIGHT BAR -->
            <transition enter-active-class="transition duration-300 transform translate-x-full" enter-to-class="translate-x-0">
                <div v-if="isDiscussionVisible" class="w-80 border-l dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col flex-shrink-0 z-30 shadow-2xl">
                    <div class="p-4 border-b flex items-center justify-between"><div class="flex items-center gap-2"><IconChatBubbleLeftRight class="w-4 h-4 text-blue-500" /><h3 class="font-black text-[10px] uppercase tracking-widest">Intelligence</h3></div><button @click="isDiscussionVisible = false" class="btn-icon-flat"><IconXMark class="w-5 h-5"/></button></div>
                    <div class="flex-grow overflow-y-auto custom-scrollbar p-4 space-y-4" ref="messagesContainerRef">
                        <div v-for="(msg, mIdx) in currentSlide?.messages" :key="mIdx" class="flex flex-col gap-1" :class="{'items-end': msg.role === 'user'}"><div class="p-3 rounded-2xl text-xs max-w-[90%]" :class="msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300'"><MessageContentRenderer :content="msg.content" /></div></div>
                    </div>
                    <div class="p-4 border-t flex gap-2"><textarea v-model="slideChatMessage" @keyup.enter.exact="sendSlideChat" class="input-field w-full text-xs h-20 resize-none" placeholder="Ask AI..." :disabled="isSendingMessage"></textarea><button @click="sendSlideChat" class="btn btn-primary h-20" :disabled="isSendingMessage"><IconSend class="w-4 h-4"/></button></div>
                </div>
            </transition>
        </div>

        <!-- EDITOR & PROMPT -->
        <div class="bg-white dark:bg-slate-900 border-t dark:border-slate-800 shadow-2xl p-6 z-40">
            <div class="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-8">
                <div v-if="currentSlide" class="space-y-4">
                    <div class="flex items-center justify-between"><h3 class="text-[10px] font-black uppercase text-slate-400 tracking-widest flex items-center gap-2"><IconPencil class="w-3 h-3"/> Content Editor</h3><select :value="currentSlide.layout" @change="updateSlideField('layout', $event.target.value)" class="text-[10px] font-bold bg-slate-100 dark:bg-slate-800 border-none rounded px-3 py-1 focus:ring-1 ring-blue-500 transition-all"><option v-for="opt in layoutOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option></select></div>
                    <input :value="currentSlide.title" @change="updateSlideField('title', $event.target.value)" placeholder="Slide Title..." class="w-full text-2xl font-black bg-transparent border-b-2 border-slate-100 dark:border-slate-800 focus:border-blue-500 p-0 transition-all outline-none" />
                    <div class="space-y-3 max-h-40 overflow-y-auto custom-scrollbar pr-2"><div v-for="(bullet, bIdx) in (currentSlide.bullets || [])" :key="bIdx" class="flex items-start gap-3 group"><span class="text-blue-500 font-black mt-1.5">●</span><textarea :value="bullet" @change="updateSlideField('bullets', currentSlide.bullets.map((b, i) => i === bIdx ? $event.target.value : b))" class="flex-grow bg-transparent text-sm border-none focus:ring-0 p-0 resize-none min-h-[24px]" rows="1"></textarea><button @click="updateSlideField('bullets', currentSlide.bullets.filter((_, i) => i !== bIdx))" class="opacity-0 group-hover:opacity-100 text-red-500 transition-opacity p-1"><IconTrash class="w-3.5 h-3.5"/></button></div><button @click="updateSlideField('bullets', [...(currentSlide.bullets || []), 'New point...'])" class="text-[10px] font-black uppercase text-blue-500 hover:underline">+ Add Point</button></div>
                </div>
                <div class="flex flex-col gap-4">
                    <div v-if="currentSlide" class="flex-grow flex flex-col bg-slate-50 dark:bg-slate-800/40 rounded-2xl p-4 border dark:border-slate-800 relative group/notes">
                        <div class="flex justify-between items-center mb-2"><div class="flex items-center gap-2"><IconMicrophone class="w-3.5 h-3.5 text-slate-400"/><label class="text-[10px] font-black uppercase text-slate-500 tracking-widest">Speaker Script</label><button @click="toggleDictation('notes')" class="p-1 rounded-full transition-all" :class="isRecording ? 'text-red-600 bg-red-100' : 'text-blue-500'"><IconMicrophone class="w-4 h-4" /></button></div><div class="flex gap-2">
                                <button @click="handleGenerateAudio" class="btn btn-secondary btn-xs" :disabled="isAudioGenerating">TTS</button>
                                <button @click="handleAutoNotes" class="btn btn-secondary btn-xs" :disabled="isNotesGenerating">AI Gen</button>
                                <button v-if="currentSlide.audio_src" @click="handleDeleteAudio" class="text-red-500 p-1 hover:bg-red-50 rounded"><IconTrash class="w-3.5 h-3.5"/></button>
                            </div></div>
                        <textarea :value="currentSlide.notes" @change="updateSlideField('notes', $event.target.value)" class="flex-grow bg-transparent border-none focus:ring-0 text-xs leading-relaxed resize-none p-0 custom-scrollbar" placeholder="Type script..."></textarea>
                        <div v-if="currentSlide.audio_src" class="mt-2 bg-blue-50 dark:bg-blue-900/20 rounded-xl p-2 flex items-center gap-2"><AuthenticatedAudio :src="currentSlide.audio_src" class="flex-grow"/></div>
                    </div>
                    <div class="flex gap-3 mt-auto"><input v-model="aiPrompt" @keyup.enter="handleProcess" placeholder="Add slides or refine deck..." class="input-field flex-grow h-12 rounded-2xl border-2" /><button @click="handleProcess" :disabled="!aiPrompt.trim() || activeTask" class="btn btn-primary px-8 rounded-2xl h-12 shadow-xl"><IconSparkles class="w-5 h-5 mr-2"/><span class="font-bold">Process</span></button></div>
                </div>
            </div>
        </div>

        <!-- MODALS -->
        <transition name="fade">
            <div v-if="isWizardOpen" class="fixed inset-0 z-[100] bg-slate-900/60 backdrop-blur-sm p-6 flex items-center justify-center">
                <div class="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-3xl flex flex-col border dark:border-slate-800"><div class="p-4 border-b flex justify-between items-center bg-slate-50 dark:bg-slate-800/50"><h3 class="font-black text-sm uppercase tracking-widest">New Slide Wizard</h3><button @click="isWizardOpen = false" class="btn-icon-flat"><IconXMark class="w-5 h-5"/></button></div><div class="p-8 min-h-[450px] overflow-y-auto custom-scrollbar">
                        <div v-if="wizardStep === 1" class="space-y-6"><div><label class="text-[10px] font-black uppercase text-blue-500 mb-2 block">1. Topic</label><textarea v-model="wizardData.topic" class="input-field w-full h-24 font-bold text-lg" placeholder="What should this slide be about?"></textarea></div><div><label class="text-[10px] font-black uppercase text-slate-500 mb-2 block">Sources</label><div class="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto p-2 border rounded-xl"><button v-for="art in notebook.artefacts" :key="art.filename" @click="toggleWizardArtefact(art.filename)" class="p-2 rounded-lg text-[10px] flex items-center gap-2 border transition-all" :class="wizardData.selected_artefacts.includes(art.filename) ? 'bg-green-50 border-green-500' : 'border-transparent'"><IconCheckCircle v-if="wizardData.selected_artefacts.includes(art.filename)" class="w-3 h-3"/><span class="truncate">{{ art.filename }}</span></button></div></div></div>
                        <div v-if="wizardStep === 2" class="space-y-6"><label class="text-[10px] font-black uppercase text-blue-500 mb-4 block">3. Layout Architecture</label><div class="grid grid-cols-3 gap-4"><button v-for="opt in layoutOptions" :key="opt.value" @click="wizardData.layout = opt.value" class="p-4 rounded-xl border-2 transition-all text-left" :class="wizardData.layout === opt.value ? 'border-blue-500 bg-blue-50' : 'border-slate-100'"><p class="text-xs font-black">{{ opt.label }}</p><p class="text-[9px] opacity-60">{{ opt.desc }}</p></button></div></div>
                        <div v-if="wizardStep === 3" class="space-y-4"><div><label class="text-[10px] font-black text-slate-500 mb-1 block">Proposed Title</label><input v-model="wizardData.title" class="input-field w-full font-bold" /></div><div><label class="text-[10px] font-black text-slate-500 mb-1 block">Visual Strategy (Prompt)</label><textarea v-model="wizardData.image_prompt" class="input-field w-full h-20 text-xs italic resize-none"></textarea></div></div>
                </div>
                <div class="p-4 border-t dark:border-slate-800 flex justify-between bg-slate-50 dark:bg-slate-900/50"><button v-if="wizardStep > 1" @click="wizardStep--" class="btn btn-secondary">Back</button><div v-else></div><div class="flex gap-2"><button @click="isWizardOpen = false" class="btn btn-secondary">Cancel</button><button v-if="wizardStep === 3" @click="finalizeAddSlide" class="btn btn-primary">Add to Deck</button><button v-else-if="wizardStep === 2" @click="brainstormSlide" class="btn btn-primary" :disabled="isBrainstorming"><IconAnimateSpin v-if="isBrainstorming" class="w-4 h-4 mr-2 animate-spin" />Brainstorm</button><button v-else @click="wizardStep = 2" class="btn btn-primary" :disabled="!wizardData.topic.trim()">Next</button></div></div></div>
            </div>
        </transition>

        <transition name="fade">
            <div v-if="isGenModalOpen" class="fixed inset-0 z-[110] bg-slate-900/60 backdrop-blur-sm p-6 flex items-center justify-center">
                <div class="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden border dark:border-slate-800 flex flex-col"><div class="p-4 border-b bg-slate-50 dark:bg-slate-800/50 flex justify-between items-center"><h3 class="font-black text-sm uppercase tracking-widest text-blue-600">{{ genModalMode === 'refine_image' ? 'Refine Visual' : 'New Variant' }}</h3><button @click="isGenModalOpen = false" class="btn-icon-flat"><IconXMark class="w-5 h-5"/></button></div><div class="p-6 space-y-4">
                        <div><label class="text-[10px] font-bold uppercase text-slate-500 mb-1 block">Strategy Prompt</label><textarea v-model="genPrompt" class="input-field w-full h-32 resize-none"></textarea></div>
                        <div class="flex justify-between items-center"><div class="flex items-center gap-2"><IconInfo class="w-3 h-3 text-slate-400"/><span class="text-[9px] font-bold uppercase text-slate-400">Context: {{ selectedArtefactNames.length }} Active</span></div><button @click="enhanceGenPrompt" class="btn btn-secondary btn-sm" :disabled="isEnhancing"><IconSparkles class="w-3 h-3 mr-1" /> Enhance AI</button></div>
                        <div><label class="text-[10px] font-bold uppercase text-red-500 mb-1 block">Negative Guidance (Avoid)</label><textarea v-model="genNegativePrompt" class="input-field w-full h-16 resize-none border-red-100" placeholder="Negative..."></textarea></div>
                    </div><div class="p-4 border-t dark:border-slate-800 flex justify-end gap-2 bg-slate-50"><button @click="isGenModalOpen = false" class="btn btn-secondary">Cancel</button><button @click="submitGenModal" class="btn btn-primary" :disabled="!genPrompt.trim()">Generate Variant</button></div></div>
            </div>
        </transition>

        <transition name="fade"><div v-if="editingArtefact" class="fixed inset-0 z-[100] bg-slate-900/60 flex items-center justify-center"><div class="bg-white dark:bg-slate-900 rounded-2xl w-full max-w-4xl h-[80vh] flex flex-col overflow-hidden"><div class="p-4 border-b flex justify-between items-center bg-slate-50"><h3 class="font-black text-xs uppercase tracking-widest">Edit Knowledge Source</h3><button @click="editingArtefact = null"><IconXMark class="w-5 h-5"/></button></div><div class="flex-grow p-6 flex flex-col gap-4"><input v-model="editingArtefact.name" class="input-field font-bold"/><textarea v-model="editingArtefact.content" class="flex-grow input-field font-mono text-xs p-4 resize-none"></textarea></div><div class="p-4 border-t flex justify-end gap-2"><button @click="editingArtefact = null" class="btn btn-secondary">Cancel</button><button @click="saveArtefactEdit" class="btn btn-primary">Update Artefact</button></div></div></div></transition>

    </div>
</template>

<style scoped>
.aspect-video { aspect-ratio: 16 / 9; }
.no-scrollbar::-webkit-scrollbar { display: none; }
.custom-scrollbar::-webkit-scrollbar { width: 5px; height: 5px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-slate-300 dark:bg-slate-700 rounded-full; }
.progress-bar-animated { background-image: linear-gradient(45deg, rgba(255, 255, 255, .15) 25%, transparent 25%, transparent 50%, rgba(255, 255, 255, .15) 50%, rgba(255, 255, 255, .15) 75%, transparent 75%, transparent); background-size: 1rem 1rem; animation: progress-animation 1s linear infinite; }
@keyframes progress-animation { from { background-position: 1rem 0; } to { background-position: 0 0; } }
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
