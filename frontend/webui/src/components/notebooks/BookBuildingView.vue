<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useNotebookStore } from '../../stores/notebooks';
import { useUiStore } from '../../stores/ui';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';

import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconSave from '../../assets/icons/IconSave.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';

const props = defineProps({
    notebook: { type: Object, required: true }
});

const notebookStore = useNotebookStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();
const { tasks } = storeToRefs(tasksStore);

const activeTabId = ref(null);
const isRenderMode = ref(true);
const aiPrompt = ref('');
const modifyCurrentTab = ref(false); // NEW: State for "Update Active"
const logsContainerRef = ref(null);
const selectedArtefactNames = ref([]);
const editingArtefact = ref(null);

// Standardized Active Task Lookup
const activeTask = computed(() => {
    return tasks.value.find(t => 
        (t.name.includes(props.notebook.title) || t.description.includes(props.notebook.id)) && 
        (t.status === 'running' || t.status === 'pending')
    );
});

const planTab = computed(() => props.notebook.tabs?.find(t => t.type === 'book_plan'));
const chapters = computed(() => {
    if (!planTab.value) return [];
    try { return JSON.parse(planTab.value.content); } catch { return []; }
});
const draftTabs = computed(() => props.notebook.tabs?.filter(t => t.type === 'markdown') || []);
const currentTab = computed(() => props.notebook.tabs?.find(t => t.id === activeTabId.value) || props.notebook.tabs?.[0]);

const initBookView = () => {
    if (props.notebook.tabs?.length > 0) {
        if (!activeTabId.value || !props.notebook.tabs.find(t => t.id === activeTabId.value)) {
            const plan = props.notebook.tabs.find(t => t.type === 'book_plan');
            activeTabId.value = plan ? plan.id : props.notebook.tabs[0].id;
        }
    }
};

watch(() => props.notebook.id, (newId, oldId) => {
    if (newId !== oldId) {
        activeTabId.value = null;
        initBookView();
    }
}, { immediate: true });

watch(() => props.notebook.tabs, initBookView, { deep: true });

watch(() => activeTask.value?.logs?.length, () => {
    nextTick(() => {
        if (logsContainerRef.value) {
            logsContainerRef.value.scrollTop = logsContainerRef.value.scrollHeight;
        }
    });
});

async function handleProcess() {
    if (!aiPrompt.value.trim()) return;
    
    let action = 'write_book_chapter'; // Default to writing new content
    let targetId = null;

    if (modifyCurrentTab.value && currentTab.value) {
        targetId = currentTab.value.id;
        if (currentTab.value.type === 'book_plan') {
            action = 'generate_book_plan'; // Regenerate plan
        }
        // If it's a chapter, we keep 'write_book_chapter' but target the existing tab to overwrite/refine
    } else {
        // If not modifying active, we assume we are generating a NEW plan or NEW chapter based on context
        // But usually "Generate Plan" is specific.
        // Let's infer: if prompt mentions "plan" or "outline", use generate_book_plan?
        // Or simpler: If we are on the Plan tab and NOT modifying, we probably want a new plan? No, multiple plans doesn't make sense.
        // Let's assume if user is on Plan tab, they likely want to update it.
        if (currentTab.value?.type === 'book_plan') {
             const { confirmed } = await uiStore.showConfirmation({ title: 'Update Plan?', message: 'This will regenerate the book outline. Continue?', confirmText: 'Regenerate' });
             if (!confirmed) return;
             action = 'generate_book_plan';
             targetId = currentTab.value.id;
        }
    }

    await notebookStore.processWithAi(aiPrompt.value, [], action, targetId, false, selectedArtefactNames.value);
    aiPrompt.value = '';
}

async function writeChapter(chapter) {
    const prompt = `Write Chapter: ${chapter.title}\nContext: ${chapter.description}`;
    await notebookStore.processWithAi(prompt, [], 'write_book_chapter', null, false, selectedArtefactNames.value);
}

function handleRemoveTab(id) {
    if (confirm("Delete this chapter?")) {
        notebookStore.removeTab(id);
        if (activeTabId.value === id) activeTabId.value = null;
    }
}

