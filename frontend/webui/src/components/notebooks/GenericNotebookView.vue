<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useNotebookStore } from '../../stores/notebooks';
import { useUiStore } from '../../stores/ui';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';

// Icons
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconSave from '../../assets/icons/IconSave.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import IconWeb from '../../assets/icons/IconWeb.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconVideoCamera from '../../assets/icons/IconVideoCamera.vue';
import IconArrowRight from '../../assets/icons/IconArrowRight.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';

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
const logsContainerRef = ref(null);
const editingArtefact = ref(null);

// Standardized Active Task Lookup
const activeTask = computed(() => {
    return tasks.value.find(t => 
        (t.name.includes(props.notebook.title) || t.description.includes(props.notebook.id)) && 
        (t.status === 'running' || t.status === 'pending')
    );
});

const currentTab = computed(() => {
    if (!props.notebook.tabs?.length) return null;
    return props.notebook.tabs.find(t => t.id === activeTabId.value) || props.notebook.tabs[0];
});

const currentHtmlSrc = computed(() => {
    if (currentTab.value?.type === 'html' && currentTab.value.content) {
        const blob = new Blob([currentTab.value.content], { type: 'text/html' });
        return URL.createObjectURL(blob);
    }
    return null;
});

// JSON Parsers for structured tabs
const slideData = computed(() => {
    if (currentTab.value?.type === 'slides') {
        try { return JSON.parse(currentTab.value.content); } catch { return null; }
    }
    return null;
});

const youtubeData = computed(() => {
    if (currentTab.value?.type === 'youtube_storyboard' || currentTab.value?.type === 'youtube_script') {
        try { return JSON.parse(currentTab.value.content); } catch { return null; }
    }
    return null;
});


const initTabs = () => {
    if (props.notebook.tabs?.length > 0) {
        if (!activeTabId.value || !props.notebook.tabs.find(t => t.id === activeTabId.value)) {
            activeTabId.value = props.notebook.tabs[0].id;
        }
    }
};

watch(() => props.notebook.id, initTabs, { immediate: true });
watch(() => props.notebook.tabs, initTabs, { deep: true });

watch(() => activeTask.value?.logs?.length, () => {
    if (logsContainerRef.value) {
        nextTick(() => {
            logsContainerRef.value.scrollTop = logsContainerRef.value.scrollHeight;
        });
    }
});

// --- AI ACTIONS ---

async function handleAction(actionType) {
    const target = modifyCurrentTab.value ? activeTabId.value : null;
    let prompt = aiPrompt.value;

    if (actionType === 'summarize' && !prompt) {
        prompt = "Summarize the selected information.";
    }
    
    if (!prompt.trim() && !selectedArtefactNames.value.length) {
        uiStore.addNotification("Please enter a prompt or select artefacts.", "warning");
        return;
    }

    await notebookStore.processWithAi(prompt, [], actionType, target, false, selectedArtefactNames.value);
    aiPrompt.value = '';
}

function handleProcess() {
    handleAction('text_processing');
}

// --- HELPERS ---
function getSlideImage(slide) {
    if (slide.images && slide.images.length > 0) {
        const idx = slide.selected_image_index || 0;
        return slide.images[idx]?.path;
    }
    return null;
}

// --- ARTEFACTS & CONVERSION ---

function toggleArtefact(name) {
    const idx = selectedArtefactNames.value.indexOf(name);
    if (idx === -1) selectedArtefactNames.value.push(name);
    else selectedArtefactNames.value.splice(idx, 1);
}

function openImportWizard() {
    uiStore.openModal('artefactImportWizard', { notebookId: props.notebook.id });
}

async function saveTabAsArtefact() {
    if (!currentTab.value) return;
    const { confirmed, value } = await uiStore.showConfirmation({
        title: 'Save as Artefact',
        message: 'Enter a name for this new source:',
        confirmText: 'Save',
        inputType: 'text',
        inputValue: currentTab.value.title
    });
    
    if (confirmed && value) {
        await notebookStore.createManualArtefact(value, currentTab.value.content);
    }
}

