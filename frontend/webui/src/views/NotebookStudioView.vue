<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import { useUiStore } from '../stores/ui';
import { useNotebookStore } from '../stores/notebooks';
import { useDiscussionsStore } from '../stores/discussions';
import { useTasksStore } from '../stores/tasks';
import { useAuthStore } from '../stores/auth';
import { storeToRefs } from 'pinia';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import CodeMirrorEditor from '../components/ui/CodeMirrorComponent/index.vue';
import MessageContentRenderer from '../components/ui/MessageContentRenderer/MessageContentRenderer.vue';
import AuthenticatedImage from '../components/ui/AuthenticatedImage.vue';
import apiClient from '../services/api';
import useEventBus from '../services/eventBus';

// Icons
import IconPlus from '../assets/icons/IconPlus.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconPhoto from '../assets/icons/IconPhoto.vue';
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

const uiStore = useUiStore();
const notebookStore = useNotebookStore();
const discussionsStore = useDiscussionsStore();
const tasksStore = useTasksStore();
const authStore = useAuthStore();
const { on, off } = useEventBus();

const { notebooks, activeNotebook } = storeToRefs(notebookStore);
const { tasks } = storeToRefs(tasksStore);
const { user } = storeToRefs(authStore);

const aiPrompt = ref('');
const isDraggingOver = ref(false);
const fileInput = ref(null);
const isRenderMode = ref(true); 
const activeTabId = ref(null);
const selectedInputTabs = ref(new Set());
const generationType = ref('text');
const mode = ref('general');
const logsContainer = ref(null);

const isTtiAvailable = computed(() => !!user.value?.tti_binding_model_name);

const availableGenerationTypes = computed(() => {
    if (mode.value === 'story') {
        return [
            { value: 'story_structure', label: 'Update Structure' },
            { value: 'story_chapter', label: 'Write Chapter' },
            { value: 'text', label: 'Free Text' }
        ];
    }
    return [
        { value: 'text', label: 'Text' },
        { value: 'images', label: 'Images' },
        { value: 'presentation', label: 'Slides' }
    ];
});

// Identify task related to THIS notebook
const activeTask = computed(() => {
    if (!activeNotebook.value) return null;
    return tasks.value.find(t => 
        t.name.includes(activeNotebook.value.id) && 
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
            // Default to last tab
            activeTabId.value = nb.tabs[nb.tabs.length - 1].id;
        }
    } else if (nb && (!nb.tabs || nb.tabs.length === 0)) {
        notebookStore.addTab();
    }
}, { immediate: true });

// Auto-switch tab if a new tab appears while a task is running (indicating creation)
watch(() => activeNotebook.value?.tabs?.length, (newLen, oldLen) => {
    if (newLen > oldLen && activeTask.value) {
        // Switch to the newly created tab (last one)
        activeTabId.value = activeNotebook.value.tabs[newLen - 1].id;
    }
});

// Auto-scroll logs
watch(() => activeTask.value?.logs?.length, () => {
    nextTick(() => {
        if (logsContainer.value) {
            logsContainer.value.scrollTop = logsContainer.value.scrollHeight;
        }
    });
}, { deep: true });

// Refresh on completion
watch(tasks, (newTasks) => {
    if (activeNotebook.value) {
        const completedTask = newTasks.find(t => 
            t.status === 'completed' && 
            t.result && 
            t.result.notebook_id === activeNotebook.value.id
        );
        
        if (completedTask) {
             // Refresh full state to get final content updates
             notebookStore.fetchNotebooks().then(() => {
                 notebookStore.selectNotebook(activeNotebook.value.id);
                 // If we switched tabs during generation, stay there, otherwise go to new one
                 if (activeNotebook.value.tabs.length > 0 && !activeNotebook.value.tabs.find(t => t.id === activeTabId.value)) {
                     activeTabId.value = activeNotebook.value.tabs[activeNotebook.value.tabs.length - 1].id;
                 }
             });
        }
    }
}, { deep: true });