function toggleArtefact(name) {
    const idx = selectedArtefactNames.value.indexOf(name);
    if (idx === -1) selectedArtefactNames.value.push(name);
    else selectedArtefactNames.value.splice(idx, 1);
}

function openImportWizard() {
    uiStore.openModal('artefactImportWizard', { notebookId: props.notebook.id });
}

// Artefact Management
function viewArtefact(art) {
    uiStore.openModal('artefactViewer', { 
        artefact: { 
            title: art.filename, 
            content: art.content 
        } 
    });
}

function openArtefactEditor(art) {
    editingArtefact.value = { 
        originalName: art.filename, 
        name: art.filename, 
        content: art.content 
    };
}

async function saveArtefactEdit() {
    if (!editingArtefact.value) return;
    try {
        await notebookStore.updateArtefact(
            editingArtefact.value.originalName, 
            editingArtefact.value.name, 
            editingArtefact.value.content
        );
        editingArtefact.value = null;
    } catch (e) { 
        console.error(e); 
    }
}

async function deleteArtefact(filename) {
    await notebookStore.deleteArtefact(filename);
}
</script>

<template>
    <div class="h-full flex overflow-hidden bg-gray-50 dark:bg-gray-900 relative">
        
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
                            <span class="text-[10px] font-black uppercase text-gray-500 tracking-widest">Book Studio Terminal Output</span>
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

        <!-- Sidebar Navigator -->
        <div class="w-72 border-r dark:border-gray-700 bg-white dark:bg-gray-850 flex flex-col flex-shrink-0">
            <div class="p-4 border-b dark:border-gray-700 font-black text-[10px] uppercase tracking-widest text-gray-500 flex justify-between items-center">
                <span>Book Navigator</span>
                <button @click="notebookStore.addTab('markdown')" class="text-blue-500 hover:text-blue-600" title="Add Chapter">
                    <IconPlus class="w-4 h-4" />
                </button>
            </div>

            <div class="flex-grow overflow-y-auto p-2 space-y-4 custom-scrollbar">
                <!-- Outline Link -->
                <div v-if="planTab" @click="activeTabId = planTab.id" 
                     class="p-3 rounded-lg border-2 cursor-pointer transition-all shadow-sm" 
                     :class="activeTabId === planTab.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-transparent bg-gray-50 dark:bg-gray-800 hover:border-gray-300'">
                    <div class="flex items-center gap-2 mb-1 text-blue-600"><IconBookOpen class="w-4 h-4"/> <span class="font-bold text-xs uppercase">Outline</span></div>
                    <p class="text-[10px] opacity-70 line-clamp-2">{{ notebook.title }} Plan</p>
                </div>

                <!-- Chapters List -->
                <div class="space-y-1">
                    <div v-for="tab in draftTabs" :key="tab.id" @click="activeTabId = tab.id" 
                         class="group flex items-center justify-between p-2 rounded cursor-pointer text-sm font-medium transition-colors" 
                         :class="activeTabId === tab.id ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300' : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'">
                        <div class="flex items-center gap-2 truncate min-w-0">
                            <IconFileText class="w-4 h-4 flex-shrink-0 opacity-70"/>
                            <span class="truncate">{{ tab.title }}</span>
                        </div>
                        <button @click.stop="handleRemoveTab(tab.id)" class="opacity-0 group-hover:opacity-100 hover:text-red-500 transition-opacity p-1">
                            <IconTrash class="w-3.5 h-3.5" />
                        </button>
                    </div>
                </div>

                <!-- ARTEFACTS -->
                <div class="pt-4 space-y-1">
                    <div class="px-2 py-1 text-[9px] font-black uppercase text-gray-400 tracking-wider flex justify-between items-center">
                        <span>Artefacts</span>
                        <button @click="openImportWizard" class="text-green-500 hover:text-green-600"><IconPlus class="w-3 h-3"/></button>
                    </div>
                    <div v-for="art in notebook.artefacts" :key="art.filename" 
                         @click="toggleArtefact(art.filename)"
                         class="flex items-center gap-2 p-2 rounded text-[10px] cursor-pointer group"
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
            </div>
        </div>

        <!-- Main Content Area -->
        <div class="flex-grow flex flex-col relative min-w-0">
            <template v-if="currentTab">
                <div class="p-3 border-b dark:border-gray-700 flex justify-between items-center bg-white dark:bg-gray-900 shadow-sm z-10">
                    <input v-model="currentTab.title" @blur="notebookStore.saveActive" class="font-bold text-lg bg-transparent border-none focus:ring-0 text-gray-800 dark:text-gray-100 p-0" />
                    <div class="flex items-center gap-2">
                        <button @click="notebookStore.saveActive" class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500" title="Save">
                            <IconSave class="w-4 h-4" />
                        </button>
                        <div class="flex gap-1 bg-gray-100 dark:bg-gray-800 p-0.5 rounded border dark:border-gray-700">
                             <button @click="isRenderMode = true" class="p-1 rounded" :class="isRenderMode ? 'bg-white shadow text-blue-600' : 'text-gray-400'"><IconEye class="w-4 h-4"/></button>
                             <button @click="isRenderMode = false" class="p-1 rounded" :class="!isRenderMode ? 'bg-white shadow text-blue-600' : 'text-gray-400'"><IconPencil class="w-4 h-4"/></button>
                        </div>
                    </div>
                </div>

                <div class="flex-grow overflow-hidden relative">
                    <div v-if="currentTab.type === 'book_plan'" class="absolute inset-0 overflow-y-auto p-8 space-y-6 custom-scrollbar bg-gray-50/50 dark:bg-transparent">
                        <div class="max-w-4xl mx-auto space-y-4">
                            <div v-for="(ch, i) in chapters" :key="i" class="p-6 bg-white dark:bg-gray-800 rounded-xl border-l-4 border-blue-500 shadow-md flex justify-between items-start transition-transform hover:scale-[1.01]">
                                <div class="flex-grow pr-6">
                                    <div class="text-[10px] font-black uppercase text-blue-500 mb-1">Chapter {{ i+1 }}</div>
                                    <div class="font-bold text-lg text-gray-900 dark:text-white mb-2">{{ ch.title }}</div>
                                    <p class="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">{{ ch.description }}</p>
                                </div>
                                <button @click="writeChapter(ch)" class="btn btn-primary btn-sm flex-shrink-0 shadow-lg" :disabled="activeTask">
                                    <IconSparkles class="w-4 h-4 mr-2"/> Write
                                </button>
                            </div>
                        </div>
                    </div>
                    <template v-else>
                        <div v-if="isRenderMode" class="absolute inset-0 overflow-y-auto p-10 custom-scrollbar bg-white dark:bg-gray-900">
                            <MessageContentRenderer :content="currentTab.content" :key="currentTab.id + currentTab.content?.length" class="prose prose-lg dark:prose-invert max-w-4xl mx-auto" />
                        </div>
                        <CodeMirrorEditor v-else v-model="currentTab.content" @blur="notebookStore.saveActive" class="h-full" />
                    </template>
                </div>
            </template>
            <div v-else class="flex-grow flex items-center justify-center text-gray-400 italic">Select a plan or chapter from the sidebar.</div>

            <!-- Global Action Bar -->
            <div class="p-4 border-t dark:border-gray-700 bg-white dark:bg-gray-900 flex gap-3 shadow-inner">
                <div class="relative flex-grow">
                    <input v-model="aiPrompt" @keyup.enter="handleProcess" placeholder="Describe the book's core topic or instructions..." class="input-field w-full pr-32" />
                    
                    <div class="flex items-center gap-2 px-2 border-l dark:border-gray-700 absolute right-1 top-1/2 -translate-y-1/2 bg-white dark:bg-gray-800 pl-2 h-8">
                        <input type="checkbox" id="mod-tab" v-model="modifyCurrentTab" class="h-3 w-3 rounded text-blue-600 focus:ring-blue-500 cursor-pointer"/>
                        <label for="mod-tab" class="text-[9px] font-black uppercase text-gray-400 cursor-pointer select-none whitespace-nowrap">Update Active</label>
                    </div>
                </div>
                <button @click="handleProcess" class="btn btn-primary px-8 flex-shrink-0" :disabled="!aiPrompt.trim() || activeTask">
                    <IconSparkles class="w-4 h-4 mr-2"/> Go
                </button>
            </div>
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
</style>
