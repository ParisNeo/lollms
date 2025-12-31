<script setup>
import { ref, computed, onMounted, watch, nextTick, onUnmounted, markRaw } from 'vue';
import { useUiStore } from '../stores/ui';
import { useNotebookStore } from '../stores/notebooks';
import { useDiscussionsStore } from '../stores/discussions';
import { useTasksStore } from '../stores/tasks';
import { useAuthStore } from '../stores/auth';
import { storeToRefs } from 'pinia';
import CodeMirrorEditor from '../components/ui/CodeMirrorComponent/index.vue';
import MessageContentRenderer from '../components/ui/MessageContentRenderer/MessageContentRenderer.vue';
import AuthenticatedImage from '../components/ui/AuthenticatedImage.vue';
import apiClient from '../services/api';
import useEventBus from '../services/eventBus';

// Icons
import IconPlus from '../assets/icons/IconPlus.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconSend from '../assets/icons/IconSend.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconServer from '../assets/icons/IconServer.vue';
import IconSave from '../assets/icons/IconSave.vue';
import IconFileText from '../assets/icons/IconFileText.vue';
import IconXMark from '../assets/icons/IconXMark.vue';
import IconCheckCircle from '../assets/icons/IconCheckCircle.vue';
import IconCircle from '../assets/icons/IconCircle.vue';
import IconArrowUpTray from '../assets/icons/IconArrowUpTray.vue';
import IconWeb from '../assets/icons/ui/IconWeb.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconEye from '../assets/icons/IconEye.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue';
import IconArchiveBox from '../assets/icons/IconArchiveBox.vue';
import IconPresentationChartBar from '../assets/icons/IconPresentationChartBar.vue';
import IconDownload from '../assets/icons/IconDownload.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconCog from '../assets/icons/IconCog.vue';
import IconTable from '../assets/icons/IconTable.vue';
import IconPlayCircle from '../assets/icons/IconPlayCircle.vue'; 
import IconPhoto from '../assets/icons/IconPhoto.vue';
import IconCode from '../assets/icons/IconCode.vue';

const uiStore = useUiStore();
const notebookStore = useNotebookStore();
const discussionsStore = useDiscussionsStore();
const tasksStore = useTasksStore();
const authStore = useAuthStore();
const { on, off } = useEventBus();

const { activeNotebook } = storeToRefs(notebookStore);
const { tasks } = storeToRefs(tasksStore);
const { user } = storeToRefs(authStore);

const aiPrompt = ref('');
const isDraggingOver = ref(false);
const fileInput = ref(null);
const isRenderMode = ref(true); 
const activeTabId = ref(null);
const selectedInputTabs = ref(new Set());
const generationAction = ref(''); 
const logsContainer = ref(null);
const modifyCurrentTab = ref(false);

// Slide Mode Specifics
const slideViewMode = ref('designer'); // 'designer', 'planner'
const selectedSlideIndex = ref(0);
const isCardFlipped = ref(false);
const localImagePrompt = ref('');

const isTtiAvailable = computed(() => !!user.value?.tti_binding_model_name);
const isSlidesNotebook = computed(() => activeNotebook.value?.type === 'slides_making');

const availableActions = computed(() => {
    const type = activeNotebook.value?.type || 'generic';
    const actions = [];
    if (type === 'data_analysis') {
        actions.push({ value: 'analyze_data', label: 'Analyze Data' });
        actions.push({ value: 'generate_visualization_code', label: 'Generate Plot Code' });
    } else if (type === 'book_building') {
        actions.push({ value: 'generate_outline', label: 'Generate Outline' });
        actions.push({ value: 'write_chapter', label: 'Write Chapter' });
    } else if (type === 'slides_making') {
        actions.push({ value: 'presentation_outline', label: 'Slide Outline' });
        actions.push({ value: 'generate_slides_text', label: 'Generate Slides' });
    } else if (type === 'benchmarks') {
        actions.push({ value: 'generate_test_cases', label: 'Gen Test Cases' });
    }
    actions.push({ value: 'text', label: 'Free Text Gen' });
    if (isTtiAvailable.value) actions.push({ value: 'images', label: 'Generate Images' });
    return actions;
});

const activeTask = computed(() => {
    if (!activeNotebook.value) return null;
    return tasks.value.find(t => 
        (t.name.includes(`Notebook ${activeNotebook.value.id}`) || t.name.includes(activeNotebook.value.id)) && 
        (t.status === 'running' || t.status === 'pending')
    );
});

const currentTab = computed(() => {
    if (!activeNotebook.value || !activeNotebook.value.tabs) return null;
    return activeNotebook.value.tabs.find(t => t.id === activeTabId.value) || activeNotebook.value.tabs[0];
});

watch(activeNotebook, (nb) => {
    if (nb && nb.tabs && nb.tabs.length > 0) {
        if (!activeTabId.value || !nb.tabs.find(t => t.id === activeTabId.value)) {
            activeTabId.value = nb.tabs[nb.tabs.length - 1].id;
        }
    } else if (nb && (!nb.tabs || nb.tabs.length === 0)) {
        notebookStore.addTab();
    }
}, { immediate: true });

watch(() => activeNotebook.value?.tabs?.length, (newLen, oldLen) => {
    if (newLen > oldLen && activeTask.value) {
        activeTabId.value = activeNotebook.value.tabs[newLen - 1].id;
    }
});

watch(() => activeTask.value?.logs?.length, () => {
    nextTick(() => {
        if (logsContainer.value) {
            logsContainer.value.scrollTop = logsContainer.value.scrollHeight;
        }
    });
}, { deep: true });

watch(tasks, (newTasks) => {
    if (activeNotebook.value) {
        const completedTask = newTasks.find(t => 
            t.status === 'completed' && 
            t.result && 
            t.result.notebook_id === activeNotebook.value.id
        );
        if (completedTask) {
             notebookStore.fetchNotebooks().then(() => {
                 notebookStore.selectNotebook(activeNotebook.value.id);
                 if (completedTask.result.new_tab_id) {
                     activeTabId.value = completedTask.result.new_tab_id;
                 }
             });
        }
    }
}, { deep: true });

