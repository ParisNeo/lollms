<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useNotebookStore } from '../../stores/notebooks';
import { useUiStore } from '../../stores/ui';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';
import DropdownMenu from '../ui/DropDownMenu/DropdownMenu.vue';

// Icons
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconSave from '../../assets/icons/IconSave.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconArrowRight from '../../assets/icons/IconArrowRight.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconTable from '../../assets/icons/IconTable.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import IconClock from '../../assets/icons/IconClock.vue';

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
const modifyCurrentTab = ref(false);
const selectedArtefactNames = ref([]);
const editingArtefact = ref(null);

const exportOptions = [
    { label: 'PDF Document', value: 'pdf' },
    { label: 'Word (DOCX)', value: 'docx' },
    { label: 'Markdown', value: 'md' },
    { label: 'PowerPoint', value: 'pptx' },
    { label: 'Text File', value: 'txt' }
];

const quickActions = [
    { id: 'summarize', label: 'Summarize', icon: IconSparkles, color: 'text-purple-500', bg: 'bg-purple-50 dark:bg-purple-900/20' },
    { id: 'extract_key_points', label: 'Key Points', icon: IconFileText, color: 'text-blue-500', bg: 'bg-blue-50 dark:bg-blue-900/20' },
    { id: 'generate_html', label: 'Visual Widget', icon: IconTable, color: 'text-green-500', bg: 'bg-green-50 dark:bg-green-900/20' },
    { id: 'generate_code', label: 'Logic/Code', icon: IconCode, color: 'text-orange-500', bg: 'bg-orange-50 dark:bg-orange-900/20' },
    { id: 'generate_timeline', label: 'Timeline', icon: IconClock, color: 'text-cyan-500', bg: 'bg-cyan-50 dark:bg-cyan-900/20' },
];

const activeTask = computed(() => {
    return tasks.value.find(t => 
        (t.description === props.notebook.id || t.name.includes(props.notebook.title)) && 
        (t.status === 'running' || t.status === 'pending')
    );
});

const currentTab = computed(() => {
    if (!props.notebook.tabs?.length) return null;
    return props.notebook.tabs.find(t => t.id === activeTabId.value) || props.notebook.tabs[0];
});

const initTabs = () => {
    if (props.notebook.tabs?.length > 0) {
        if (!activeTabId.value || !props.notebook.tabs.find(t => t.id === activeTabId.value)) {
            const reportTab = props.notebook.tabs.find(t => t.type === 'markdown');
            activeTabId.value = reportTab ? reportTab.id : props.notebook.tabs[0].id;
        }
    }
};

watch(() => props.notebook.id, initTabs, { immediate: true });

async function handleAction(actionType, customPrompt = null) {
    const target = modifyCurrentTab.value ? activeTabId.value : null;
    const finalPrompt = customPrompt || aiPrompt.value || `Perform ${actionType.replace('_', ' ')}`;
    
    await notebookStore.processWithAi(finalPrompt, [], actionType, target, false, selectedArtefactNames.value);
    if (!customPrompt) aiPrompt.value = '';
}

function handleProcess() { handleAction('text_processing'); }

async function handleQuickAction(actionId) {
    if (activeTask.value) return;
    await handleAction(actionId);
}

async function handleExport(fmt) { await notebookStore.exportNotebook(fmt); }

function toggleArtefact(name) {
    const idx = selectedArtefactNames.value.indexOf(name);
    if (idx === -1) selectedArtefactNames.value.push(name);
    else selectedArtefactNames.value.splice(idx, 1);
}

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
</script>

