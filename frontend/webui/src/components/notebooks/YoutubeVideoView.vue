<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue';
import { useNotebookStore } from '../../stores/notebooks';
import { useUiStore } from '../../stores/ui';
import { useTasksStore } from '../../stores/tasks';
import { useAuthStore } from '../../stores/auth'; 
import { storeToRefs } from 'pinia';
import AuthenticatedVideo from '../ui/AuthenticatedVideo.vue';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';

// Icons
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconVideoCamera from '../../assets/icons/IconVideoCamera.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconSave from '../../assets/icons/IconSave.vue';
import IconUserGroup from '../../assets/icons/IconUserGroup.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';

const props = defineProps({
    notebook: { type: Object, required: true }
});

const notebookStore = useNotebookStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();
const authStore = useAuthStore(); 
const { tasks } = storeToRefs(tasksStore);
const user = computed(() => authStore.user); 

const activeTabId = ref(null);
const selectedSceneIdx = ref(0);
const aiPrompt = ref('');
const logsContainerRef = ref(null);
const selectedArtefactNames = ref([]);
const showPersonalities = ref(false);
const modifyCurrentTab = ref(false); // NEW: Update Active Script

// WIZARD STATE
const isWizardOpen = ref(false);
const wizardStep = ref(1);
const wizardData = ref({
    topic: '',
    num_scenes: 5,
    target_duration: '2 minutes',
    style: 'Documentary',
    platform: 'YouTube (16:9)',
    selected_artefacts: [],
});

const styleOptions = ['Documentary', 'Vlog', 'Cinematic', 'Tutorial', 'News Report', 'Animation Script', 'Music Video'];
const platformOptions = ['YouTube (16:9)', 'YouTube Shorts (9:16)', 'TikTok (9:16)', 'Instagram Reel (9:16)'];

// Standardized Active Task Lookup
const activeTask = computed(() => {
    return tasks.value.find(t => 
        (t.name.includes(props.notebook.title) || t.description.includes(props.notebook.id)) && 
        (t.status === 'running' || t.status === 'pending')
    );
});

const scriptTab = computed(() => props.notebook.tabs?.find(t => t.type === 'youtube_script' || t.title === 'Script'));

const scriptData = computed(() => {
    if (!scriptTab.value) return { scenes: [], metadata: {}, personalities: [] };
    try { 
        const data = JSON.parse(scriptTab.value.content); 
        if (!data.personalities) data.personalities = [];
        return data;
    } catch (e) { return { scenes: [], metadata: {}, personalities: [] }; }
});

const currentTab = computed(() => props.notebook.tabs?.find(t => t.id === activeTabId.value) || scriptTab.value || props.notebook.tabs?.[0]);

const initYoutubeView = () => {
    if (props.notebook.tabs?.length > 0) {
        if (!activeTabId.value || !props.notebook.tabs.find(t => t.id === activeTabId.value)) {
            const script = props.notebook.tabs.find(t => t.type === 'youtube_script' || t.title === 'Script');
            activeTabId.value = script ? script.id : props.notebook.tabs[0].id;
        }
    }
};

watch(() => props.notebook.id, (newId, oldId) => {
    if (newId !== oldId) {
        activeTabId.value = null;
        initYoutubeView();
    }
}, { immediate: true });

watch(() => props.notebook.tabs, initYoutubeView, { deep: true });

// Auto-scroll logs
watch(() => activeTask.value?.logs?.length, () => {
    nextTick(() => {
        if (logsContainerRef.value) {
            logsContainerRef.value.scrollTop = logsContainerRef.value.scrollHeight;
        }
    });
});

// --- WIZARD ACTIONS ---
function openWizard() {
    wizardData.value = { 
        topic: '', 
        num_scenes: 5, 
        target_duration: '2 minutes', 
        style: 'Documentary', 
        platform: 'YouTube (16:9)',
        selected_artefacts: [...selectedArtefactNames.value]
    };
    wizardStep.value = 1; 
    isWizardOpen.value = true;
}

function toggleWizardArtefact(name) {
    const idx = wizardData.value.selected_artefacts.indexOf(name);
    if (idx === -1) wizardData.value.selected_artefacts.push(name);
    else wizardData.value.selected_artefacts.splice(idx, 1);
}