// --- Parsed Content Helper ---
const currentTabParsed = computed(() => {
    if (!currentTab.value) return {};
    if (currentTab.value.type === 'slides' || isSlidesNotebook.value) {
        try {
            return typeof currentTab.value.content === 'string' ? JSON.parse(currentTab.value.content) : currentTab.value.content;
        } catch(e) {
            return { mode: 'text', slides_data: [] }; // Fallback
        }
    }
    return {};
});

// Update local prompt when selection changes
watch(
    () => {
        const s = currentTabParsed.value?.slides_data?.[selectedSlideIndex.value];
        return {
            idx: selectedSlideIndex.value,
            imgIdx: s?.selected_image_index,
            imagesLen: s?.images?.length
        };
    },
    (newVal) => {
        const slide = currentTabParsed.value?.slides_data?.[newVal.idx];
        if (slide) {
            const img = slide.images?.[newVal.imgIdx || 0];
            localImagePrompt.value = img?.prompt || slide.image_prompt || '';
        }
        // Reset flip state when slide changes
        isCardFlipped.value = false;
    },
    { deep: true, immediate: true }
);

// --- Default Generation Action Watcher ---
watch(
    [() => activeNotebook.value?.type, () => currentTabParsed.value?.mode, slideViewMode, availableActions],
    ([type, mode, viewMode, actions]) => {
        if (type === 'slides_making' && viewMode === 'designer') {
            // Slide Designer Context
            if (mode === 'image_only') {
                generationAction.value = 'images';
            } else {
                if (generationAction.value !== 'images' && generationAction.value !== 'update_slide_text') {
                    generationAction.value = 'update_slide_text';
                }
            }
        } else {
            // Standard Notebook Context
            if (actions && actions.length > 0) {
                const isValid = actions.some(a => a.value === generationAction.value);
                if (!isValid) {
                    generationAction.value = actions[0].value;
                }
            }
        }
    },
    { immediate: true }
);

// --- Actions ---
async function createNotebook() { uiStore.openModal('notebookWizard'); }
async function toggleSource(source) { source.is_loaded = !source.is_loaded; await notebookStore.saveActive(); }
async function removeSource(filename) { if (await uiStore.showConfirmation({ title: 'Remove Source?' })) { activeNotebook.value.artefacts = activeNotebook.value.artefacts.filter(a => a.filename !== filename); await notebookStore.saveActive(); } }
async function viewSource(source) { uiStore.openModal('sourceViewer', { title: source.filename, content: source.content, language: 'markdown' }); }
async function sendToChat() {
    if (!currentTab.value) return;
    const { confirmed, value: targetId } = await uiStore.showConfirmation({
        title: 'Send to Chat',
        message: 'Append current tab content to discussion context:',
        inputType: 'select',
        inputOptions: Object.values(discussionsStore.discussions).map(d => ({ text: d.title, value: d.id })),
        confirmText: 'Send'
    });
    if (confirmed && targetId) {
        const contentToSend = currentTab.value.content || (currentTab.value.type === 'gallery' ? JSON.stringify(currentTab.value.images) : '');
        await discussionsStore.appendToDataZone({ discussionId: targetId, content: contentToSend });
        uiStore.addNotification("Content sent to chat.", "success");
    }
}
function triggerFileUpload() { fileInput.value.click(); }
async function handleFileSelect(e) { const files = Array.from(e.target.files); if (!activeNotebook.value || files.length === 0) return; uiStore.addNotification(`Uploading ${files.length} source(s)...`, 'info'); await Promise.all(files.map(f => notebookStore.uploadSource(f))); e.target.value = ''; }
async function handleScrape() { if (!activeNotebook.value) return; const { confirmed, value: url } = await uiStore.showConfirmation({ title: 'Scrape URL', message: 'Enter URL:', inputType: 'text', confirmText: 'Scrape' }); if (confirmed && url) await notebookStore.scrapeUrl(url); }
async function handleRefresh() { if (activeNotebook.value) { await notebookStore.selectNotebook(activeNotebook.value.id); uiStore.addNotification("Notebook refreshed.", "success"); } }
async function handleConvertToSource() { if (!currentTab.value) return; const { confirmed, value: title } = await uiStore.showConfirmation({ title: 'Convert to Source', message: 'Enter title:', inputType: 'text', confirmText: 'Convert' }); if (confirmed && title) { const content = currentTab.value.content || (currentTab.value.type === 'gallery' ? JSON.stringify(currentTab.value.images) : ''); await notebookStore.createTextArtefact(title, content); } }
function handleTabClick(tabId) { activeTabId.value = tabId; }
async function handleAddTab() { notebookStore.addTab(); setTimeout(() => { if(activeNotebook.value.tabs.length > 0) activeTabId.value = activeNotebook.value.tabs[activeNotebook.value.tabs.length-1].id; }, 100); }
function handleCloseTab(tabId) { if (confirm("Delete this tab?")) { notebookStore.removeTab(tabId); if (activeTabId.value === tabId) { activeTabId.value = activeNotebook.value.tabs.length > 0 ? activeNotebook.value.tabs[0].id : null; } } }
function toggleInputSelection(tabId) { if (selectedInputTabs.value.has(tabId)) selectedInputTabs.value.delete(tabId); else selectedInputTabs.value.add(tabId); }
function handleAutoRename() { notebookStore.generateTitle(); }
function openImageViewer(src) { uiStore.openImageViewer({ imageList: [{ src, prompt: 'Notebook Image' }], startIndex: 0 }); }

