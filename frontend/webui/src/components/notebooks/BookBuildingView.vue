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
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';

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
const logsContainerRef = ref(null);
const selectedArtefactNames = ref([]);
const editingArtefact = ref(null);

const exportOptions = [
    { label: 'PDF Manuscript', value: 'pdf' },
    { label: 'Word (DOCX)', value: 'docx' },
    { label: 'Markdown File', value: 'md' },
    { label: 'Plain Text', value: 'txt' }
];

async function handleExport(format) { await notebookStore.exportNotebook(format); }

const activeTask = computed(() => {
    return tasks.value.find(t => 
        (t.description === props.notebook.id || t.name.includes(props.notebook.title)) && 
        (t.status === 'running' || t.status === 'pending')
    );
});

const planTab = computed(() => props.notebook.tabs?.find(t => t.type === 'book_plan'));
const chapters = computed(() => {
    if (!planTab.value) return [];
    try { return JSON.parse(planTab.value.content); } catch { return []; }
});
const currentTab = computed(() => props.notebook.tabs?.find(t => t.id === activeTabId.value) || props.notebook.tabs?.[0]);

const initBookView = () => {
    if (props.notebook.tabs?.length > 0) {
        if (!activeTabId.value || !props.notebook.tabs.find(t => t.id === activeTabId.value)) {
            const plan = props.notebook.tabs.find(t => t.type === 'book_plan');
            activeTabId.value = plan ? plan.id : props.notebook.tabs[0].id;
        }
    }
};

watch(() => props.notebook.id, initBookView, { immediate: true });

async function handleProcess() {
    if (!aiPrompt.value.trim()) return;
    let action = (modifyCurrentTab.value && currentTab.value?.type === 'book_plan') ? 'generate_book_plan' : 'write_book_chapter';
    let targetId = modifyCurrentTab.value ? currentTab.value?.id : null;
    await notebookStore.processWithAi(aiPrompt.value, [], action, targetId, false, selectedArtefactNames.value);
    aiPrompt.value = '';
}

async function writeChapter(chapter) {
    await notebookStore.processWithAi(`Write Chapter: ${chapter.title}`, [], 'write_book_chapter', null, false, selectedArtefactNames.value);
}

function openImportWizard() { uiStore.openModal('artefactImportWizard', { notebookId: props.notebook.id }); }
async function saveArtefactEdit() {
    await notebookStore.updateArtefact(editingArtefact.value.originalName, editingArtefact.value.name, editingArtefact.value.content);
    editingArtefact.value = null;
}
</script>