async function createNotebook() {
    try {
        const res = await apiClient.post('/api/notebooks', { title: 'New Research', content: '' });
        await notebookStore.fetchNotebooks();
        await notebookStore.selectNotebook(res.data.id);
    } catch (e) {
        uiStore.addNotification("Failed to create notebook.", "error");
    }
}

async function deleteNotebook(id) {
    if (await uiStore.showConfirmation({ title: 'Delete Notebook?' })) {
        await notebookStore.selectNotebook(id);
        await apiClient.delete(`/api/notebooks/${id}`);
        await notebookStore.fetchNotebooks();
        notebookStore.activeNotebook = null;
    }
}

async function toggleSource(source) {
    source.is_loaded = !source.is_loaded;
    await notebookStore.saveActive();
}

async function removeSource(filename) {
    if (await uiStore.showConfirmation({ title: 'Remove Source?' })) {
        activeNotebook.value.artefacts = activeNotebook.value.artefacts.filter(a => a.filename !== filename);
        await notebookStore.saveActive();
    }
}

async function viewSource(source) {
    uiStore.openModal('sourceViewer', { 
        title: source.filename, 
        content: source.content,
        language: 'markdown'
    });
}

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

async function handleDrop(e) {
    isDraggingOver.value = false;
    const files = Array.from(e.dataTransfer.files);
    if (!activeNotebook.value || files.length === 0) return;
    uiStore.addNotification(`Uploading ${files.length} source(s)...`, 'info');
    await Promise.all(files.map(f => notebookStore.uploadSource(f)));
}

function triggerFileUpload() { fileInput.value.click(); }
async function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    if (!activeNotebook.value || files.length === 0) return;
    uiStore.addNotification(`Uploading ${files.length} source(s)...`, 'info');
    await Promise.all(files.map(f => notebookStore.uploadSource(f)));
    e.target.value = ''; 
}

async function handleScrape() {
    if (!activeNotebook.value) return;
    const { confirmed, value: url } = await uiStore.showConfirmation({
        title: 'Scrape URL',
        message: 'Enter URL to scrape content from:',
        inputType: 'text',
        inputPlaceholder: 'https://example.com',
        confirmText: 'Scrape'
    });
    
    if (confirmed && url) {
        await notebookStore.scrapeUrl(url);
    }
}

async function handleRefresh() {
    if (activeNotebook.value) {
        await notebookStore.selectNotebook(activeNotebook.value.id);
        uiStore.addNotification("Notebook refreshed.", "success");
    }
}

async function handleConvertToSource() {
    if (!currentTab.value) return;
    const { confirmed, value: title } = await uiStore.showConfirmation({
        title: 'Convert to Source',
        message: 'Enter a title for the new source artefact:',
        inputType: 'text',
        inputPlaceholder: 'My Tab Notes',
        confirmText: 'Convert'
    });
    
    if (confirmed && title) {
        const content = currentTab.value.content || (currentTab.value.type === 'gallery' ? JSON.stringify(currentTab.value.images) : '');
        await notebookStore.createTextArtefact(title, content);
    }
}

function handleTabClick(tabId) {
    activeTabId.value = tabId;
}

async function handleAddTab() {
    notebookStore.addTab();
    // Wait for update then select new tab
    setTimeout(() => {
         if(activeNotebook.value.tabs.length > 0) activeTabId.value = activeNotebook.value.tabs[activeNotebook.value.tabs.length-1].id;
    }, 100);
}

function handleCloseTab(tabId) {
    if (confirm("Delete this tab?")) {
        notebookStore.removeTab(tabId);
        if (activeTabId.value === tabId) {
             activeTabId.value = activeNotebook.value.tabs.length > 0 ? activeNotebook.value.tabs[0].id : null;
        }
    }
}

function toggleInputSelection(tabId) {
    if (selectedInputTabs.value.has(tabId)) selectedInputTabs.value.delete(tabId);
    else selectedInputTabs.value.add(tabId);
}

function handleProcess() {
    if (!aiPrompt.value.trim()) return;
    const inputs = Array.from(selectedInputTabs.value);
    notebookStore.processWithAi(aiPrompt.value, inputs, generationType.value);
    aiPrompt.value = '';
    selectedInputTabs.value.clear();
}