async function exportNotebook(format) {
    try {
        const response = await apiClient.get(`/api/notebooks/${activeNotebook.value.id}/export`, { params: { format }, responseType: 'blob' });
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        const ext = format === 'json' ? 'json' : 'pptx';
        link.setAttribute('download', `${activeNotebook.value.title}.${ext}`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } catch(e) {
        uiStore.addNotification("Export failed.", "error");
    }
}

function handleProcess() {
    const inputs = Array.from(selectedInputTabs.value);
    const targetTabId = modifyCurrentTab.value || isSlidesNotebook.value ? activeTabId.value : null;
    
    if (modifyCurrentTab.value && !activeTabId.value) { uiStore.addNotification("No active tab.", "warning"); return; }
    if (generationAction.value === 'images' && !aiPrompt.value.trim() && (!modifyCurrentTab.value || !currentTab.value?.title)) { uiStore.addNotification("Prompt required.", "warning"); return; }
    
    // For slide specific updates
    if (isSlidesNotebook.value && slideViewMode.value === 'designer') {
        if (!aiPrompt.value.trim()) { uiStore.addNotification("Prompt required.", "warning"); return; }
        
        // Handle Action Setup for Slides
        if (generationAction.value === 'images') {
             // Check if prefix already exists (e.g. from flip card or manual entry)
             if (!aiPrompt.value.startsWith('SLIDE_INDEX:')) {
                 aiPrompt.value = `SLIDE_INDEX:${selectedSlideIndex.value}| ${aiPrompt.value}`;
             }
        } else if (generationAction.value === 'update_slide_text') {
             if (!aiPrompt.value.startsWith('SLIDE_INDEX:')) {
                 aiPrompt.value = `SLIDE_INDEX:${selectedSlideIndex.value}| ${aiPrompt.value}`;
             }
        }
    }

    if (!aiPrompt.value.trim() && generationAction.value !== 'images' && generationAction.value !== 'generate_slides_text') return;
    
    notebookStore.processWithAi(aiPrompt.value, inputs, generationAction.value, targetTabId);
    aiPrompt.value = '';
    selectedInputTabs.value.clear();
}

// Slide Specific Handlers
function handleRegenerateSlideImage(slideIndex, slideTitle) {
    modifyCurrentTab.value = true;
    generationAction.value = 'images';
    // Set descriptive prompt without prefix, handleProcess will add it
    aiPrompt.value = `Create a high quality visual representation for the slide titled "${slideTitle}".`; 
    handleProcess();
}

function handleGenerateFromFlip() {
    if (!localImagePrompt.value.trim()) return;
    // Switch action
    generationAction.value = 'images';
    aiPrompt.value = localImagePrompt.value;
    // Trigger standard regeneration logic
    handleProcess();
    // Flip back
    isCardFlipped.value = false;
}

function selectMainImage(slideIndex, imgIndex) {
    const parsed = currentTabParsed.value;
    if (parsed.slides_data && parsed.slides_data[slideIndex]) {
        parsed.slides_data[slideIndex].selected_image_index = imgIndex;
        currentTab.value.content = JSON.stringify(parsed);
        notebookStore.saveActive();
    }
}

function handleAddSlide(index) {
    const parsed = currentTabParsed.value;
    if (!parsed.slides_data) parsed.slides_data = [];
    
    const newSlide = {
        id: crypto.randomUUID(),
        layout: 'TitleBody',
        title: 'New Slide',
        bullets: ['Add content here...'],
        images: [],
        selected_image_index: 0
    };
    
    parsed.slides_data.splice(index + 1, 0, newSlide);
    currentTab.value.content = JSON.stringify(parsed);
    notebookStore.saveActive();
    selectedSlideIndex.value = index + 1;
}

function handleDeleteSlide(index) {
    const parsed = currentTabParsed.value;
    if (!parsed.slides_data) return;
    parsed.slides_data.splice(index, 1);
    currentTab.value.content = JSON.stringify(parsed);
    notebookStore.saveActive();
    if (selectedSlideIndex.value >= parsed.slides_data.length) {
        selectedSlideIndex.value = Math.max(0, parsed.slides_data.length - 1);
    }
}

function handleDeleteSlideImage(slideIndex, imgIndex) {
    const parsed = currentTabParsed.value;
    const slide = parsed.slides_data[slideIndex];
    if (!slide || !slide.images) return;
    
    slide.images.splice(imgIndex, 1);
    
    // Adjust selection if we deleted the currently selected one or one before it
    if (slide.selected_image_index >= slide.images.length) {
        slide.selected_image_index = Math.max(0, slide.images.length - 1);
    } else if (imgIndex < slide.selected_image_index) {
        slide.selected_image_index--;
    }
    
    currentTab.value.content = JSON.stringify(parsed);
    notebookStore.saveActive();
}

// Drag & Drop for Slides
const draggingSlideIndex = ref(null);

function onSlideDragStart(index, event) {
    draggingSlideIndex.value = index;
    event.dataTransfer.effectAllowed = 'move';
}

function onSlideDrop(index) {
    if (draggingSlideIndex.value === null || draggingSlideIndex.value === index) return;
    const parsed = currentTabParsed.value;
    const item = parsed.slides_data.splice(draggingSlideIndex.value, 1)[0];
    parsed.slides_data.splice(index, 0, item);
    currentTab.value.content = JSON.stringify(parsed);
    notebookStore.saveActive();
    selectedSlideIndex.value = index;
    draggingSlideIndex.value = null;
}

onMounted(() => {
    notebookStore.fetchNotebooks();
    uiStore.setPageTitle({ title: '' });
});
onUnmounted(() => {
    uiStore.setPageTitle({ title: '' });
});
</script>

<template>
    <div class="h-full w-full flex flex-col overflow-hidden bg-white dark:bg-gray-900">
        <!-- Teleports -->
        <Teleport to="#global-header-title-target" v-if="activeNotebook">
             <div class="flex items-center gap-2 w-full max-w-md pointer-events-auto">
                 <input v-model="activeNotebook.title" @blur="notebookStore.saveActive" 
                        class="flex-grow bg-transparent border-b border-transparent hover:border-gray-300 focus:border-blue-500 focus:ring-0 text-center font-bold text-gray-800 dark:text-gray-200 transition-colors px-2 py-1 outline-none truncate" />
                 <button @click="handleAutoRename" class="p-1.5 rounded-full hover:bg-purple-100 dark:hover:bg-purple-900/30 text-purple-500 transition-colors"><IconSparkles class="w-4 h-4" /></button>
             </div>
        </Teleport>
        <Teleport to="#global-header-actions-target" v-if="activeNotebook">
            <div class="flex items-center gap-1">
                <span class="px-2 py-1 text-[10px] font-black uppercase bg-gray-100 dark:bg-gray-800 text-gray-500 rounded mr-2 border dark:border-gray-700">{{ activeNotebook.type ? activeNotebook.type.replace('_', ' ') : 'Generic' }}</span>
                
                <!-- View Switch for Slide Mode -->
                <div v-if="isSlidesNotebook" class="flex bg-gray-100 dark:bg-gray-800 rounded p-0.5 mr-2">
                    <button @click="slideViewMode = 'designer'" class="px-2 py-1 text-xs font-bold rounded" :class="slideViewMode === 'designer' ? 'bg-white dark:bg-gray-700 shadow text-blue-600' : 'text-gray-500'">Designer</button>
                    <button @click="slideViewMode = 'planner'" class="px-2 py-1 text-xs font-bold rounded" :class="slideViewMode === 'planner' ? 'bg-white dark:bg-gray-700 shadow text-purple-600' : 'text-gray-500'">Planner</button>
                </div>

                <button @click="exportNotebook('pptx')" class="btn-icon p-2" title="Export PPTX"><IconPresentationChartBar class="w-4 h-4" /></button>
                <button @click="exportNotebook('json')" class="btn-icon p-2" title="Export JSON"><IconDownload class="w-4 h-4" /></button>
                <button @click="handleRefresh" class="btn-icon p-2" title="Refresh"><IconRefresh class="w-4 h-4" /></button>
                <button v-if="!isSlidesNotebook" @click="handleConvertToSource" class="btn-icon p-2" title="Save Source"><IconArchiveBox class="w-4 h-4" /></button>
                <button v-if="!isSlidesNotebook" @click="sendToChat" class="btn-icon p-2" title="Send Chat"><IconSend class="w-4 h-4" /></button>
                <button @click="notebookStore.saveActive" class="btn-primary-flat p-2" title="Save"><IconSave class="w-4 h-4" /></button>
            </div>
        </Teleport>

        <div v-if="activeNotebook" class="h-full flex flex-col relative" @dragover.prevent="isDraggingOver=true" @dragleave="isDraggingOver=false" @drop.prevent="handleDrop">
            <div v-if="isDraggingOver" class="absolute inset-0 bg-blue-500/10 border-4 border-dashed border-blue-500 rounded-lg z-50 flex items-center justify-center m-4 pointer-events-none"><p class="text-2xl font-black text-blue-600 uppercase">Drop Research Sources Here</p></div>

            <!-- Tabs (Hidden for Slide Mode) -->
            <div v-if="!isSlidesNotebook" class="bg-gray-50 dark:bg-gray-800 border-b dark:border-gray-700 pt-1 px-4 flex-shrink-0">
                <div class="flex items-center justify-between">
                     <div class="flex items-center gap-1 overflow-x-auto custom-scrollbar pb-0 no-scrollbar">
                         <div v-for="tab in activeNotebook.tabs" :key="tab.id" class="group relative flex items-center gap-2 px-4 py-2 rounded-t-lg cursor-pointer transition-colors border-t border-x border-transparent hover:bg-gray-200 dark:hover:bg-gray-700 flex-shrink-0 text-xs font-medium uppercase tracking-wide" :class="activeTabId === tab.id ? 'bg-white dark:bg-gray-900 border-gray-300 dark:border-gray-600 text-blue-600 dark:text-blue-400 font-bold shadow-sm' : 'text-gray-500 hover:text-gray-700'">
                              <span @click="handleTabClick(tab.id)" class="truncate max-w-[120px]">{{ tab.title }}</span>
                              <button @click.stop="handleCloseTab(tab.id)" class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500"><IconXMark class="w-3 h-3" /></button>
                         </div>
                         <button @click="handleAddTab" class="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 mb-0.5 flex-shrink-0"><IconPlus class="w-4 h-4" /></button>
                    </div>
                </div>
            </div>

            <div class="flex-grow flex min-h-0 relative">
                <!-- Main Content -->
                <div class="flex-grow flex flex-col min-w-0 border-r dark:border-gray-700 relative">
                    <!-- Task Overlay -->
                    <div v-if="activeTask" class="absolute inset-0 z-30 bg-white/95 dark:bg-gray-900/95 flex flex-col backdrop-blur-sm">
                        <div class="p-4 border-b dark:border-gray-700 flex items-center justify-between shadow-sm bg-white dark:bg-gray-800 flex-shrink-0">
                            <div class="flex items-center gap-3"><IconAnimateSpin class="w-5 h-5 text-blue-600 animate-spin" /><div><h3 class="font-bold text-sm text-gray-900 dark:text-gray-100">{{ activeTask.name }}</h3><p class="text-xs text-gray-500 dark:text-gray-400">{{ activeTask.description }}</p></div></div><div class="text-xs font-mono text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-2 py-1 rounded">{{ activeTask.progress }}%</div>
                        </div>
                        <div class="flex-grow overflow-hidden relative"><div ref="logsContainer" class="absolute inset-0 overflow-y-auto p-4 font-mono text-xs text-gray-600 dark:text-gray-300 space-y-1"><div v-for="(log, idx) in activeTask.logs" :key="idx" class="flex gap-2"><span class="text-gray-400 shrink-0">[{{ new Date(log.timestamp).toLocaleTimeString() }}]</span><span :class="{'text-red-500': log.level === 'ERROR', 'text-yellow-500': log.level === 'WARNING'}">{{ log.message }}</span></div></div></div>
                    </div>

                    <div v-if="currentTab" class="flex-grow overflow-hidden flex flex-col relative h-full">
                        
                        <!-- SLIDE STUDIO VIEW -->
                        <div v-if="isSlidesNotebook && slideViewMode === 'designer'" class="h-full flex overflow-hidden">
                            <!-- Left: Slides List (Tiles) -->
                            <div class="w-64 bg-gray-100 dark:bg-gray-850 border-r dark:border-gray-700 flex flex-col flex-shrink-0">
                                <div class="p-3 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
                                    <h3 class="text-xs font-black uppercase text-gray-500 tracking-widest">Slides</h3>
                                </div>
                                <div class="flex-grow overflow-y-auto custom-scrollbar p-2 space-y-2">
                                    <div v-for="(slide, idx) in currentTabParsed.slides_data" :key="slide.id" 
                                         class="relative group"
                                         draggable="true"
                                         @dragstart="onSlideDragStart(idx, $event)"
                                         @dragover.prevent
                                         @drop="onSlideDrop(idx)"
                                    >
                                        <div @click="selectedSlideIndex = idx" 
                                             class="p-2 bg-white dark:bg-gray-800 rounded border-2 cursor-pointer transition-all hover:shadow-md"
                                             :class="selectedSlideIndex === idx ? 'border-blue-500 ring-1 ring-blue-500' : 'border-transparent hover:border-gray-300 dark:hover:border-gray-600'">
                                            <div class="flex items-center justify-between mb-1">
                                                <span class="text-[10px] font-bold text-gray-400">#{{ idx + 1 }}</span>
                                                <button @click.stop="handleDeleteSlide(idx)" class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500"><IconTrash class="w-3 h-3" /></button>
                                            </div>
                                            <div class="text-xs font-bold truncate mb-1">{{ slide.title }}</div>
                                            <div class="h-16 bg-gray-100 dark:bg-gray-900 rounded overflow-hidden flex items-center justify-center">
                                                <AuthenticatedImage 
                                                    v-if="slide.images && slide.images.length > 0" 
                                                    :src="slide.images[slide.selected_image_index || 0].path" 
                                                    class="w-full h-full object-cover" 
                                                />
                                                <IconPhoto v-else class="w-6 h-6 text-gray-300" />
                                            </div>
                                        </div>
                                        
                                        <!-- Insert Button -->
                                        <div class="absolute -bottom-3 left-0 right-0 h-4 opacity-0 hover:opacity-100 flex items-center justify-center z-10 cursor-pointer" @click="handleAddSlide(idx)">
                                            <div class="h-0.5 w-full bg-blue-500"></div>
                                            <div class="absolute bg-blue-500 text-white rounded-full p-0.5 shadow-sm"><IconPlus class="w-3 h-3" /></div>
                                        </div>
                                    </div>
                                    <button @click="handleAddSlide(currentTabParsed.slides_data?.length - 1)" class="w-full py-3 border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-lg text-gray-400 hover:text-blue-500 hover:border-blue-400 transition-colors flex items-center justify-center gap-2">
                                        <IconPlus class="w-4 h-4" /> Add Slide
                                    </button>
                                </div>
                            </div>

                            <!-- Center: Canvas -->
                            <div class="flex-grow bg-gray-200 dark:bg-gray-900 flex flex-col relative overflow-hidden">
                                <div class="flex-grow flex items-center justify-center p-8 overflow-auto">
                                    <div v-if="currentTabParsed.slides_data && currentTabParsed.slides_data[selectedSlideIndex]" class="bg-white dark:bg-gray-800 shadow-2xl rounded-xl w-full max-w-4xl aspect-video p-8 flex flex-col relative group overflow-hidden">
                                        
                                        <!-- Image Only Mode -->
                                        <div v-if="currentTabParsed.mode === 'image_only'" class="absolute inset-0">
                                            
                                            <!-- Prompt Edit View -->
                                            <div v-if="isCardFlipped" class="w-full h-full p-6 flex flex-col bg-gray-100 dark:bg-gray-900 absolute inset-0 z-30">
                                                <div class="flex justify-between items-center mb-4">
                                                    <h3 class="text-sm font-bold uppercase text-gray-500">Edit Image Prompt</h3>
                                                    <button @click="isCardFlipped = false" class="p-2 text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-800 rounded-full" title="Cancel">
                                                        <IconXMark class="w-5 h-5" />
                                                    </button>
                                                </div>
                                                <textarea 
                                                    v-model="localImagePrompt" 
                                                    class="flex-grow w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg p-4 resize-none focus:ring-2 focus:ring-blue-500 mb-4 font-mono text-sm"
                                                    placeholder="Describe the image you want to generate..."
                                                ></textarea>
                                                <div class="flex justify-end gap-2">
                                                    <button @click="isCardFlipped = false" class="btn btn-secondary">Cancel</button>
                                                    <button @click="handleGenerateFromFlip" class="btn btn-primary">
                                                        <IconSparkles class="w-4 h-4 mr-2" /> Generate
                                                    </button>
                                                </div>
                                            </div>

                                            <!-- Image View -->
                                            <div v-else class="w-full h-full relative group/imgview">
                                                <AuthenticatedImage 
                                                    v-if="currentTabParsed.slides_data[selectedSlideIndex].images && currentTabParsed.slides_data[selectedSlideIndex].images.length > 0" 
                                                    :src="currentTabParsed.slides_data[selectedSlideIndex].images[currentTabParsed.slides_data[selectedSlideIndex].selected_image_index || 0].path" 
                                                    class="w-full h-full object-cover" 
                                                />
                                                <div v-else class="flex items-center justify-center h-full text-gray-400 italic flex-col gap-2 bg-gray-100 dark:bg-gray-900">
                                                    <IconPhoto class="w-12 h-12 opacity-50" />
                                                    <span>No image generated</span>
                                                </div>
                                                
                                                <!-- Overlay Controls for Image Only -->
                                                <div class="absolute bottom-4 right-4 flex gap-2 opacity-0 group-hover/imgview:opacity-100 transition-opacity">
                                                    <button @click="isCardFlipped = true" class="btn btn-secondary btn-sm shadow-lg backdrop-blur-md bg-white/80 dark:bg-black/60"><IconPencil class="w-4 h-4 mr-1"/> Edit Prompt</button>
                                                    <button @click="handleRegenerateSlideImage(selectedSlideIndex, currentTabParsed.slides_data[selectedSlideIndex].title)" class="btn btn-primary btn-sm shadow-lg"><IconRefresh class="w-4 h-4 mr-1"/> Regenerate</button>
                                                </div>
                                                
                                                <!-- Variant Selector (Image Only) -->
                                                <div v-if="currentTabParsed.slides_data[selectedSlideIndex].images && currentTabParsed.slides_data[selectedSlideIndex].images.length > 1" class="absolute bottom-4 left-4 h-16 flex gap-2 overflow-x-auto p-1 bg-white/50 dark:bg-black/20 rounded z-20 backdrop-blur-sm opacity-0 group-hover/imgview:opacity-100 transition-opacity">
                                                     <div v-for="(img, i) in currentTabParsed.slides_data[selectedSlideIndex].images" :key="i" class="relative group/thumb flex-shrink-0 w-20 h-full">
                                                         <div @click="selectMainImage(selectedSlideIndex, i)" class="w-full h-full rounded cursor-pointer border-2 transition-colors overflow-hidden" :class="(currentTabParsed.slides_data[selectedSlideIndex].selected_image_index || 0) === i ? 'border-blue-500' : 'border-transparent opacity-60 hover:opacity-100'">
                                                             <AuthenticatedImage :src="img.path" class="w-full h-full object-cover" />
                                                         </div>
                                                         <button @click.stop="handleDeleteSlideImage(selectedSlideIndex, i)" class="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-4 h-4 flex items-center justify-center opacity-0 group-hover/thumb:opacity-100 transition-opacity hover:bg-red-600 shadow-sm" title="Delete Variant">
                                                             <IconXMark class="w-3 h-3" />
                                                         </button>
                                                     </div>
                                                </div>
                                            </div>
                                        </div>

                                        <!-- Hybrid/Text Mode -->
                                        <div v-else class="flex-grow flex gap-6 h-full">
                                            <!-- Content Edit -->
                                            <div :class="(currentTabParsed.slides_data[selectedSlideIndex].layout === 'TitleImageBody' || currentTabParsed.mode === 'hybrid') ? 'w-1/2' : 'w-full'">
                                                <input v-model="currentTabParsed.slides_data[selectedSlideIndex].title" @blur="notebookStore.saveActive" class="text-3xl font-bold w-full bg-transparent border-none focus:ring-0 p-0 mb-4 text-gray-900 dark:text-gray-100 placeholder-gray-400" placeholder="Slide Title" />
                                                <textarea 
                                                    v-model="currentTabParsed.slides_data[selectedSlideIndex].bullets"
                                                    @blur="()=>{ currentTabParsed.slides_data[selectedSlideIndex].bullets = Array.isArray(currentTabParsed.slides_data[selectedSlideIndex].bullets) ? currentTabParsed.slides_data[selectedSlideIndex].bullets : currentTabParsed.slides_data[selectedSlideIndex].bullets.split('\n'); notebookStore.saveActive() }"
                                                    class="w-full h-64 bg-transparent border-none focus:ring-0 p-0 text-lg text-gray-700 dark:text-gray-300 resize-none list-disc"
                                                    placeholder="• Point 1&#10;• Point 2"
                                                ></textarea>
                                            </div>
                                            
                                            <!-- Visual Edit -->
                                            <div v-if="currentTabParsed.slides_data[selectedSlideIndex].layout === 'TitleImageBody' || currentTabParsed.mode === 'hybrid'" class="w-1/2 flex flex-col gap-2 relative">
                                                <div class="relative flex-grow bg-gray-100 dark:bg-gray-900 rounded-lg overflow-hidden border dark:border-gray-700 group/img">
                                                    <!-- Flip Logic for Hybrid Mode Visual -->
                                                    <div v-if="isCardFlipped" class="w-full h-full p-4 flex flex-col bg-gray-100 dark:bg-gray-800 absolute inset-0 z-20">
                                                        <div class="flex justify-between items-center mb-2">
                                                            <h3 class="text-xs font-bold uppercase text-gray-500">Edit Prompt</h3>
                                                            <button @click="isCardFlipped = false" class="p-1 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700"><IconXMark class="w-4 h-4"/></button>
                                                        </div>
                                                        <textarea v-model="localImagePrompt" class="flex-grow w-full text-xs bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded p-2 resize-none mb-2 font-mono"></textarea>
                                                        <button @click="handleGenerateFromFlip" class="btn btn-primary btn-sm w-full"><IconSparkles class="w-3 h-3 mr-1"/> Generate</button>
                                                    </div>

                                                    <AuthenticatedImage 
                                                        v-if="currentTabParsed.slides_data[selectedSlideIndex].images && currentTabParsed.slides_data[selectedSlideIndex].images.length > 0" 
                                                        :src="currentTabParsed.slides_data[selectedSlideIndex].images[currentTabParsed.slides_data[selectedSlideIndex].selected_image_index || 0].path" 
                                                        class="w-full h-full object-cover" 
                                                    />
                                                    <div v-else class="flex items-center justify-center h-full text-gray-400 italic flex-col gap-2">
                                                        <IconPhoto class="w-12 h-12 opacity-50" />
                                                        <span>No visual</span>
                                                    </div>
                                                    
                                                    <div class="absolute inset-0 bg-black/50 opacity-0 group-hover/img:opacity-100 transition-opacity flex items-center justify-center gap-2">
                                                        <button @click="isCardFlipped = true" class="btn btn-secondary btn-sm"><IconPencil class="w-4 h-4 mr-1"/> Edit Prompt</button>
                                                        <button @click="handleRegenerateSlideImage(selectedSlideIndex, currentTabParsed.slides_data[selectedSlideIndex].title)" class="btn btn-primary btn-sm"><IconRefresh class="w-4 h-4 mr-1"/> Regen</button>
                                                        <button @click="openImageViewer(currentTabParsed.slides_data[selectedSlideIndex].images[currentTabParsed.slides_data[selectedSlideIndex].selected_image_index || 0]?.path)" class="btn btn-secondary btn-sm"><IconEye class="w-4 h-4"/></button>
                                                    </div>
                                                </div>
                                                
                                                <!-- Variant Selector -->
                                                <div v-if="currentTabParsed.slides_data[selectedSlideIndex].images && currentTabParsed.slides_data[selectedSlideIndex].images.length > 1" class="h-16 flex gap-2 overflow-x-auto p-1 bg-white/50 dark:bg-black/20 rounded">
                                                     <div v-for="(img, i) in currentTabParsed.slides_data[selectedSlideIndex].images" :key="i" class="relative group/thumb flex-shrink-0 w-20 h-full">
                                                         <div @click="selectMainImage(selectedSlideIndex, i)" class="w-full h-full rounded cursor-pointer border-2 transition-colors overflow-hidden" :class="(currentTabParsed.slides_data[selectedSlideIndex].selected_image_index || 0) === i ? 'border-blue-500' : 'border-transparent opacity-60 hover:opacity-100'">
                                                             <AuthenticatedImage :src="img.path" class="w-full h-full object-cover" />
                                                         </div>
                                                         <button @click.stop="handleDeleteSlideImage(selectedSlideIndex, i)" class="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-4 h-4 flex items-center justify-center opacity-0 group-hover/thumb:opacity-100 transition-opacity hover:bg-red-600 shadow-sm" title="Delete Variant">
                                                             <IconXMark class="w-3 h-3" />
                                                         </button>
                                                     </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <div v-else class="text-gray-500">Select a slide to edit.</div>
                                </div>
                                
                                <!-- Prompt Area for Selected Slide -->
                                <div class="bg-white dark:bg-gray-800 border-t dark:border-gray-700 p-4">
                                    <div class="flex gap-2">
                                        <select v-model="generationAction" class="bg-gray-100 dark:bg-gray-700 border-none rounded px-3 py-2 text-sm font-bold uppercase text-gray-600 dark:text-gray-300">
                                            <option v-if="currentTabParsed.mode !== 'image_only'" value="update_slide_text">Update Text</option>
                                            <option value="images">Update Image</option>
                                        </select>
                                        <input v-model="aiPrompt" @keyup.enter="handleProcess" placeholder="Instructions for this slide..." class="input-field flex-grow" />
                                        <button @click="handleProcess" class="btn btn-primary"><IconSparkles class="w-4 h-4 mr-2" /> Update Slide</button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- PLANNER / BACKEND VIEW (Raw JSON / Code) -->
                        <div v-else-if="isSlidesNotebook && slideViewMode === 'planner'" class="h-full flex flex-col">
                             <div class="p-2 bg-gray-100 dark:bg-gray-800 border-b dark:border-gray-700 flex justify-between items-center">
                                 <h3 class="text-sm font-bold text-gray-600">Structure (JSON)</h3>
                                 <button @click="notebookStore.saveActive" class="btn-primary-flat btn-sm"><IconSave class="w-4 h-4 mr-1"/> Save JSON</button>
                             </div>
                             <CodeMirrorEditor v-model="currentTab.content" language="json" class="flex-grow" />
                        </div>

                        <!-- Markdown (Standard) -->
                        <div v-if="!isSlidesNotebook && currentTab.type === 'markdown'" class="h-full flex flex-col">
                            <div class="p-2 border-b dark:border-gray-700 flex justify-between items-center bg-white dark:bg-gray-900 flex-shrink-0">
                                <input v-model="currentTab.title" @blur="notebookStore.saveActive" class="bg-transparent border-none text-sm font-bold text-gray-700 dark:text-gray-300 focus:ring-0 px-2 w-full" placeholder="Tab Title" />
                                <div class="flex gap-1 bg-gray-100 dark:bg-gray-800 rounded p-0.5 border dark:border-gray-700">
                                     <button @click="isRenderMode = true" class="p-1 rounded" :class="isRenderMode ? 'bg-white dark:bg-gray-600 text-blue-600 shadow-sm' : 'text-gray-500'"><IconEye class="w-4 h-4" /></button>
                                     <button @click="isRenderMode = false" class="p-1 rounded" :class="!isRenderMode ? 'bg-white dark:bg-gray-600 text-blue-600 shadow-sm' : 'text-gray-500'"><IconPencil class="w-4 h-4" /></button>
                                </div>
                            </div>
                            <div class="flex-grow overflow-hidden relative">
                                 <div v-if="isRenderMode" class="absolute inset-0 overflow-y-auto p-8 custom-scrollbar"><MessageContentRenderer :content="currentTab.content" :key="currentTab.id + currentTab.content.length" class="prose dark:prose-invert max-w-none" /></div>
                                 <CodeMirrorEditor v-else v-model="currentTab.content" @blur="notebookStore.saveActive" class="h-full" />
                            </div>
                        </div>
                        
                        <!-- Gallery (Standard) -->
                        <div v-else-if="!isSlidesNotebook && currentTab.type === 'gallery'" class="h-full overflow-y-auto p-4 custom-scrollbar">
                             <div class="flex justify-between items-center mb-4 border-b border-gray-300 dark:border-gray-700 pb-2">
                                <input v-model="currentTab.title" @blur="notebookStore.saveActive" class="bg-transparent border-none text-lg font-bold p-0 focus:ring-0 w-full" placeholder="Gallery Title" />
                                <button v-if="isTtiAvailable" @click="handleRegenerateImages" class="btn-secondary btn-sm flex-shrink-0" title="Regenerate Images"><IconRefresh class="w-4 h-4 mr-1"/> Regenerate</button>
                             </div>
                             <div v-if="currentTab.images && currentTab.images.length > 0" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                                 <div v-for="(img, idx) in currentTab.images" :key="idx" class="relative group aspect-square rounded-lg overflow-hidden bg-gray-100 dark:bg-gray-800 border dark:border-gray-700 cursor-pointer" @click="openImageViewer(img.path)">
                                     <AuthenticatedImage :src="img.path" class="w-full h-full object-cover" />
                                     <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-2"><p class="text-white text-xs truncate">{{ img.prompt }}</p></div>
                                 </div>
                             </div>
                             <div v-else class="text-center text-gray-500 py-10 flex flex-col items-center"><p>No images generated.</p><button v-if="isTtiAvailable" @click="handleRegenerateImages" class="mt-2 text-blue-500 hover:underline">Generate Images</button></div>
                        </div>
                        
                        <!-- Standard Slides Viewer (Legacy) -->
                        <div v-else-if="!isSlidesNotebook && currentTab.type === 'slides' && currentTabParsed.slides_data" class="h-full overflow-y-auto p-8 custom-scrollbar bg-gray-100 dark:bg-gray-900">
                             <div class="mb-4">
                                <input v-model="currentTab.title" @blur="notebookStore.saveActive" class="w-full p-2 bg-transparent border-b text-xl font-bold" placeholder="Presentation Title" />
                             </div>
                             
                             <div v-for="(slide, idx) in currentTabParsed.slides_data" :key="slide.id" class="bg-white dark:bg-gray-800 p-6 shadow-md rounded-xl mb-8 border dark:border-gray-700 relative group">
                                 <div class="flex gap-6">
                                     <div :class="slide.layout === 'TitleImageBody' ? 'w-1/2' : 'w-full'">
                                         <h3 class="text-2xl font-bold mb-4 border-b pb-2 dark:border-gray-700">{{ slide.title }}</h3>
                                         <ul class="list-disc pl-5 space-y-2 text-gray-700 dark:text-gray-300">
                                             <li v-for="(point, i) in slide.bullets" :key="i">{{ point }}</li>
                                         </ul>
                                     </div>
                                     <div v-if="slide.layout === 'TitleImageBody'" class="w-1/2 flex flex-col gap-2">
                                         <div class="relative aspect-video bg-gray-200 dark:bg-gray-900 rounded-lg overflow-hidden border dark:border-gray-600">
                                             <AuthenticatedImage v-if="slide.images && slide.images.length > 0" :src="slide.images[slide.selected_image_index || 0].path" class="w-full h-full object-cover" />
                                             <div v-else class="flex items-center justify-center h-full text-gray-400 italic">No image generated</div>
                                         </div>
                                     </div>
                                 </div>
                             </div>
                        </div>
                    </div>
                    <div v-else class="flex-grow flex items-center justify-center text-gray-400">No tab selected.</div>
                    
                    <!-- Standard Processing Bar (Only for non-slide notebooks) -->
                    <div v-if="!isSlidesNotebook" class="p-3 border-t dark:border-gray-700 bg-white dark:bg-gray-900 flex-shrink-0 z-20">
                        <div class="flex items-center gap-2 mb-2 overflow-x-auto pb-1 custom-scrollbar">
                            <span class="text-[10px] font-bold text-gray-400 uppercase flex-shrink-0 tracking-wider">Input Context</span>
                            <div v-for="tab in activeNotebook.tabs" :key="'ctx-'+tab.id" @click="toggleInputSelection(tab.id)" class="px-2 py-0.5 rounded text-[10px] cursor-pointer border transition-colors select-none whitespace-nowrap flex-shrink-0 uppercase font-bold" :class="selectedInputTabs.has(tab.id) ? 'bg-blue-50 border-blue-200 text-blue-600' : 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-500'">{{ tab.title }}</div>
                        </div>
                        <div class="flex gap-2 items-center">
                            <div class="relative flex-grow">
                                <input v-model="aiPrompt" placeholder="Describe what you want to do..." class="input-field w-full pr-32 !text-sm" @keyup.enter="handleProcess" />
                                <div class="absolute right-1 top-1 bottom-1 flex items-center">
                                    <select v-model="generationAction" class="bg-gray-100 dark:bg-gray-700 border-none text-[10px] rounded px-2 py-1 outline-none cursor-pointer text-gray-600 dark:text-gray-300 font-bold uppercase h-full hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">
                                        <option v-for="action in availableActions" :key="action.value" :value="action.value">{{ action.label }}</option>
                                    </select>
                                </div>
                            </div>
                            <div class="flex items-center"><input type="checkbox" id="modify-tab" v-model="modifyCurrentTab" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"><label for="modify-tab" class="ml-1 text-[10px] uppercase font-bold text-gray-500 cursor-pointer select-none">Update Active</label></div>
                            <button @click="handleProcess" :disabled="!!activeTask" class="btn btn-primary gap-2 w-20 flex-shrink-0 justify-center"><IconSparkles class="w-4 h-4" /> Go</button>
                        </div>
                    </div>
                </div>

                <div class="w-64 flex-shrink-0 flex flex-col bg-gray-50 dark:bg-gray-900 border-l dark:border-gray-700">
                    <div class="p-3 border-b dark:border-gray-700 flex justify-between items-center flex-shrink-0"><span class="font-black text-[10px] uppercase text-gray-500 tracking-widest">Sources</span><div class="flex gap-1"><button @click="triggerFileUpload" class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded text-gray-500" title="Upload File"><IconArrowUpTray class="w-4 h-4"/></button><input type="file" ref="fileInput" @change="handleFileSelect" multiple class="hidden"><button @click="handleScrape" class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded text-gray-500" title="Scrape URL"><IconWeb class="w-4 h-4"/></button></div></div>
                    <div class="flex-grow overflow-y-auto p-2 space-y-2 custom-scrollbar">
                         <div v-for="source in activeNotebook.artefacts" :key="source.filename" class="p-2.5 bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 shadow-sm group hover:shadow-md transition-shadow">
                            <div class="flex items-center justify-between mb-2"><div class="flex items-center gap-2 min-w-0"><IconFileText class="w-3.5 h-3.5 text-blue-400 shrink-0" /><span class="text-xs truncate font-bold text-gray-700 dark:text-gray-300" :title="source.filename">{{ source.filename }}</span></div><div class="flex items-center"><button @click="viewSource(source)" class="text-gray-400 hover:text-blue-500 mr-1 opacity-0 group-hover:opacity-100 transition-opacity" title="View Content"><IconEye class="w-3.5 h-3.5" /></button><button @click="removeSource(source.filename)" class="text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"><IconXMark class="w-3.5 h-3.5" /></button></div></div>
                            <button @click="toggleSource(source)" class="w-full flex items-center justify-between text-[9px] font-bold uppercase tracking-tighter px-2 py-1 rounded transition-colors" :class="source.is_loaded ? 'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-300' : 'bg-gray-100 dark:bg-gray-700 text-gray-500'"><span>{{ source.is_loaded ? 'Active' : 'Inactive' }}</span><IconCheckCircle v-if="source.is_loaded" class="w-3 h-3"/><IconCircle v-else class="w-3 h-3"/></button>
                         </div>
                         <div v-if="activeNotebook.artefacts.length === 0" class="text-center py-10 text-[10px] uppercase font-bold text-gray-400 opacity-50 italic px-4">No sources added.</div>
                    </div>
                </div>
            </div>
        </div>
        <div v-else class="h-full flex flex-col items-center justify-center text-gray-500 dark:text-gray-400"><IconServer class="w-16 h-16 mb-4 text-gray-300 dark:text-gray-600" /><p class="text-lg font-medium">Select a notebook from the sidebar to begin.</p><button @click="createNotebook" class="mt-4 btn btn-primary flex items-center gap-2"><IconPlus class="w-4 h-4" /> Create New Notebook</button></div>
    </div>
</template>