<template>
    <div class="h-full flex overflow-hidden bg-gray-50 dark:bg-gray-900 relative">
        
        <!-- TELEPORT TO GLOBAL HEADER -->
        <Teleport to="#global-header-title-target">
            <div class="flex flex-col items-center">
                <span class="text-sm font-bold text-gray-800 dark:text-gray-100">{{ notebook.title }}</span>
                <span class="text-[9px] font-black uppercase text-blue-500 tracking-widest">Book Studio</span>
            </div>
        </Teleport>

        <Teleport to="#global-header-actions-target">
            <div class="flex items-center gap-1">
                <DropdownMenu title="Export" button-class="btn-icon-flat text-gray-500">
                    <template #icon><IconArrowDownTray class="w-4 h-4" /></template>
                    <div class="w-48 py-1">
                        <button v-for="opt in exportOptions" :key="opt.value" @click="handleExport(opt.value)" class="w-full text-left px-4 py-2 text-xs font-bold hover:bg-gray-100 dark:hover:bg-gray-800">{{ opt.label }}</button>
                    </div>
                </DropdownMenu>

                <div class="flex bg-gray-100 dark:bg-gray-800 p-0.5 rounded-lg border dark:border-gray-700">
                     <button @click="isRenderMode = true" class="p-1.5 rounded transition-colors" :class="isRenderMode ? 'bg-white dark:bg-gray-700 shadow text-blue-600' : 'text-gray-400'"><IconEye class="w-3.5 h-3.5"/></button>
                     <button @click="isRenderMode = false" class="p-1.5 rounded transition-colors" :class="!isRenderMode ? 'bg-white dark:bg-gray-700 shadow text-blue-600' : 'text-gray-400'"><IconPencil class="w-3.5 h-3.5"/></button>
                </div>

                <button @click="notebookStore.saveActive" class="btn-icon-flat text-green-500" title="Save">
                    <IconSave class="w-4 h-4" />
                </button>
            </div>
        </Teleport>

        <!-- Sidebar -->
        <div class="w-72 border-r dark:border-gray-700 bg-white dark:bg-gray-850 flex flex-col flex-shrink-0">
            <div class="p-4 border-b dark:border-gray-700 font-black text-[10px] uppercase tracking-widest text-gray-500 flex justify-between items-center">
                <span>Manuscript</span>
                <button @click="notebookStore.addTab('markdown')" class="text-blue-500 hover:text-blue-600"><IconPlus class="w-4 h-4" /></button>
            </div>
            <div class="flex-grow overflow-y-auto p-2 space-y-4 custom-scrollbar">
                <div v-if="planTab" @click="activeTabId = planTab.id" class="p-3 rounded-lg border-2 cursor-pointer shadow-sm" :class="activeTabId === planTab.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'bg-gray-50 dark:bg-gray-800 border-transparent'">
                    <div class="flex items-center gap-2 mb-1 text-blue-600"><IconBookOpen class="w-4 h-4"/> <span class="font-bold text-xs uppercase">Outline</span></div>
                    <p class="text-[10px] opacity-70">{{ notebook.title }} Plan</p>
                </div>
            </div>
        </div>

        <!-- Main Content Area -->
        <div class="flex-grow flex flex-col relative min-w-0">
            <div class="flex-grow overflow-hidden relative">
                <div v-if="currentTab?.type === 'book_plan'" class="absolute inset-0 overflow-y-auto p-8 space-y-6 bg-gray-50/50 dark:bg-transparent">
                    <div class="max-w-4xl mx-auto space-y-4">
                        <div v-for="(ch, i) in chapters" :key="i" class="p-6 bg-white dark:bg-gray-800 rounded-xl border-l-4 border-blue-500 shadow-md flex justify-between items-start transition-transform hover:scale-[1.01]">
                            <div class="flex-grow pr-6">
                                <div class="text-[10px] font-black uppercase text-blue-500 mb-1">Chapter {{ i+1 }}</div>
                                <div class="font-bold text-lg text-gray-900 dark:text-white mb-2">{{ ch.title }}</div>
                                <p class="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">{{ ch.description }}</p>
                            </div>
                            <button @click="writeChapter(ch)" class="btn btn-primary btn-sm flex-shrink-0 shadow-lg" :disabled="activeTask"><IconSparkles class="w-4 h-4 mr-2"/> Write</button>
                        </div>
                    </div>
                </div>
                <template v-else-if="currentTab">
                    <div v-if="isRenderMode" class="absolute inset-0 overflow-y-auto p-10 custom-scrollbar bg-white dark:bg-gray-900">
                        <MessageContentRenderer :content="currentTab.content" class="prose prose-lg dark:prose-invert max-w-4xl mx-auto" />
                    </div>
                    <CodeMirrorEditor v-else v-model="currentTab.content" @blur="notebookStore.saveActive" class="h-full" />
                </template>
            </div>

            <!-- Global Action Bar -->
            <div class="p-4 border-t dark:border-gray-700 bg-white dark:bg-gray-900 flex gap-3 shadow-inner">
                <div class="relative flex-grow">
                    <input v-model="aiPrompt" @keyup.enter="handleProcess" placeholder="Describe instructions for the book..." class="input-field w-full pr-32" />
                    <div class="flex items-center gap-2 px-2 border-l dark:border-gray-700 absolute right-1 top-1/2 -translate-y-1/2 bg-white dark:bg-gray-800 pl-2 h-8">
                        <input type="checkbox" id="mod-tab" v-model="modifyCurrentTab" class="h-3 w-3 rounded text-blue-600 cursor-pointer"/>
                        <label for="mod-tab" class="text-[9px] font-black uppercase text-gray-400 cursor-pointer">Update Active</label>
                    </div>
                </div>
                <button @click="handleProcess" class="btn btn-primary px-8 flex-shrink-0" :disabled="activeTask"><IconSparkles class="w-4 h-4 mr-2"/> Go</button>
            </div>
        </div>
    </div>
</template>