async function finalizeWizard() {
    isWizardOpen.value = false;
    // Pass config as JSON string in the prompt
    const configPayload = JSON.stringify(wizardData.value);
    await notebookStore.processWithAi(configPayload, [], 'generate_script', null, false, wizardData.value.selected_artefacts);
}

// --- STANDARD ACTIONS ---
async function generateScript() {
    if (!aiPrompt.value.trim()) return;
    
    // Determine target ID
    let targetId = null;
    if (modifyCurrentTab.value && scriptTab.value) {
        targetId = scriptTab.value.id;
    }
    
    // If not modifyCurrentTab, backend will create a new script tab.
    // If modifyCurrentTab is true, we update existing.
    
    await notebookStore.processWithAi(aiPrompt.value, [], 'generate_script', targetId, false, selectedArtefactNames.value);
    aiPrompt.value = '';
}

async function renderVideo() {
    const { confirmed } = await uiStore.showConfirmation({ title: 'Render Video', message: 'Generate visuals and synthesis audio?', confirmText: 'Start' });
    if (confirmed) await notebookStore.processWithAi("Render full video", [scriptTab.value?.id], 'generate_animation');
}

async function updateScript(newData) {
    if (!scriptTab.value) return;
    scriptTab.value.content = JSON.stringify(newData);
    await notebookStore.saveActive();
}

async function addScene() {
    const data = JSON.parse(JSON.stringify(scriptData.value));
    data.scenes.push({ id: Math.random().toString(36).substr(2, 9), title: `Scene ${data.scenes.length + 1}`, content: '', visual_description: '', audio_script: '' });
    await updateScript(data);
    selectedSceneIdx.value = data.scenes.length - 1;
}

async function removeScene(idx) {
    const data = JSON.parse(JSON.stringify(scriptData.value));
    data.scenes.splice(idx, 1);
    await updateScript(data);
    if (selectedSceneIdx.value >= data.scenes.length) selectedSceneIdx.value = Math.max(0, data.scenes.length - 1);
}

async function updateSceneField(field, value) {
    const data = JSON.parse(JSON.stringify(scriptData.value));
    if (data.scenes[selectedSceneIdx.value]) { data.scenes[selectedSceneIdx.value][field] = value; await updateScript(data); }
}

async function generatePersonalities() {
    await notebookStore.processWithAi("Extract and generate characters", [scriptTab.value.id], 'generate_personalities', scriptTab.value.id);
    showPersonalities.value = true;
}

async function regeneratePersonality(personId) {
    await notebookStore.processWithAi(personId, [scriptTab.value.id], 'regenerate_personality', scriptTab.value.id);
}

async function deletePersonality(idx) {
    const data = JSON.parse(JSON.stringify(scriptData.value));
    data.personalities.splice(idx, 1);
    await updateScript(data);
}

async function togglePersonalityForScene(personId, sceneIdx) {
    const data = JSON.parse(JSON.stringify(scriptData.value));
    const scene = data.scenes[sceneIdx];
    if (!scene.selected_personalities) scene.selected_personalities = [];
    
    const idx = scene.selected_personalities.indexOf(personId);
    if (idx === -1) scene.selected_personalities.push(personId);
    else scene.selected_personalities.splice(idx, 1);
    
    await updateScript(data);
}

async function generateSceneImage(sceneIdx) {
    await notebookStore.processWithAi(`SCENE_INDEX:${sceneIdx}`, [scriptTab.value.id], 'generate_scene_image', scriptTab.value.id);
}

function viewImage(path) {
    uiStore.openImageViewer({ imageList: [{ src: path }], startIndex: 0 });
}

function toggleArtefact(name) {
    const idx = selectedArtefactNames.value.indexOf(name);
    if (idx === -1) selectedArtefactNames.value.push(name);
    else selectedArtefactNames.value.splice(idx, 1);
}

function openImportWizard() {
    uiStore.openModal('artefactImportWizard', { notebookId: props.notebook.id });
}