<template>
    <div class="h-full flex flex-col overflow-hidden bg-gray-50 dark:bg-gray-950 relative">
        
        <!-- TELEPORT TO GLOBAL HEADER -->
        <Teleport to="#global-header-title-target">
            <div class="flex flex-col items-center">
                <span class="text-sm font-bold text-gray-800 dark:text-gray-100 truncate max-w-[200px]">{{ notebook.title }}</span>
                <div class="flex items-center gap-1.5">
                    <span class="text-[8px] font-black uppercase bg-gray-200 dark:bg-gray-800 px-1.5 py-0.5 rounded text-gray-500">Research</span>
                    <span v-if="activeTask" class="flex items-center gap-1 text-[8px] font-black uppercase text-blue-500 animate-pulse">
                        <IconAnimateSpin class="w-2 h-2 animate-spin" /> {{ activeTask.progress }}%
                    </span>
                </div>
            </div>
        </Teleport>

        <Teleport to="#global-header-actions-target">
            <div class="flex items-center gap-1">
                <DropdownMenu title="Export"  icon="ticket"  button-class="btn-icon-flat text-gray-500 hover:text-blue-500">
                    <template #icon><IconArrowDownTray class="w-4 h-4" /></template>
                    <div class="w-48 py-1">
                        <button v-for="opt in exportOptions" :key="opt.value" 
                                @click="handleExport(opt.value)" 
                                class="w-full text-left px-4 py-2 text-xs font-bold hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                            {{ opt.label }}
                        </button>
                    </div>
                </DropdownMenu>

                <div class="flex bg-gray-100 dark:bg-gray-800 p-0.5 rounded-lg border dark:border-gray-700 mx-1">
                     <button @click="isRenderMode = true" class="p-1.5 rounded transition-colors" :class="isRenderMode ? 'bg-white dark:bg-gray-700 shadow text-blue-600' : 'text-gray-400'"><IconEye class="w-3.5 h-3.5"/></button>
                     <button @click="isRenderMode = false" class="p-1.5 rounded transition-colors" :class="!isRenderMode ? 'bg-white dark:bg-gray-700 shadow text-blue-600' : 'text-gray-400'"><IconPencil class="w-3.5 h-3.5"/></button>
                </div>

                <button @click="notebookStore.saveActive" class="btn-icon-flat text-green-500" title="Save">
                    <IconSave class="w-4 h-4" />
                </button>
            </div>
        </Teleport>

        <div class="flex-grow flex overflow-hidden">
            <!-- Sidebar -->
            <div class="w-72 border-r dark:border-gray-800 bg-gray-100 dark:bg-gray-900 flex flex-col flex-shrink-0">
                <div class="p-4 border-b dark:border-gray-800 font-black text-[10px] uppercase tracking-widest text-gray-500 flex justify-between items-center">
                    <span>Research Material</span>
                    <button @click="uiStore.openModal('artefactImportWizard', { notebookId: props.notebook.id })" class="text-green-500 hover:text-green-600"><IconPlus class="w-4 h-4" /></button>
                </div>
                <div class="flex-grow overflow-y-auto p-2 space-y-1 custom-scrollbar">
                    <div v-for="art in notebook.artefacts" :key="art.filename" @click="toggleArtefact(art.filename)"
                         class="flex items-center gap-2 p-3 rounded-lg cursor-pointer group bg-white dark:bg-gray-800 border transition-all shadow-sm"
                         :class="selectedArtefactNames.includes(art.filename) ? 'border-green-500 ring-1 ring-green-500/20' : 'border-transparent'">
                        
                        <div class="flex items-center gap-2 flex-grow min-w-0">
                            <IconCheckCircle v-if="selectedArtefactNames.includes(art.filename)" class="w-4 h-4 text-green-500" />
                            <IconFileText v-else class="w-4 h-4 text-gray-400" />
                            <span class="truncate text-xs font-bold">{{ art.filename }}</span>
                        </div>

                        <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button @click.stop="viewArtefact(art)" class="p-1 hover:text-blue-500 transition-colors" title="View">
                                <IconEye class="w-3.5 h-3.5" />
                            </button>
                            <button @click.stop="openArtefactEditor(art)" class="p-1 hover:text-blue-500 transition-colors" title="Edit">
                                <IconPencil class="w-3.5 h-3.5" />
                            </button>
                            <button @click.stop="notebookStore.deleteArtefact(art.filename)" class="p-1 hover:text-red-500 transition-colors" title="Delete">
                                <IconTrash class="w-3.5 h-3.5" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Workspace -->
            <div class="flex-grow flex flex-col min-w-0">
                <div class="bg-white dark:bg-gray-900 border-b dark:border-gray-800 flex overflow-x-auto no-scrollbar pt-2 px-2 shadow-sm">
                    <div v-for="tab in notebook.tabs" :key="tab.id" @click="activeTabId = tab.id" 
                         class="group px-4 py-2 cursor-pointer text-[10px] font-black uppercase transition-all flex items-center gap-2 border-t border-x rounded-t-lg mx-0.5" 
                         :class="activeTabId === tab.id ? 'bg-gray-50 dark:bg-gray-950 border-gray-200 dark:border-gray-700 text-blue-600' : 'text-gray-400'">
                        <span class="truncate">{{ tab.title }}</span>
                    </div>
                </div>

                <div class="flex-grow overflow-hidden relative">
                    <template v-if="currentTab">
                        <div v-if="isRenderMode" class="absolute inset-0 overflow-y-auto p-12 custom-scrollbar bg-white dark:bg-gray-900">
                            <div class="max-w-4xl mx-auto shadow-sm border dark:border-gray-800 p-10 rounded-xl min-h-full">
                                <MessageContentRenderer :content="currentTab.content" :key="currentTab.id + currentTab.content?.length" class="prose dark:prose-invert max-w-none" />
                            </div>
                        </div>
                        <CodeMirrorEditor v-else v-model="currentTab.content" @blur="notebookStore.saveActive" class="h-full" />
                    </template>
                </div>
            </div>
        </div>

        <!-- Global Action Bar -->
        <div class="p-4 bg-white dark:bg-gray-900 border-t dark:border-gray-800 z-50 shadow-inner flex flex-col gap-3">
            
            <!-- QUICK ACTION BADGES -->
            <div class="max-w-6xl mx-auto w-full flex items-center gap-2 overflow-x-auto no-scrollbar pb-1">
                <span class="text-[9px] font-black uppercase text-gray-400 tracking-widest mr-2 shrink-0">Analysis Tools:</span>
                <button v-for="action in quickActions" 
                        :key="action.id"
                        @click="handleQuickAction(action.id)"
                        :disabled="activeTask"
                        class="flex items-center gap-2 px-3 py-1.5 rounded-full border transition-all shrink-0 hover:shadow-md active:scale-95 disabled:opacity-50"
                        :class="[action.bg, action.color, 'border-transparent hover:border-current']">
                    <component :is="action.icon" class="w-3.5 h-3.5" />
                    <span class="text-[10px] font-black uppercase tracking-wide">{{ action.label }}</span>
                </button>
            </div>

            <div class="max-w-6xl mx-auto w-full flex gap-2 relative">
                <input v-model="aiPrompt" @keyup.enter="handleProcess" placeholder="Ask AI to analyze or write..." class="input-field flex-grow pr-32 h-12 rounded-xl text-sm" />
                <div class="absolute right-14 top-1/2 -translate-y-1/2 flex items-center gap-2 border-l dark:border-gray-700 pl-3 pr-2 bg-white dark:bg-gray-900">
                    <input type="checkbox" id="mod-tab" v-model="modifyCurrentTab" class="h-4 w-4 rounded text-blue-600"/>
                    <label for="mod-tab" class="text-[9px] font-black uppercase text-gray-400 cursor-pointer select-none">Update Active</label>
                </div>
                <button @click="handleProcess" class="btn btn-primary w-12 h-12 rounded-xl shadow-lg" :disabled="activeTask"><IconArrowRight class="w-5 h-5"/></button>
            </div>
        </div>

        <!-- ARTEFACT EDITOR MODAL -->
        <transition enter-active-class="transition duration-300" enter-from-class="opacity-0" enter-to-class="opacity-100" leave-active-class="transition duration-200" leave-from-class="opacity-100" leave-to-class="opacity-0">
            <div v-if="editingArtefact" class="fixed inset-0 z-[100] bg-gray-900/60 backdrop-blur-sm flex items-center justify-center p-6">
                <div class="bg-white dark:bg-gray-900 rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col overflow-hidden border dark:border-gray-800 shadow-2xl">
                    <div class="p-4 border-b dark:border-gray-800 flex justify-between items-center bg-gray-50 dark:bg-gray-800/50">
                        <div class="flex items-center gap-2">
                            <IconPencil class="w-4 h-4 text-blue-500" />
                            <h3 class="font-black text-xs uppercase tracking-widest text-gray-500">Edit Research Source</h3>
                        </div>
                        <button @click="editingArtefact = null" class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors">
                            <IconXMark class="w-5 h-5"/>
                        </button>
                    </div>
                    <div class="flex-grow p-6 flex flex-col gap-4 overflow-hidden">
                        <div class="space-y-1">
                            <label class="text-[10px] font-black uppercase text-gray-400">Source Name</label>
                            <input v-model="editingArtefact.name" class="input-field w-full font-bold text-lg" placeholder="Filename..."/>
                        </div>
                        <div class="flex-grow flex flex-col space-y-1 min-h-0">
                            <label class="text-[10px] font-black uppercase text-gray-400">Content</label>
                            <textarea v-model="editingArtefact.content" class="flex-grow input-field font-mono text-xs p-4 resize-none leading-relaxed" placeholder="Type or paste content..."></textarea>
                        </div>
                    </div>
                    <div class="p-4 border-t dark:border-gray-800 flex justify-end gap-3 bg-gray-50 dark:bg-gray-900/50">
                        <button @click="editingArtefact = null" class="btn btn-secondary">Cancel</button>
                        <button @click="saveArtefactEdit" class="btn btn-primary px-8">Save Changes</button>
                    </div>
                </div>
            </div>
        </transition>

    </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
.no-scrollbar::-webkit-scrollbar { display: none; }
</style>