async function convertToProject(type) {
    // 1. Gather context: Selected Artefacts + Current Tab content
    let context = "";
    if (currentTab.value && currentTab.value.content) {
        context += `\n\n[Primary Content from ${currentTab.value.title}]\n${currentTab.value.content}\n`;
    }
    
    for (const name of selectedArtefactNames.value) {
        const art = props.notebook.artefacts.find(a => a.filename === name);
        if (art) context += `\n\n[Source: ${name}]\n${art.content}\n`;
    }

    if (!context.trim()) {
        uiStore.addNotification("Please select artefacts or open a tab with content to use as a base.", "warning");
        return;
    }

    // 2. Create New Notebook
    const title = type === 'slides_making' ? 'New Presentation' : 'New Video Project';
    const newNotebook = await notebookStore.createStructuredNotebook({
        title: title,
        type: type,
        initialPrompt: "Initialize project from previous research.", // This triggers the ingestion/setup task
        raw_text: context // This puts the gathered context into the new notebook's artefacts immediately
    });

    if (newNotebook) {
        uiStore.addNotification("Project created! Switching views...", "success");
        await notebookStore.selectNotebook(newNotebook.id);
    }
}

// --- TAB MANAGEMENT ---

function handleCloseTab(id) {
    if (confirm("Delete this tab?")) {
        notebookStore.removeTab(id);
        if (activeTabId.value === id) activeTabId.value = null;
    }
}

// --- ARTEFACT EDITING ---
function viewArtefact(art) {
    uiStore.openModal('artefactViewer', { artefact: { title: art.filename, content: art.content } });
}
function openArtefactEditor(art) {
    editingArtefact.value = { originalName: art.filename, name: art.filename, content: art.content };
}
async function saveArtefactEdit() {
    if (!editingArtefact.value) return;
    try {
        await notebookStore.updateArtefact(editingArtefact.value.originalName, editingArtefact.value.name, editingArtefact.value.content);
        editingArtefact.value = null;
    } catch (e) { console.error(e); }
}
async function deleteArtefact(filename) {
    await notebookStore.deleteArtefact(filename);
}
</script>