function handleAutoRename() {
    notebookStore.generateTitle();
}

function openImageViewer(src) {
    uiStore.openImageViewer({ imageList: [{ src, prompt: 'Notebook Image' }], startIndex: 0 });
}

onMounted(notebookStore.fetchNotebooks);
</script>

<template>
    <PageViewLayout title="Notebook Studio" :title-icon="IconServer">
        <template #sidebar>
            <div class="p-2 space-y-4">
                <button @click="createNotebook" class="btn btn-primary w-full flex items-center justify-center gap-2 py-3">
                    <IconPlus class="w-5 h-5" /> New Notebook
                </button>
                <div class="space-y-1">
                    <div v-for="nb in notebooks" :key="nb.id" @click="notebookStore.selectNotebook(nb.id)"
                         class="p-3 rounded-xl cursor-pointer flex justify-between items-center group transition-all"
                         :class="activeNotebook?.id === nb.id ? 'bg-blue-600 text-white' : 'hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300'">
                        <span class="truncate font-semibold text-sm">{{ nb.title }}</span>
                        <div class="flex items-center">
                            <button @click.stop="deleteNotebook(nb.id)" class="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400"><IconTrash class="w-4 h-4" /></button>
                        </div>
                    </div>
                </div>
            </div>
        </template>

        <template #main>
            <div v-if="activeNotebook" class="h-full flex flex-col bg-white dark:bg-gray-900 relative"
                 @dragover.prevent="isDraggingOver = true" @dragleave="isDraggingOver = false" @drop.prevent="handleDrop">
                
                <div v-if="isDraggingOver" class="absolute inset-0 bg-blue-500/10 border-4 border-dashed border-blue-500 rounded-lg z-50 flex items-center justify-center m-4 pointer-events-none">
                    <p class="text-2xl font-black text-blue-600 uppercase">Drop Research Sources Here</p>
                </div>

                <!-- Header & Tabs -->
                <div class="bg-gray-100 dark:bg-gray-800 border-b dark:border-gray-700 pt-2 px-2 flex flex-col gap-2">
                     <div class="flex items-center justify-between px-2 pb-2">
                        <div class="flex items-center gap-2 flex-grow">
                             <!-- Global Task Indicator in Notebook Header -->
                             <div v-if="activeTask" class="flex items-center gap-2 mr-4 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 px-3 py-1 rounded-full animate-pulse">
                                 <IconAnimateSpin class="w-4 h-4 animate-spin" />
                                 <span class="text-xs font-bold uppercase tracking-wide">Processing... {{ activeTask.progress }}%</span>
                             </div>

                             <input v-model="activeNotebook.title" @blur="notebookStore.saveActive" class="text-lg font-black bg-transparent border-none focus:ring-0 w-full" />
                             <!-- AI Rename Button -->
                             <button @click="handleAutoRename" class="p-1 rounded hover:bg-purple-100 dark:hover:bg-purple-900/50 text-purple-500" title="Auto-rename with AI">
                                 <IconSparkles class="w-4 h-4" />
                             </button>
                             <!-- MODE SWITCHER -->
                             <div class="bg-white dark:bg-gray-700 rounded-lg p-0.5 flex text-xs font-bold border dark:border-gray-600 flex-shrink-0">
                                 <button @click="mode = 'general'" class="px-2 py-1 rounded-md transition-colors" :class="mode === 'general' ? 'bg-blue-100 text-blue-700' : 'text-gray-500'">General</button>
                                 <button @click="mode = 'story'" class="px-2 py-1 rounded-md transition-colors" :class="mode === 'story' ? 'bg-purple-100 text-purple-700' : 'text-gray-500'">Story</button>
                             </div>
                        </div>
                        <div class="flex items-center gap-2">
                            <button @click="handleRefresh" class="btn btn-secondary btn-sm" title="Refresh">
                                <IconRefresh class="w-4 h-4" />
                            </button>
                            <button @click="handleConvertToSource" class="btn btn-secondary btn-sm gap-2" title="Save content as a new source">
                                <IconArchiveBox class="w-4 h-4" /> Src
                            </button>
                            <button @click="sendToChat" class="btn btn-secondary btn-sm gap-2"><IconSend class="w-4 h-4" /> To Chat</button>
                            <button @click="notebookStore.saveActive" class="btn btn-primary btn-sm gap-2"><IconSave class="w-4 h-4" /> Save</button>
                        </div>
                    </div>
                    
                    <div class="flex items-center gap-1 overflow-x-auto custom-scrollbar pb-0">
                         <div v-for="tab in activeNotebook.tabs" :key="tab.id" 
                              class="group relative flex items-center gap-2 px-4 py-2 rounded-t-lg cursor-pointer transition-colors border-t border-x border-transparent hover:bg-gray-200 dark:hover:bg-gray-700"
                              :class="activeTabId === tab.id ? 'bg-white dark:bg-gray-900 border-gray-300 dark:border-gray-600 text-blue-600 dark:text-blue-400 font-bold' : 'text-gray-500 bg-gray-100 dark:bg-gray-800 border-b border-gray-300 dark:border-gray-600'">
                              <span @click="handleTabClick(tab.id)" class="text-xs uppercase tracking-wide truncate max-w-[150px]">{{ tab.title }}</span>
                              <button @click.stop="handleCloseTab(tab.id)" class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500"><IconXMark class="w-3 h-3" /></button>
                         </div>
                         <button @click="handleAddTab" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 mb-1"><IconPlus class="w-4 h-4" /></button>
                    </div>
                </div>

                <div class="flex-grow flex min-h-0 relative">
                    <!-- Main Content (Editor/Viewer) -->
                    <div class="flex-grow flex flex-col min-w-0 border-r dark:border-gray-700 relative">
                        
                        <!-- Console Overlay for Active Task -->
                        <div v-if="activeTask" class="absolute inset-0 z-30 bg-white/95 dark:bg-gray-900/95 flex flex-col backdrop-blur-sm">
                            <div class="p-4 border-b dark:border-gray-700 flex items-center justify-between shadow-sm bg-white dark:bg-gray-800">
                                <div class="flex items-center gap-3">
                                    <IconAnimateSpin class="w-5 h-5 text-blue-600 animate-spin" />
                                    <div>
                                        <h3 class="font-bold text-sm text-gray-900 dark:text-gray-100">{{ activeTask.name }}</h3>
                                        <p class="text-xs text-gray-500 dark:text-gray-400">{{ activeTask.description }}</p>
                                    </div>
                                </div>
                                <div class="text-xs font-mono text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-2 py-1 rounded">
                                    {{ activeTask.progress }}%
                                </div>
                            </div>
                            <div class="flex-grow overflow-hidden relative">
                                <div ref="logsContainer" class="absolute inset-0 overflow-y-auto p-4 font-mono text-xs text-gray-600 dark:text-gray-300 space-y-1">
                                    <div v-for="(log, idx) in activeTask.logs" :key="idx" class="flex gap-2">
                                        <span class="text-gray-400 shrink-0">[{{ new Date(log.timestamp).toLocaleTimeString() }}]</span>
                                        <span :class="{'text-red-500': log.level === 'ERROR', 'text-yellow-500': log.level === 'WARNING'}">{{ log.message }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div v-if="currentTab" class="flex-grow overflow-hidden flex flex-col relative h-full">
                            <!-- Markdown Editor/Viewer -->
                            <div v-if="currentTab.type === 'markdown'" class="h-full flex flex-col">
                                <div class="p-2 border-b dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-800/50">
                                    <input v-model="currentTab.title" @blur="notebookStore.saveActive" class="bg-transparent border-none text-sm font-bold text-gray-700 dark:text-gray-300 focus:ring-0" placeholder="Tab Title" />
                                    <div class="flex gap-1 bg-white dark:bg-gray-700 rounded p-0.5 border dark:border-gray-600">
                                         <button @click="isRenderMode = true" class="p-1 rounded" :class="isRenderMode ? 'bg-blue-100 text-blue-600' : 'text-gray-500'"><IconEye class="w-4 h-4" /></button>
                                         <button @click="isRenderMode = false" class="p-1 rounded" :class="!isRenderMode ? 'bg-blue-100 text-blue-600' : 'text-gray-500'"><IconPencil class="w-4 h-4" /></button>
                                    </div>
                                </div>
                                <div class="flex-grow overflow-hidden relative">
                                     <div v-if="isRenderMode" class="absolute inset-0 overflow-y-auto p-8 custom-scrollbar">
                                         <MessageContentRenderer :content="currentTab.content" class="prose dark:prose-invert max-w-none" />
                                     </div>
                                     <CodeMirrorEditor v-else v-model="currentTab.content" @blur="notebookStore.saveActive" class="h-full" />
                                </div>
                            </div>
                            
                            <!-- Gallery Viewer -->
                            <div v-else-if="currentTab.type === 'gallery'" class="h-full overflow-y-auto p-4 custom-scrollbar">
                                 <input v-model="currentTab.title" @blur="notebookStore.saveActive" class="w-full mb-4 bg-transparent border-b border-gray-300 dark:border-gray-700 text-lg font-bold p-2" placeholder="Gallery Title" />
                                 <div v-if="currentTab.images && currentTab.images.length > 0" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                                     <div v-for="(img, idx) in currentTab.images" :key="idx" class="relative group aspect-square rounded-lg overflow-hidden bg-gray-100 dark:bg-gray-800 border dark:border-gray-700 cursor-pointer" @click="openImageViewer(img.path)">
                                         <AuthenticatedImage :src="img.path" class="w-full h-full object-cover" />
                                         <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-2">
                                             <p class="text-white text-xs truncate">{{ img.prompt }}</p>
                                         </div>
                                     </div>
                                 </div>
                                 <div v-else class="text-center text-gray-500 py-10">No images generated.</div>
                            </div>
                            
                            <!-- Slides Viewer -->
                            <div v-else-if="currentTab.type === 'slides'" class="h-full overflow-hidden flex flex-col">
                                <input v-model="currentTab.title" @blur="notebookStore.saveActive" class="w-full p-2 bg-transparent border-b text-lg font-bold" placeholder="Presentation Title" />
                                <div class="flex-grow overflow-y-auto p-8 custom-scrollbar bg-gray-100 dark:bg-gray-900">
                                     <!-- Simple vertical slide render for now -->
                                     <div v-for="(slide, idx) in currentTab.content.split('---')" :key="idx" class="bg-white dark:bg-gray-800 p-8 shadow-lg rounded-xl mb-8 min-h-[400px] prose dark:prose-invert max-w-none border dark:border-gray-700">
                                         <MessageContentRenderer :content="slide.trim()" />
                                     </div>
                                </div>
                            </div>
                        </div>
                        <div v-else class="flex-grow flex items-center justify-center text-gray-400">No tab selected.</div>
                        
                        <!-- AI Process Bar -->
                        <div class="p-4 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                            <div class="flex items-center gap-2 mb-2 overflow-x-auto pb-1">
                                <span class="text-xs font-bold text-gray-500 uppercase">Input Context:</span>
                                <div v-for="tab in activeNotebook.tabs" :key="'ctx-'+tab.id" 
                                     @click="toggleInputSelection(tab.id)"
                                     class="px-2 py-1 rounded text-xs cursor-pointer border transition-colors select-none whitespace-nowrap"
                                     :class="selectedInputTabs.has(tab.id) ? 'bg-blue-100 border-blue-300 text-blue-700' : 'bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-500'">
                                    {{ tab.title }}
                                </div>
                            </div>
                            
                            <div class="flex gap-2">
                                <div class="relative flex-grow">
                                    <input 
                                        v-model="aiPrompt" 
                                        :placeholder="mode === 'story' ? 'Describe the chapter or structural change...' : 'Ask AI to process selected tabs...'" 
                                        class="input-field w-full pr-32" 
                                        @keyup.enter="handleProcess" 
                                    />
                                    <select v-model="generationType" class="absolute right-1 top-1 bottom-1 bg-gray-100 dark:bg-gray-700 border-none text-xs rounded px-2 outline-none cursor-pointer text-gray-600 dark:text-gray-300 font-bold uppercase">
                                        <option v-for="t in availableGenerationTypes" :key="t.value" :value="t.value" :disabled="t.value === 'images' && !isTtiAvailable">
                                            {{ t.label }}
                                        </option>
                                    </select>
                                </div>
                                <button @click="handleProcess" :disabled="!!activeTask" class="btn btn-primary gap-2 w-24">
                                    <IconSparkles class="w-4 h-4" /> Go
                                </button>
                            </div>
                            <p v-if="mode === 'story'" class="text-[10px] text-gray-400 mt-1">
                                Tip: Use <code>&lt;ScanForInfos&gt;query&lt;/ScanForInfos&gt;</code> in prompt or context to trigger agentic lookup.
                            </p>
                        </div>
                    </div>

                    <!-- Independent Sources Sidebar -->
                    <div class="w-72 flex-shrink-0 flex flex-col bg-gray-50/50 dark:bg-gray-900/30 border-l dark:border-gray-700">
                        <div class="p-3 border-b dark:border-gray-700 flex justify-between items-center">
                             <span class="font-black text-[10px] uppercase text-gray-500 tracking-widest">Research Sources</span>
                             <div class="flex gap-1">
                                <button @click="triggerFileUpload" class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded text-gray-500" title="Upload File">
                                    <IconArrowUpTray class="w-4 h-4"/>
                                </button>
                                <input type="file" ref="fileInput" @change="handleFileSelect" multiple class="hidden">
                                <button @click="handleScrape" class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded text-gray-500" title="Scrape URL">
                                    <IconWeb class="w-4 h-4"/>
                                </button>
                             </div>
                        </div>
                        <div class="flex-grow overflow-y-auto p-2 space-y-2 custom-scrollbar">
                             <div v-for="source in activeNotebook.artefacts" :key="source.filename" 
                                  class="p-3 bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 shadow-sm group hover:shadow-md transition-shadow">
                                <div class="flex items-center justify-between mb-2">
                                    <div class="flex items-center gap-2 min-w-0">
                                        <IconFileText class="w-4 h-4 text-blue-400 shrink-0" />
                                        <span class="text-xs truncate font-bold" :title="source.filename">{{ source.filename }}</span>
                                    </div>
                                    <div class="flex items-center">
                                        <button @click="viewSource(source)" class="text-gray-400 hover:text-blue-500 mr-1 opacity-0 group-hover:opacity-100 transition-opacity" title="View Content">
                                            <IconEye class="w-3.5 h-3.5" />
                                        </button>
                                        <button @click="removeSource(source.filename)" class="text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"><IconXMark class="w-3.5 h-3.5" /></button>
                                    </div>
                                </div>
                                <button @click="toggleSource(source)" class="w-full flex items-center justify-between text-[10px] font-bold uppercase tracking-tighter px-2 py-1.5 rounded transition-colors"
                                        :class="source.is_loaded ? 'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-300' : 'bg-gray-100 dark:bg-gray-700 text-gray-500'">
                                    <span>{{ source.is_loaded ? 'Active' : 'Inactive' }}</span>
                                    <IconCheckCircle v-if="source.is_loaded" class="w-3 h-3"/>
                                    <IconCircle v-else class="w-3 h-3"/>
                                </button>
                             </div>
                             <div v-if="activeNotebook.artefacts.length === 0" class="text-center py-10 text-[10px] uppercase font-bold text-gray-400 opacity-50 italic px-4">
                                Drop files here or use buttons above to add sources.
                             </div>
                        </div>
                    </div>
                </div>
            </div>
            <div v-else class="h-full flex items-center justify-center text-gray-500 italic text-sm">Select or create a notebook to begin.</div>
        </template>
    </PageViewLayout>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>