onUnmounted(() => { if (recognition && isRecording.value) recognition.stop(); });
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
                            <span class="text-[10px] font-black uppercase text-gray-500 tracking-widest">Video Studio Terminal Output</span>
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

        <!-- WIZARD MODAL -->
        <transition enter-active-class="transition ease-out duration-200" enter-from-class="opacity-0 translate-y-4" enter-to-class="opacity-100 translate-y-0" leave-active-class="transition ease-in duration-150" leave-from-class="opacity-100 translate-y-0" leave-to-class="opacity-0 translate-y-4">
            <div v-if="isWizardOpen" class="fixed inset-0 z-[100] bg-gray-900/60 backdrop-blur-sm p-6 flex items-center justify-center" @click.self="isWizardOpen = false">
                <div class="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-3xl flex flex-col overflow-hidden border dark:border-gray-800">
                    <div class="p-4 border-b dark:border-gray-800 flex justify-between items-center bg-gray-50 dark:bg-gray-800/50"><h3 class="font-black text-sm uppercase tracking-widest flex items-center gap-2"><IconPlus class="w-4 h-4" /> New Video Project</h3><button @click="isWizardOpen = false" class="btn-icon-flat"><IconXMark class="w-5 h-5"/></button></div>
                    <div class="p-8 overflow-y-auto custom-scrollbar min-h-[450px]">
                        
                        <div v-if="wizardStep === 1" class="space-y-6">
                            <div>
                                <label class="text-[10px] font-black uppercase text-blue-500 mb-2 block tracking-widest">1. Video Concept</label>
                                <textarea v-model="wizardData.topic" class="input-field w-full h-32 font-bold text-lg p-4" placeholder="What is this video about? (e.g. A documentary about Mars colonization...)"></textarea>
                            </div>
                            <div>
                                <label class="text-[10px] font-black uppercase text-gray-500 mb-2 block tracking-widest">2. Research Sources</label>
                                <div class="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto p-2 border rounded-xl dark:border-gray-800">
                                    <button v-for="art in notebook.artefacts" :key="art.filename" @click="toggleWizardArtefact(art.filename)" class="p-2 rounded-lg text-[10px] flex items-center gap-2 text-left transition-all border" :class="wizardData.selected_artefacts.includes(art.filename) ? 'bg-green-50 border-green-500 text-green-700' : 'border-transparent hover:bg-gray-50 text-gray-500'">
                                        <IconCheckCircle v-if="wizardData.selected_artefacts.includes(art.filename)" class="w-3 h-3 flex-shrink-0" /><IconFileText v-else class="w-3 h-3 opacity-30 flex-shrink-0" /><span class="truncate">{{ art.filename }}</span>
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div v-if="wizardStep === 2" class="space-y-6">
                            <label class="text-[10px] font-black uppercase text-blue-500 mb-4 block tracking-widest">3. Configuration</label>
                            <div class="grid grid-cols-2 gap-6">
                                <div>
                                    <label class="label mb-2">Style / Genre</label>
                                    <select v-model="wizardData.style" class="input-field w-full">
                                        <option v-for="opt in styleOptions" :key="opt" :value="opt">{{ opt }}</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="label mb-2">Platform / Format</label>
                                    <select v-model="wizardData.platform" class="input-field w-full">
                                        <option v-for="opt in platformOptions" :key="opt" :value="opt">{{ opt }}</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="label mb-2">Target Duration</label>
                                    <input v-model="wizardData.target_duration" class="input-field w-full" placeholder="e.g. 5 minutes" />
                                </div>
                                <div>
                                    <label class="label mb-2">Approx. Scene Count</label>
                                    <input type="number" v-model.number="wizardData.num_scenes" class="input-field w-full" min="1" max="50" />
                                </div>
                            </div>
                        </div>

                    </div>
                    <div class="p-4 border-t dark:border-gray-800 flex justify-between gap-3 bg-gray-50 dark:bg-gray-900/50">
                        <button v-if="wizardStep > 1" @click="wizardStep--" class="btn btn-secondary">Back</button>
                        <div v-else></div>
                        <div class="flex gap-2">
                            <button @click="isWizardOpen = false" class="btn btn-secondary">Cancel</button>
                            <button v-if="wizardStep === 1" @click="wizardStep = 2" class="btn btn-primary" :disabled="!wizardData.topic">Next</button>
                            <button v-if="wizardStep === 2" @click="finalizeWizard" class="btn btn-primary">Generate Script</button>
                        </div>
                    </div>
                </div>
            </div>
        </transition>

        <!-- LEFT SIDEBAR -->
        <div class="w-72 border-r dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col flex-shrink-0 transition-all duration-300">
            <div class="p-4 border-b dark:border-gray-800 font-black text-[10px] uppercase tracking-widest text-gray-500 flex justify-between items-center">
                <span>Video Studio</span>
                <div class="flex gap-2">
                    <button @click="showPersonalities = !showPersonalities" class="text-blue-500 hover:text-blue-600" title="Toggle Personalities"><IconUserGroup class="w-4 h-4" /></button>
                    <button @click="addScene" class="text-blue-500 hover:text-blue-600" title="Add Scene"><IconPlus class="w-4 h-4" /></button>
                </div>
            </div>
            
            <div class="flex-grow overflow-y-auto p-3 space-y-4 custom-scrollbar">
                <!-- PERSONALITIES PANEL -->
                <div v-if="showPersonalities" class="bg-blue-50 dark:bg-blue-900/10 rounded-xl p-3 border border-blue-100 dark:border-blue-900/30 mb-4 animate-in slide-in-from-left duration-300">
                    <div class="flex justify-between items-center mb-3">
                        <span class="text-xs font-bold text-blue-700 dark:text-blue-300">Cast & Characters</span>
                        <button @click="generatePersonalities" class="p-1 bg-blue-100 dark:bg-blue-800 text-blue-600 dark:text-blue-200 rounded hover:bg-blue-200 transition-colors" title="Auto-generate from Script"><IconSparkles class="w-3 h-3" /></button>
                    </div>
                    
                    <div v-if="scriptData.personalities.length === 0" class="text-[10px] text-center text-gray-400 italic py-2">
                        No characters yet.
                    </div>
                    
                    <div class="space-y-2">
                        <div v-for="(p, idx) in scriptData.personalities" :key="p.id" class="flex items-center gap-2 bg-white dark:bg-gray-800 p-2 rounded-lg shadow-sm">
                            <div class="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-700 flex-shrink-0 overflow-hidden cursor-pointer border border-gray-200 dark:border-gray-600" @click="viewImage(p.image_path)">
                                <AuthenticatedImage v-if="p.image_path" :src="p.image_path" class="w-full h-full object-cover" />
                                <IconUserGroup v-else class="w-4 h-4 m-2 text-gray-400" />
                            </div>
                            <div class="min-w-0 flex-grow">
                                <p class="text-xs font-bold truncate">{{ p.name }}</p>
                            </div>
                            <div class="flex gap-1">
                                <button @click="regeneratePersonality(p.id)" class="text-gray-400 hover:text-blue-500"><IconRefresh class="w-3 h-3" /></button>
                                <button @click="deletePersonality(idx)" class="text-gray-400 hover:text-red-500"><IconXMark class="w-3 h-3" /></button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- SCENES LIST -->
                <div v-if="scriptTab" @click="activeTabId = scriptTab.id" class="p-3 rounded-xl border-2 cursor-pointer transition-all shadow-sm" :class="activeTabId === scriptTab.id ? 'border-red-500 bg-red-50 dark:bg-red-900/10' : 'border-transparent bg-gray-50 dark:bg-gray-800 hover:border-gray-300'">
                    <div class="flex items-center gap-2 mb-1 text-red-600"><IconFileText class="w-4 h-4"/> <span class="font-bold text-xs uppercase">Master Script</span></div>
                    <p class="text-[10px] opacity-70">{{ scriptData.scenes.length }} Scenes</p>
                </div>
                
                <div v-if="activeTabId === scriptTab?.id" class="space-y-1">
                    <div v-for="(scene, idx) in scriptData.scenes" :key="idx" @click="selectedSceneIdx = idx" class="group flex items-center justify-between p-2 rounded-lg cursor-pointer text-sm transition-all" :class="selectedSceneIdx === idx ? 'bg-gray-200 dark:bg-gray-700 font-bold text-gray-900 dark:text-white' : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'">
                        <div class="flex items-center gap-2 truncate min-w-0"><span class="w-4 h-4 flex items-center justify-center bg-gray-300 dark:bg-gray-600 rounded-full text-[8px] flex-shrink-0">{{ idx + 1 }}</span><span class="truncate">{{ scene.title }}</span></div>
                        <button @click.stop="removeScene(idx)" class="opacity-0 group-hover:opacity-100 hover:text-red-500 p-1"><IconTrash class="w-3.5 h-3.5" /></button>
                    </div>
                </div>
            </div>
            
            <div class="p-4 border-t dark:border-gray-800"><button @click="renderVideo" class="btn btn-primary w-full" :disabled="activeTask || !scriptTab"><IconVideoCamera class="w-4 h-4 mr-2" /> Render Video</button></div>
        </div>

        <!-- Main Workspace -->
        <div class="flex-grow flex flex-col relative min-w-0">
            <!-- Empty State -->
            <div v-if="scriptData.scenes.length === 0" class="absolute inset-0 flex items-center justify-center p-8 text-center bg-gray-50 dark:bg-gray-900/50">
                <div class="max-w-md">
                    <div class="w-20 h-20 bg-gray-100 dark:bg-gray-800 rounded-full flex items-center justify-center mx-auto mb-6">
                        <IconVideoCamera class="w-10 h-10 text-gray-400" />
                    </div>
                    <h2 class="text-2xl font-bold text-gray-800 dark:text-white mb-3">Start Your Video Production</h2>
                    <p class="text-gray-500 dark:text-gray-400 mb-8">Use the wizard to generate a professional script and storyboard from your topic or documents.</p>
                    <button @click="openWizard" class="btn btn-primary px-8 py-3 text-lg shadow-xl hover:shadow-blue-500/20 transition-all">
                        <IconSparkles class="w-5 h-5 mr-2" /> Open Video Wizard
                    </button>
                </div>
            </div>

            <template v-else-if="currentTab">
                <!-- TOP BAR -->
                <div class="p-3 border-b dark:border-gray-800 flex justify-between items-center bg-white dark:bg-gray-900 shadow-sm z-10">
                    <div class="flex items-center gap-3"><input v-model="currentTab.title" @blur="notebookStore.saveActive" class="font-black text-lg bg-transparent border-none focus:ring-0 text-gray-800 dark:text-white p-0" /></div>
                    <div class="flex items-center gap-3"><button @click="notebookStore.saveActive" class="btn btn-secondary btn-sm"><IconSave class="w-4 h-4 mr-2" /> Save</button></div>
                </div>

                <!-- SCENE EDITOR -->
                <div class="flex-grow overflow-hidden relative">
                    <div v-if="currentTab.type === 'youtube_script'" class="absolute inset-0 flex flex-col md:flex-row overflow-hidden">
                        <div class="flex-grow overflow-y-auto p-6 md:p-10 custom-scrollbar bg-gray-50/30 dark:bg-transparent">
                            <div v-if="scriptData.scenes[selectedSceneIdx]" class="max-w-4xl mx-auto space-y-8 animate-in fade-in duration-300">
                                
                                <!-- Scene Header -->
                                <div>
                                    <label class="text-[10px] font-black uppercase text-gray-400 mb-2 block">Scene Title</label>
                                    <input :value="scriptData.scenes[selectedSceneIdx].title" @input="updateSceneField('title', $event.target.value)" class="w-full bg-transparent border-b-2 border-gray-200 dark:border-gray-800 focus:border-red-500 transition-colors py-2 text-2xl font-black outline-none dark:text-white" />
                                </div>

                                <!-- Cast Selector -->
                                <div v-if="scriptData.personalities.length > 0">
                                    <label class="text-[10px] font-black uppercase text-gray-400 mb-2 block">Scene Cast</label>
                                    <div class="flex flex-wrap gap-2">
                                        <button 
                                            v-for="p in scriptData.personalities" 
                                            :key="p.id"
                                            @click="togglePersonalityForScene(p.id, selectedSceneIdx)"
                                            class="flex items-center gap-2 px-3 py-1.5 rounded-full border transition-all text-xs font-bold"
                                            :class="(scriptData.scenes[selectedSceneIdx].selected_personalities || []).includes(p.id) ? 'bg-blue-100 border-blue-500 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300' : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-500 hover:border-blue-300'"
                                        >
                                            <div class="w-4 h-4 rounded-full bg-gray-300 overflow-hidden"><AuthenticatedImage v-if="p.image_path" :src="p.image_path" class="w-full h-full object-cover" /></div>
                                            {{ p.name }}
                                        </button>
                                    </div>
                                </div>

                                <!-- Script & Visuals -->
                                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                    <div>
                                        <label class="text-[10px] font-black uppercase text-gray-400 mb-3 block">Narration</label>
                                        <textarea :value="scriptData.scenes[selectedSceneIdx].audio_script" @input="updateSceneField('audio_script', $event.target.value)" class="w-full bg-white dark:bg-gray-900 border dark:border-gray-800 rounded-2xl p-5 min-h-[200px] text-lg leading-relaxed dark:text-gray-200 shadow-sm" placeholder="Narration script..."></textarea>
                                    </div>
                                    <div class="flex flex-col gap-4">
                                        <div>
                                            <label class="text-[10px] font-black uppercase text-gray-400 mb-3 block">Visual Direction</label>
                                            <textarea :value="scriptData.scenes[selectedSceneIdx].visual_description" @input="updateSceneField('visual_description', $event.target.value)" class="w-full bg-blue-50/50 dark:bg-blue-900/10 border border-blue-100 dark:border-blue-900/20 rounded-2xl p-5 text-sm italic dark:text-gray-300 min-h-[100px]" placeholder="Visual Prompt..."></textarea>
                                        </div>
                                        
                                        <!-- Generated Image Preview -->
                                        <div class="bg-black rounded-2xl overflow-hidden aspect-video relative group shadow-lg border dark:border-gray-800">
                                            <AuthenticatedImage v-if="scriptData.scenes[selectedSceneIdx].image_path" :src="scriptData.scenes[selectedSceneIdx].image_path" class="w-full h-full object-contain" />
                                            <div v-else class="w-full h-full flex items-center justify-center text-gray-600">
                                                <IconPhoto class="w-12 h-12 opacity-20" />
                                            </div>
                                            
                                            <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                                <button @click="generateSceneImage(selectedSceneIdx)" class="btn btn-primary shadow-xl">
                                                    <IconSparkles class="w-4 h-4 mr-2" /> {{ scriptData.scenes[selectedSceneIdx].image_path ? 'Regenerate' : 'Generate Visual' }}
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                            </div>
                        </div>
                    </div>
                    
                    <div v-else-if="currentTab.type === 'video'" class="absolute inset-0 p-10 bg-black flex items-center justify-center">
                        <AuthenticatedVideo :src="currentTab.content" />
                    </div>
                </div>
            </template>
        </div>

        <div class="p-4 border-t dark:border-gray-800 bg-white dark:bg-gray-900 flex gap-4 shadow-2xl z-20">
            <div class="relative flex-grow">
                <input v-model="aiPrompt" @keyup.enter="generateScript" placeholder="Quickly modify script or scene..." class="input-field w-full pr-32" />
                <div class="flex items-center gap-2 px-2 border-l dark:border-gray-700 absolute right-1 top-1/2 -translate-y-1/2 bg-white dark:bg-gray-800 pl-2 h-8">
                    <input type="checkbox" id="mod-tab" v-model="modifyCurrentTab" class="h-3 w-3 rounded text-blue-600 focus:ring-blue-500 cursor-pointer"/>
                    <label for="mod-tab" class="text-[9px] font-black uppercase text-gray-400 cursor-pointer select-none whitespace-nowrap">Update Active</label>
                </div>
            </div>
            <button @click="generateScript" class="btn btn-primary px-8 h-12 rounded-2xl" :disabled="!aiPrompt.trim() || activeTask"><IconSparkles class="w-4 h-4 mr-2"/> Go</button>
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
