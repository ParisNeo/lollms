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
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconSave from '../../assets/icons/IconSave.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconArrowRight from '../../assets/icons/IconArrowRight.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconTable from '../../assets/icons/IconTable.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import IconClock from '../../assets/icons/IconClock.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconMagic from '../../assets/icons/IconMagic.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';

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
const useRlm = ref(false); 
const selectedArtefactNames = ref([]);
const logsContainerRef = ref(null);

// Tab Editing
const editingTabId = ref(null);
const tabTitleInput = ref('');

const exportOptions = [
    { label: 'PDF Document', value: 'pdf' }, { label: 'Word (DOCX)', value: 'docx' }, { label: 'Markdown', value: 'md' }, { label: 'PowerPoint', value: 'pptx' }, { label: 'Text File', value: 'txt' }
];

const quickActions = [
    { id: 'summarize', label: 'Summarize', icon: IconSparkles, color: 'text-purple-500', bg: 'bg-purple-50 dark:bg-purple-900/20' },
    { id: 'extract_key_points', label: 'Key Points', icon: IconFileText, color: 'text-blue-500', bg: 'bg-blue-50 dark:bg-blue-900/20' },
    { id: 'generate_html', label: 'Visual Widget', icon: IconTable, color: 'text-green-500', bg: 'bg-green-50 dark:bg-green-900/20' },
    { id: 'generate_code', label: 'Logic/Code', icon: IconCode, color: 'text-orange-500', bg: 'bg-orange-50 dark:bg-orange-900/20' },
    { id: 'generate_timeline', label: 'Timeline', icon: IconClock, color: 'text-cyan-500', bg: 'bg-cyan-50 dark:bg-cyan-900/20' },
];

// REFINED ACTIVE TASK FILTER: Match by notebook ID description
const activeTask = computed(() => {
    return tasks.value.find(t => 
        (t.description === props.notebook.id || (t.name && t.name.includes(props.notebook.title))) && 
        (t.status === 'running' || t.status === 'pending')
    );
});

const isCurrentTabProcessing = computed(() => !!activeTask.value);

const currentTab = computed(() => {
    if (!props.notebook.tabs?.length) return null;
    return props.notebook.tabs.find(t => t.id === activeTabId.value) || props.notebook.tabs[0];
});

// HTML SECURE PREVIEW
const htmlPreviewUrl = ref(null);
watch(() => [currentTab.value?.content, currentTab.value?.type], ([content, type]) => {
    if (type === 'html' && content) {
        if (htmlPreviewUrl.value) URL.revokeObjectURL(htmlPreviewUrl.value);
        const blob = new Blob([content], { type: 'text/html' });
        htmlPreviewUrl.value = URL.createObjectURL(blob);
    } else {
        htmlPreviewUrl.value = null;
    }
}, { immediate: true });

const initTabs = () => {
    if (props.notebook.tabs?.length > 0 && !activeTabId.value) {
        activeTabId.value = props.notebook.tabs[0].id;
    }
};
watch(() => props.notebook.id, () => { activeTabId.value = null; initTabs(); }, { immediate: true });

watch(() => activeTask.value?.logs?.length, () => {
    nextTick(() => { if (logsContainerRef.value) logsContainerRef.value.scrollTop = logsContainerRef.value.scrollHeight; });
});

// --- TAB TITLES ---
function startEditingTab(tab) {
    editingTabId.value = tab.id;
    tabTitleInput.value = tab.title;
    nextTick(() => document.getElementById(`tab-input-${tab.id}`)?.focus());
}

async function saveTabTitle() {
    if (!editingTabId.value) return;
    const tab = props.notebook.tabs.find(t => t.id === editingTabId.value);
    if (tab && tabTitleInput.value.trim()) {
        tab.title = tabTitleInput.value.trim();
        await notebookStore.saveActive();
    }
    editingTabId.value = null;
}