<template>
    <div class="h-full flex overflow-hidden bg-gray-50 dark:bg-gray-950 relative">
        
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
                            <span class="text-[10px] font-black uppercase text-gray-500 tracking-widest">Process Terminal Output</span>
                            <div class="flex gap-1.5">
                                <div class="w-2 h-2 rounded-full bg-red-500/50"></div>
                                <div class="w-2 h-2 rounded-full bg-yellow-500/50"></div>
                                <div class="w-2 h-2 rounded-full bg-green-500/50"></div>
                            </div>
                        </div>
                        <div ref="logsContainerRef" class="flex-grow overflow-y-auto p-6 font-mono text-xs text-gray-400 space-y-1.5 custom-scrollbar">
                            <div v-for="(log, i) in activeTask.logs" :key="i" class="flex gap-4">
                                <span class="text-gray-700 shrink-0 select-none">[{{ new Date(log.timestamp).toLocaleTimeString() }}]</span> 
                                <span :class="{'text-red-400 font-bold': log.level === 'ERROR', 'text-blue-400': log.level === 'INFO', 'text-yellow-400': log.level === 'WARNING'}">
                                    {{ log.message }}
                                </span>
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

        <!-- Sidebar -->
        <div class="w-72 border-r dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col flex-shrink-0 transition-all">
            <div class="p-4 border-b dark:border-gray-800 font-black text-[10px] uppercase tracking-widest text-gray-500 flex justify-between items-center">
                <span>Research Data</span>
                <button @click="openImportWizard" class="text-green-500 hover:text-green-600 p-1 rounded hover:bg-green-50 dark:hover:bg-green-900/20"><IconPlus class="w-4 h-4" /></button>
            </div>
            
            <div class="flex-grow overflow-y-auto p-2 space-y-1 custom-scrollbar">
                <div v-if="notebook.artefacts.length === 0" class="text-center p-4 text-xs text-gray-400 italic">
                    No data sources yet.<br>Click + to import content.
                </div>
                <div v-for="art in notebook.artefacts" :key="art.filename" 
                     @click="toggleArtefact(art.filename)"
                     class="flex items-center gap-2 p-2 rounded cursor-pointer group transition-colors border border-transparent"
                     :class="selectedArtefactNames.includes(art.filename) ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 border-green-200 dark:border-green-800' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'">
                    <div class="flex-shrink-0">
                        <IconCheckCircle v-if="selectedArtefactNames.includes(art.filename)" class="w-4 h-4" />
                        <IconFileText v-else class="w-4 h-4 opacity-50" />
                    </div>
                    <span class="truncate text-xs font-medium flex-grow">{{ art.filename }}</span>
                    
                    <!-- Actions -->
                    <div class="flex items-center opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 bg-white/50 dark:bg-black/50 rounded px-1 backdrop-blur-sm">
                        <button @click.stop="viewArtefact(art)" class="p-1 hover:text-blue-500" title="View"><IconEye class="w-3 h-3" /></button>
                        <button @click.stop="openArtefactEditor(art)" class="p-1 hover:text-orange-500" title="Edit"><IconPencil class="w-3 h-3" /></button>
                        <button @click.stop="deleteArtefact(art.filename)" class="p-1 hover:text-red-500" title="Delete"><IconTrash class="w-3 h-3" /></button>
                    </div>
                </div>
            </div>

            <!-- Conversion Tools -->
            <div class="p-4 border-t dark:border-gray-800 bg-gray-50 dark:bg-gray-850">
                <p class="text-[9px] font-black uppercase text-gray-400 mb-2">Create Project from Selection</p>
                <div class="grid grid-cols-2 gap-2">
                    <button @click="convertToProject('slides_making')" class="flex flex-col items-center justify-center p-2 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded hover:border-blue-500 transition-colors text-center group">
                        <IconPresentationChartBar class="w-5 h-5 text-gray-400 group-hover:text-blue-500 mb-1" />
                        <span class="text-[10px] font-bold">Slides</span>
                    </button>
                    <button @click="convertToProject('youtube_video')" class="flex flex-col items-center justify-center p-2 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded hover:border-pink-500 transition-colors text-center group">
                        <IconVideoCamera class="w-5 h-5 text-gray-400 group-hover:text-pink-500 mb-1" />
                        <span class="text-[10px] font-bold">Video</span>
                    </button>
                </div>
            </div>
        </div>

        <!-- Main -->
        <div class="flex-grow flex flex-col overflow-hidden">
            <!-- Tab Bar -->
            <div class="bg-gray-100 dark:bg-gray-900 border-b dark:border-gray-700 pt-1 px-4 flex gap-1 overflow-x-auto no-scrollbar">
                <div v-for="tab in notebook.tabs" :key="tab.id" @click="activeTabId = tab.id" 
                     class="group relative px-4 py-2 rounded-t-lg cursor-pointer text-xs font-bold uppercase transition-all flex items-center gap-2 min-w-[100px] justify-between" 
                     :class="activeTabId === tab.id ? 'bg-white dark:bg-gray-950 text-blue-600 border-t border-x border-gray-300 dark:border-gray-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 bg-gray-200/50 dark:bg-gray-800/50 hover:bg-gray-200 dark:hover:bg-gray-800'">
                    <span class="truncate">{{ tab.title }}</span>
                    <button @click.stop="handleCloseTab(tab.id)" class="opacity-0 group-hover:opacity-100 hover:text-red-500 transition-opacity"><IconXMark class="w-3 h-3" /></button>
                </div>
                <button @click="notebookStore.addTab('markdown')" class="px-3 py-2 text-gray-400 hover:text-blue-500"><IconPlus class="w-4 h-4"/></button>
            </div>

            <!-- Editor / Viewer -->
            <div class="flex-grow flex flex-col relative min-h-0 bg-white dark:bg-gray-950">
                <template v-if="currentTab">
                    <!-- Tab Actions Toolbar -->
                    <div class="p-2 border-b dark:border-gray-700 flex justify-between items-center shadow-sm bg-white dark:bg-gray-950 z-10">
                        <input v-model="currentTab.title" @blur="notebookStore.saveActive" class="font-bold bg-transparent border-none focus:ring-0 text-gray-800 dark:text-gray-100 text-sm ml-2" />
                        
                        <div class="flex items-center gap-2">
                            <button @click="saveTabAsArtefact" class="btn btn-secondary btn-sm text-xs" title="Save this content as a reusable artefact">
                                <IconSave class="w-3 h-3 mr-1" /> To Artefact
                            </button>
                            <div class="h-4 w-px bg-gray-300 dark:bg-gray-700 mx-1"></div>
                            
                            <!-- Toggle View/Edit only for non-structured types -->
                            <div class="flex gap-1 bg-gray-100 dark:bg-gray-800 p-0.5 rounded border dark:border-gray-700" v-if="!['html', 'slides', 'youtube_storyboard', 'youtube_script'].includes(currentTab.type)">
                                <button @click="isRenderMode = true" class="p-1.5 rounded transition-colors" :class="isRenderMode ? 'bg-white dark:bg-gray-700 shadow text-blue-600' : 'text-gray-400 hover:text-gray-600'"><IconEye class="w-3.5 h-3.5"/></button>
                                <button @click="isRenderMode = false" class="p-1.5 rounded transition-colors" :class="!isRenderMode ? 'bg-white dark:bg-gray-700 shadow text-blue-600' : 'text-gray-400 hover:text-gray-600'"><IconPencil class="w-3.5 h-3.5"/></button>
                            </div>
                            <button @click="notebookStore.saveActive" class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500" title="Save changes"><IconSave class="w-4 h-4" /></button>
                        </div>
                    </div>

                    <!-- Content -->
                    <div class="flex-grow overflow-hidden relative">
                        <!-- HTML Viewer -->
                        <template v-if="currentTab.type === 'html'">
                            <iframe v-if="currentHtmlSrc" :src="currentHtmlSrc" class="w-full h-full border-none bg-white"></iframe>
                            <div v-else class="flex items-center justify-center h-full text-gray-400">No HTML Content</div>
                        </template>

                        <!-- SLIDES VIEWER -->
                        <template v-else-if="currentTab.type === 'slides' && slideData">
                            <div class="p-6 overflow-y-auto custom-scrollbar h-full bg-gray-50 dark:bg-gray-900">
                                <div class="max-w-4xl mx-auto space-y-6 pb-20">
                                    <div v-if="slideData.summary" class="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg text-sm">
                                        <h3 class="font-bold text-blue-700 dark:text-blue-300 mb-1">Deck Summary</h3>
                                        <p class="text-gray-700 dark:text-gray-300">{{ slideData.summary }}</p>
                                    </div>

                                    <div v-for="(slide, index) in slideData.slides_data" :key="index" class="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-xl overflow-hidden shadow-sm flex flex-col md:flex-row h-auto md:h-56">
                                        <div class="w-full md:w-1/3 bg-black relative flex-shrink-0">
                                             <AuthenticatedImage v-if="getSlideImage(slide)" :src="getSlideImage(slide)" class="w-full h-full object-cover" />
                                             <div v-else class="w-full h-full flex flex-col items-center justify-center text-gray-500 gap-2 bg-gray-100 dark:bg-gray-900"><IconPhoto class="w-8 h-8 opacity-20"/></div>
                                        </div>
                                        <div class="p-4 flex-1 flex flex-col overflow-y-auto custom-scrollbar">
                                            <div class="flex justify-between items-start mb-2">
                                                 <h4 class="font-bold text-lg text-gray-900 dark:text-white leading-tight">{{ slide.title }}</h4>
                                                 <span class="text-xs font-mono text-gray-400 ml-2">#{{ index + 1 }}</span>
                                            </div>
                                            <ul class="list-disc list-inside text-sm space-y-1 text-gray-600 dark:text-gray-300 mb-3 flex-grow">
                                                <li v-for="(bullet, bIdx) in slide.bullets" :key="bIdx">{{ bullet }}</li>
                                            </ul>
                                            <div v-if="slide.notes" class="text-xs text-gray-500 italic bg-gray-50 dark:bg-gray-900/50 p-2 rounded mt-auto border dark:border-gray-700">
                                                <span class="font-semibold not-italic text-gray-600 dark:text-gray-400">Speaker Notes:</span> {{ slide.notes }}
                                            </div>
                                        </div>
                                    </div>
                                    <div class="text-center text-xs text-gray-400">To edit these slides, use the "Create Project > Slides" option in the sidebar.</div>
                                </div>
                            </div>
                        </template>

                        <!-- STORYBOARD VIEWER -->
                        <template v-else-if="(currentTab.type === 'youtube_storyboard' || currentTab.type === 'youtube_script') && youtubeData">
                            <div class="p-6 overflow-y-auto custom-scrollbar h-full bg-gray-50 dark:bg-gray-900">
                                <div class="max-w-4xl mx-auto space-y-6 pb-20">
                                    <div v-for="(scene, index) in youtubeData.scenes" :key="index" class="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-xl overflow-hidden shadow-sm p-5">
                                        <div class="flex justify-between items-center mb-3 border-b dark:border-gray-700 pb-2">
                                            <h4 class="font-black text-base text-gray-900 dark:text-white">{{ scene.title }}</h4>
                                            <span class="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-[10px] uppercase font-bold text-gray-500">Scene {{ index + 1 }}</span>
                                        </div>
                                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            <div>
                                                <p class="text-[10px] font-bold uppercase text-blue-500 mb-1">Visual</p>
                                                <p class="text-sm text-gray-600 dark:text-gray-300 italic">{{ scene.visual_description }}</p>
                                            </div>
                                            <div>
                                                <p class="text-[10px] font-bold uppercase text-green-500 mb-1">Audio</p>
                                                <p class="text-sm text-gray-800 dark:text-gray-200">{{ scene.audio_script }}</p>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="text-center text-xs text-gray-400">To produce this video, use the "Create Project > Video" option in the sidebar.</div>
                                </div>
                            </div>
                        </template>
                        
                        <!-- Standard Markdown/Code -->
                        <template v-else>
                            <div v-if="isRenderMode" class="absolute inset-0 overflow-y-auto p-8 custom-scrollbar">
                                <MessageContentRenderer :content="currentTab.content" :key="currentTab.id + currentTab.content?.length" class="prose dark:prose-invert max-w-none" />
                            </div>
                            <CodeMirrorEditor v-else v-model="currentTab.content" @blur="notebookStore.saveActive" class="h-full" :language="currentTab.type === 'code' ? 'python' : 'markdown'" />
                        </template>
                    </div>
                </template>
                <div v-else class="flex-grow flex items-center justify-center text-gray-400 italic">Select a tab or create a new one.</div>
            </div>

            <!-- Prompt Bar -->
            <div class="p-4 border-t dark:border-gray-700 bg-white dark:bg-gray-900 flex flex-col gap-2 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)] z-20">
                <div class="flex items-center gap-2 overflow-x-auto no-scrollbar pb-1">
                    <span class="text-[10px] font-black uppercase text-gray-400 whitespace-nowrap">Quick Actions:</span>
                    <button @click="handleAction('summarize')" class="px-3 py-1 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-full text-xs font-bold border border-blue-100 dark:border-blue-900/30 hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors whitespace-nowrap"><IconFileText class="w-3 h-3 inline mr-1"/>Summarize</button>
                    <button @click="handleAction('generate_html')" class="px-3 py-1 bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 rounded-full text-xs font-bold border border-purple-100 dark:border-purple-900/30 hover:bg-purple-100 dark:hover:bg-purple-900/40 transition-colors whitespace-nowrap"><IconWeb class="w-3 h-3 inline mr-1"/>Visualize (HTML)</button>
                    <button @click="handleAction('generate_code')" class="px-3 py-1 bg-yellow-50 dark:bg-yellow-900/20 text-yellow-600 dark:text-yellow-400 rounded-full text-xs font-bold border border-yellow-100 dark:border-yellow-900/30 hover:bg-yellow-100 dark:hover:bg-yellow-900/40 transition-colors whitespace-nowrap"><IconCode class="w-3 h-3 inline mr-1"/>Generate Code</button>
                </div>
                <div class="flex gap-2 relative">
                    <input v-model="aiPrompt" @keyup.enter="handleProcess" placeholder="Ask AI to process selected data or write content..." class="input-field flex-grow pr-32" />
                    
                    <div class="flex items-center gap-2 px-2 border-l dark:border-gray-700 absolute right-16 top-1/2 -translate-y-1/2 bg-white dark:bg-gray-800 pl-2">
                        <input type="checkbox" id="mod-tab" v-model="modifyCurrentTab" class="h-3 w-3 rounded text-blue-600 focus:ring-blue-500 cursor-pointer"/>
                        <label for="mod-tab" class="text-[9px] font-black uppercase text-gray-400 cursor-pointer select-none whitespace-nowrap">Edit Active</label>
                    </div>
                    
                    <button @click="handleProcess" class="btn btn-primary px-4 absolute right-1 top-1 bottom-1 flex items-center justify-center rounded-lg" :disabled="(!aiPrompt.trim() && !selectedArtefactNames.length) || activeTask">
                        <IconArrowRight class="w-4 h-4"/>
                    </button>
                </div>
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
