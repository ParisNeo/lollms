<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useUiStore } from '../stores/ui';
import { useNotebookStore } from '../stores/notebooks';
import { useDiscussionsStore } from '../stores/discussions';
import { useTasksStore } from '../stores/tasks';
import { storeToRefs } from 'pinia';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import CodeMirrorEditor from '../components/ui/CodeMirrorComponent/index.vue';
import MessageContentRenderer from '../components/ui/MessageContentRenderer/MessageContentRenderer.vue';
import apiClient from '../services/api';

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

const { notebooks, activeNotebook } = storeToRefs(notebookStore);
const { tasks } = storeToRefs(tasksStore);

const aiPrompt = ref('');
const isDraggingOver = ref(false);
const fileInput = ref(null);
const isRenderMode = ref(true); // Default to render mode

const activeTask = computed(() => {
    if (!activeNotebook.value) return null;
    return tasks.value.find(t => t.name.includes(activeNotebook.value.id) && (t.status === 'running' || t.status === 'pending'));
});

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

async function sendToChat() {
    if (!activeNotebook.value) return;
    const { confirmed, value: targetId } = await uiStore.showConfirmation({
        title: 'Send to Chat',
        message: 'Append notebook content to discussion context:',
        inputType: 'select',
        inputOptions: Object.values(discussionsStore.discussions).map(d => ({ text: d.title, value: d.id })),
        confirmText: 'Send'
    });
    if (confirmed && targetId) {
        await discussionsStore.appendToDataZone({ discussionId: targetId, content: activeNotebook.value.content });
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

function triggerFileUpload() {
    fileInput.value.click();
}

async function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    if (!activeNotebook.value || files.length === 0) return;
    uiStore.addNotification(`Uploading ${files.length} source(s)...`, 'info');
    await Promise.all(files.map(f => notebookStore.uploadSource(f)));
    e.target.value = ''; // Reset input
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
    if (!activeNotebook.value) return;
    const { confirmed, value: title } = await uiStore.showConfirmation({
        title: 'Convert to Source',
        message: 'Enter a title for the new source artefact:',
        inputType: 'text',
        inputPlaceholder: 'My Notebook Notes',
        confirmText: 'Convert'
    });
    
    if (confirmed && title) {
        await notebookStore.createTextArtefact(title, activeNotebook.value.content);
    }
}

// Auto-refresh editor if AI finishes a task related to this notebook
watch(tasks, (newTasks) => {
    if (activeNotebook.value) {
        // Check if any task associated with this notebook ID completed
        const completedTask = newTasks.find(t => 
            t.status === 'completed' && 
            t.result && 
            t.result.notebook_id === activeNotebook.value.id
        );
        
        if (completedTask) {
             notebookStore.selectNotebook(activeNotebook.value.id);
             // Optional: clear the task result from tracking to prevent repeated refreshes if needed, 
             // but `watch` handles changes, so duplicates shouldn't be an issue unless tasks array mutates unexpectedly.
        }
    }
}, { deep: true });

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
                        <button @click.stop="deleteNotebook(nb.id)" class="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400"><IconTrash class="w-4 h-4" /></button>
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

                <div class="p-3 border-b dark:border-gray-700 flex items-center justify-between shadow-sm">
                    <div class="flex items-center gap-3 flex-grow">
                        <input v-model="activeNotebook.title" @blur="notebookStore.saveActive" class="text-lg font-black bg-transparent border-none focus:ring-0 w-full" />
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                        <div class="bg-gray-100 dark:bg-gray-800 p-1 rounded-lg flex gap-1">
                            <button @click="isRenderMode = true" class="p-1.5 rounded transition-colors" :class="isRenderMode ? 'bg-white dark:bg-gray-600 shadow-sm text-blue-600' : 'text-gray-500'" title="View">
                                <IconEye class="w-4 h-4" />
                            </button>
                            <button @click="isRenderMode = false" class="p-1.5 rounded transition-colors" :class="!isRenderMode ? 'bg-white dark:bg-gray-600 shadow-sm text-blue-600' : 'text-gray-500'" title="Edit">
                                <IconPencil class="w-4 h-4" />
                            </button>
                        </div>
                        <div class="h-6 w-px bg-gray-300 dark:bg-gray-700 mx-1"></div>
                        <button @click="handleRefresh" class="btn btn-secondary btn-sm" title="Refresh">
                            <IconRefresh class="w-4 h-4" />
                        </button>
                        <button @click="handleConvertToSource" class="btn btn-secondary btn-sm gap-2" title="Save content as a new source">
                            <IconArchiveBox class="w-4 h-4" /> Src
                        </button>
                        <button @click="sendToChat" class="btn btn-secondary btn-sm gap-2"><IconSend class="w-4 h-4" /> Chat</button>
                        <button @click="notebookStore.saveActive" class="btn btn-primary btn-sm gap-2"><IconSave class="w-4 h-4" /> Save</button>
                    </div>
                </div>

                <div class="flex-grow flex min-h-0 relative">
                    <div class="flex-grow flex flex-col min-w-0 border-r dark:border-gray-700">
                        <div v-if="activeTask" class="px-4 py-2 bg-blue-50 dark:bg-blue-900/40 border-b flex items-center justify-between gap-4">
                            <span class="text-xs font-black text-blue-700 dark:text-blue-300 truncate uppercase">{{ activeTask.description }}</span>
                            <div class="w-32 h-1.5 bg-blue-200 dark:bg-blue-800 rounded-full overflow-hidden"><div class="h-full bg-blue-600 transition-all duration-300" :style="{ width: activeTask.progress + '%' }"></div></div>
                        </div>

                        <div class="flex-grow overflow-hidden relative">
                             <!-- Rendered View -->
                             <div v-if="isRenderMode" class="absolute inset-0 overflow-y-auto p-8 custom-scrollbar">
                                 <MessageContentRenderer :content="activeNotebook.content" class="prose dark:prose-invert max-w-none" />
                             </div>
                             
                             <!-- Editor View -->
                            <CodeMirrorEditor v-else v-model="activeNotebook.content" @blur="notebookStore.saveActive" class="h-full" />
                        </div>
                        
                        <div class="p-4 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                            <div class="max-w-4xl mx-auto flex gap-2 items-center">
                                <input v-model="aiPrompt" placeholder="Instruct AI to process this notebook..." class="input-field flex-grow shadow-inner" @keyup.enter="notebookStore.processWithAi(aiPrompt); aiPrompt = ''" />
                                <button @click="notebookStore.processWithAi(aiPrompt); aiPrompt = ''" :disabled="!!activeTask" class="btn btn-primary gap-2 min-w-[120px]"><IconSparkles class="w-5 h-5" />Process</button>
                            </div>
                        </div>
                    </div>

                    <!-- Independent Sources Sidebar -->
                    <div class="w-80 flex-shrink-0 flex flex-col bg-gray-50/50 dark:bg-gray-900/30">
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
                                  class="p-3 bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 shadow-sm group">
                                <div class="flex items-center justify-between mb-2">
                                    <div class="flex items-center gap-2 min-w-0">
                                        <IconFileText class="w-4 h-4 text-blue-400 shrink-0" />
                                        <span class="text-xs truncate font-bold" :title="source.filename">{{ source.filename }}</span>
                                    </div>
                                    <button @click="removeSource(source.filename)" class="text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100"><IconXMark class="w-4 h-4" /></button>
                                </div>
                                <button @click="toggleSource(source)" class="w-full flex items-center justify-between text-[10px] font-bold uppercase tracking-tighter px-2 py-1 rounded transition-colors"
                                        :class="source.is_loaded ? 'bg-blue-50 text-blue-600' : 'bg-gray-100 text-gray-400'">
                                    <span>{{ source.is_loaded ? 'Loaded' : 'Deactivated' }}</span>
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