async function handleAutoTabTitle() {
    if (!currentTab.value || !currentTab.value.content) return;
    uiStore.addNotification("Generating title...", "info");
    const res = await notebookStore.enhancePrompt(currentTab.value.content.substring(0, 500), "Create a short 3-word title.");
    if (res) { currentTab.value.title = res.replace(/"/g, '').trim(); await notebookStore.saveActive(); }
}

// --- ACTIONS ---
async function handleAction(actionType, skipValidation = false) {
    let targetId = activeTabId.value;
    let prompt = aiPrompt.value;
    if (actionType === 'summarize' && !prompt) prompt = "Summarize the sources.";
    if (!skipValidation && !prompt.trim() && !selectedArtefactNames.value.length) return uiStore.addNotification("Prompt or context needed.", "warning");

    if (!modifyCurrentTab.value) {
        let type = actionType === 'generate_html' ? 'html' : (actionType === 'generate_code' ? 'code' : 'markdown');
        const newTab = notebookStore.addTab(type);
        newTab.title = "Generating...";
        await notebookStore.saveActive();
        activeTabId.value = newTab.id;
        targetId = newTab.id;
    }
    await notebookStore.processWithAi(prompt, [], actionType, targetId, false, selectedArtefactNames.value, "", useRlm.value);
    aiPrompt.value = '';
}

async function stopTask() { if (activeTask.value) await tasksStore.cancelTask(activeTask.value.id); }
async function handleCopy() { if (currentTab.value?.content) { await navigator.clipboard.writeText(currentTab.value.content); uiStore.addNotification("Copied!", "success"); } }
async function handleExport(fmt) { await notebookStore.exportNotebook(fmt); }
function toggleArtefact(name) {
    const idx = selectedArtefactNames.value.indexOf(name);
    if (idx === -1) selectedArtefactNames.value.push(name); else selectedArtefactNames.value.splice(idx, 1);
}
</script>

<template>
    <div class="h-full flex flex-col overflow-hidden bg-gray-50 dark:bg-gray-950 relative">
        
        <Teleport to="#global-header-title-target">
            <div class="flex flex-col items-center">
                <span class="text-sm font-bold text-gray-800 dark:text-gray-100 truncate max-w-[200px]">{{ notebook.title }}</span>
                <div class="flex items-center gap-1.5">
                    <span v-if="isCurrentTabProcessing" class="flex items-center gap-1 text-[8px] font-black text-blue-500 animate-pulse"><IconAnimateSpin class="w-2 h-2 animate-spin" /> {{ activeTask?.progress || 0 }}%</span>
                    <span v-if="useRlm" class="text-[8px] font-black uppercase bg-purple-100 dark:bg-purple-900/30 px-1.5 py-0.5 rounded text-purple-600 flex items-center gap-1"><IconCpuChip class="w-2 h-2" /> RLM</span>
                </div>
            </div>
        </Teleport>

        <Teleport to="#global-header-actions-target">
            <div class="flex items-center gap-1">
                <button @click="handleAutoTabTitle" class="btn-icon-flat text-purple-500" title="Auto-Title"><IconMagic class="w-4 h-4" /></button>
                <button @click="handleCopy" class="btn-icon-flat text-gray-500 hover:text-blue-500" title="Copy Content"><IconCopy class="w-4 h-4" /></button>
                <DropdownMenu title="Export" button-class="btn-icon-flat text-gray-500"><template #icon><IconArrowDownTray class="w-4 h-4" /></template><div class="w-48 py-1"><button v-for="opt in exportOptions" :key="opt.value" @click="handleExport(opt.value)" class="w-full text-left px-4 py-2 text-xs font-bold hover:bg-gray-100 dark:hover:bg-gray-800">{{ opt.label }}</button></div></DropdownMenu>
                <div class="flex bg-gray-100 dark:bg-gray-800 p-0.5 rounded-lg border dark:border-gray-700 mx-1"><button @click="isRenderMode = true" class="p-1.5 rounded transition-colors" :class="isRenderMode ? 'bg-white dark:bg-gray-700 shadow text-blue-600' : 'text-gray-400'"><IconEye class="w-3.5 h-3.5"/></button><button @click="isRenderMode = false" class="p-1.5 rounded transition-colors" :class="!isRenderMode ? 'bg-white dark:bg-gray-700 shadow text-blue-600' : 'text-gray-400'"><IconPencil class="w-3.5 h-3.5"/></button></div>
                <button @click="notebookStore.saveActive" class="btn-icon-flat text-green-500" title="Save All"><IconSave class="w-4 h-4" /></button>
            </div>
        </Teleport>

        <div class="flex-grow flex overflow-hidden">
            <div class="w-72 border-r dark:border-gray-800 bg-gray-100 dark:bg-gray-900 flex flex-col flex-shrink-0">
                <div class="p-4 border-b dark:border-gray-800 font-black text-[10px] uppercase text-gray-500 flex justify-between items-center"><span>Research Material</span><button @click="uiStore.openModal('artefactImportWizard', { notebookId: props.notebook.id })" class="text-green-500"><IconPlus class="w-4 h-4" /></button></div>
                <div class="flex-grow overflow-y-auto p-2 space-y-1 custom-scrollbar">
                    <div v-for="art in notebook.artefacts" :key="art.filename" @click="toggleArtefact(art.filename)" class="flex items-center gap-2 p-3 rounded-lg cursor-pointer group bg-white dark:bg-gray-800 border transition-all" :class="selectedArtefactNames.includes(art.filename) ? 'border-green-500' : 'border-transparent'">
                        <IconCheckCircle v-if="selectedArtefactNames.includes(art.filename)" class="w-4 h-4 text-green-500" /><IconFileText v-else class="w-4 h-4 text-gray-400 opacity-50" /><span class="truncate text-xs font-bold">{{ art.filename }}</span>
                    </div>
                </div>
            </div>

            <div class="flex-grow flex flex-col min-w-0 bg-white dark:bg-gray-900">
                <div class="border-b dark:border-gray-800 flex overflow-x-auto pt-2 px-2 shadow-sm bg-gray-50 dark:bg-gray-900">
                    <div v-for="tab in notebook.tabs" :key="tab.id" @click="activeTabId = tab.id" class="group px-4 py-2 cursor-pointer text-[10px] font-black uppercase transition-all flex items-center gap-2 border-t border-x rounded-t-xl mx-0.5 min-w-[120px] max-w-[200px] h-9" :class="activeTabId === tab.id ? 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-blue-600' : 'text-gray-400 border-transparent hover:text-gray-600'">
                        <input v-if="editingTabId === tab.id" :id="`tab-input-${tab.id}`" v-model="tabTitleInput" @blur="saveTabTitle" @keyup.enter="saveTabTitle" class="bg-transparent border-none outline-none w-full p-0 text-[10px] font-black uppercase text-blue-600" />
                        <span v-else class="truncate flex-grow" @dblclick="startEditingTab(tab)">{{ tab.title }}</span>
                        <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100"><button @click.stop="startEditingTab(tab)" class="p-0.5 hover:text-blue-500"><IconPencil class="w-2.5 h-2.5"/></button><button v-if="tab.title !== 'Main Draft'" @click.stop="notebookStore.removeTab(tab.id)" class="p-0.5 hover:text-red-500"><IconXMark class="w-3 h-3"/></button></div>
                    </div>
                </div>

                <div class="flex-grow overflow-hidden relative">
                    <!-- TERMINAL UI -->
                    <div v-if="isCurrentTabProcessing && activeTask" class="absolute inset-0 z-50 flex flex-col bg-slate-900/95 backdrop-blur-sm animate-in fade-in duration-300">
                        <div class="p-6 border-b border-white/10 flex items-center justify-between">
                            <div class="flex items-center gap-4">
                                <div class="p-4 bg-blue-600 rounded-2xl shadow-xl shadow-blue-500/40"><IconAnimateSpin class="w-8 h-8 animate-spin text-white"/></div>
                                <div><h2 class="text-xl font-black text-white uppercase tracking-tight">{{ activeTask.name }}</h2><p class="text-xs font-bold text-blue-400 uppercase">{{ activeTask.description }}</p></div>
                            </div>
                            <div class="flex items-center gap-4">
                                <div class="text-5xl font-black text-blue-500 font-mono">{{ activeTask.progress }}%</div>
                                <button @click="stopTask" class="btn btn-danger px-8 py-3 rounded-xl flex items-center gap-2 shadow-2xl"><IconStopCircle class="w-6 h-6" /> Stop</button>
                            </div>
                        </div>
                        <div class="flex-grow flex flex-col min-h-0 m-8 bg-black rounded-3xl border border-white/10 shadow-2xl overflow-hidden font-mono">
                            <div ref="logsContainerRef" class="flex-grow overflow-y-auto p-8 text-xs text-gray-400 space-y-2 custom-scrollbar">
                                <div v-for="(log, i) in activeTask.logs" :key="i" class="flex gap-4">
                                    <span class="text-gray-700 shrink-0 select-none">[{{ new Date(log.timestamp).toLocaleTimeString() }}]</span> 
                                    <span :class="{'text-red-400 font-bold': log.level === 'ERROR', 'text-blue-400': log.level === 'INFO', 'text-green-400': log.level === 'SUCCESS'}">{{ log.message }}</span>
                                </div>
                                <div v-if="activeTask.logs.length === 0" class="text-gray-600 italic">Connecting to task stream...</div>
                            </div>
                        </div>
                    </div>

                    <template v-else-if="currentTab">
                        <div v-if="currentTab.type === 'html'" class="absolute inset-0 bg-white">
                            <iframe v-if="htmlPreviewUrl" :src="htmlPreviewUrl" sandbox="allow-scripts allow-forms" class="w-full h-full border-none"></iframe>
                        </div>
                        <div v-else-if="isRenderMode" class="absolute inset-0 overflow-y-auto p-8 custom-scrollbar">
                            <div class="max-w-4xl mx-auto shadow-sm border dark:border-gray-800 p-10 rounded-2xl bg-white dark:bg-gray-900 animate-in slide-in-from-bottom-2 duration-500">
                                <MessageContentRenderer :content="currentTab.content" :key="currentTab.id + currentTab.content?.length" class="prose dark:prose-invert max-w-none" />
                            </div>
                        </div>
                        <CodeMirrorEditor v-else v-model="currentTab.content" @blur="notebookStore.saveActive" class="h-full" />
                    </template>
                </div>
            </div>
        </div>

        <div class="p-4 bg-white dark:bg-gray-900 border-t dark:border-gray-800 z-50 shadow-inner flex flex-col gap-3">
            <div class="max-w-6xl mx-auto w-full flex items-center gap-2 overflow-x-auto no-scrollbar pb-1">
                <button v-for="action in quickActions" :key="action.id" @click="handleQuickAction(action.id)" :disabled="isCurrentTabProcessing" class="flex items-center gap-2 px-3 py-1.5 rounded-full border transition-all shrink-0" :class="[action.bg, action.color, 'border-transparent hover:border-current']">
                    <component :is="action.icon" class="w-3.5 h-3.5" /><span class="text-[10px] font-black uppercase tracking-wide">{{ action.label }}</span>
                </button>
            </div>
            <div class="max-w-6xl mx-auto w-full flex gap-2 relative">
                <input v-model="aiPrompt" @keyup.enter="handleAction('text_processing')" placeholder="Ask AI to analyze or write..." class="input-field flex-grow pr-64 h-12 rounded-xl text-sm" />
                <div class="absolute right-14 top-1/2 -translate-y-1/2 flex items-center gap-4 border-l dark:border-gray-700 pl-3 pr-2 bg-white dark:bg-gray-800 h-8">
                    <label class="flex items-center gap-1.5 cursor-pointer group"><input type="checkbox" v-model="useRlm" class="h-3 w-3 rounded text-purple-600 focus:ring-purple-500"/><span class="text-[9px] font-black uppercase text-gray-400 group-hover:text-purple-500 select-none">RLM Mode</span></label>
                    <label class="flex items-center gap-1.5 cursor-pointer group"><input type="checkbox" v-model="modifyCurrentTab" class="h-3 w-3 rounded text-blue-600 focus:ring-blue-500"/><span class="text-[9px] font-black uppercase text-gray-400 group-hover:text-blue-500 select-none">Update Active</span></label>
                </div>
                <button @click="handleAction('text_processing')" class="btn btn-primary w-12 h-12 rounded-xl shadow-lg flex items-center justify-center" :disabled="isCurrentTabProcessing"><IconArrowRight v-if="!isCurrentTabProcessing" class="w-5 h-5"/><IconAnimateSpin v-else class="w-5 h-5 animate-spin"/></button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.progress-bar-animated { background-image: linear-gradient(45deg, rgba(255, 255, 255, .1) 25%, transparent 25%, transparent 50%, rgba(255, 255, 255, .1) 50%, rgba(255, 255, 255, .1) 75%, transparent 75%, transparent); background-size: 1rem 1rem; animation: shimmer 1s linear infinite; }
@keyframes shimmer { 0% { background-position: 1rem 0; } 100% { background-position: 0 0; } }
</style>
