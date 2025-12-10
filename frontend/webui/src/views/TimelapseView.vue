<template>
    <div class="h-full flex flex-col bg-gray-50 dark:bg-gray-900 overflow-hidden relative">
        <!-- Header -->
        <div class="h-14 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-4 z-20 shadow-sm flex-shrink-0">
            <div class="flex items-center gap-4">
                <router-link to="/image-studio" class="btn-icon" title="Back to Image Studio">
                    <IconArrowLeft class="w-5 h-5" />
                </router-link>
                <div class="flex items-center gap-2">
                    <IconFilm class="w-5 h-5 text-blue-500" />
                    <h1 class="text-lg font-semibold text-gray-800 dark:text-gray-200">Timelapse Creator</h1>
                </div>
            </div>
            
            <div class="flex items-center gap-2">
                <button @click="generateTimelapse" class="btn btn-primary btn-sm gap-2" :disabled="isGenerating || keyframes.length < 2">
                    <IconAnimateSpin v-if="isGenerating" class="w-4 h-4 animate-spin" />
                    <IconPlayCircle v-else class="w-4 h-4" />
                    {{ isGenerating ? 'Rendering...' : 'Generate Video' }}
                </button>
            </div>
        </div>

        <!-- Main Content -->
        <div class="flex-grow flex min-h-0 overflow-hidden">
            <!-- Storyboard / Keyframes List -->
            <div class="w-96 flex-shrink-0 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col overflow-hidden">
                <div class="p-3 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex justify-between items-center">
                    <h3 class="font-semibold text-sm">Storyboard</h3>
                    <button @click="addKeyframe" class="btn btn-secondary btn-sm text-xs gap-1">
                        <IconPlus class="w-3 h-3" /> Add Frame
                    </button>
                </div>
                
                <div class="flex-grow overflow-y-auto p-3 space-y-3 custom-scrollbar">
                    <div v-for="(frame, index) in keyframes" :key="index" class="p-3 bg-gray-100 dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600 relative group transition-all hover:shadow-md">
                        <div class="flex justify-between items-start mb-2">
                            <span class="text-xs font-bold text-gray-500 bg-gray-200 dark:bg-gray-600 px-1.5 rounded">Frame {{ index + 1 }}</span>
                            <button @click="removeKeyframe(index)" class="text-red-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity" title="Remove Frame">
                                <IconTrash class="w-4 h-4" />
                            </button>
                        </div>
                        
                        <div class="space-y-2">
                            <div>
                                <label class="text-[10px] font-semibold text-gray-500 uppercase">Prompt</label>
                                <textarea v-model="frame.prompt" rows="2" class="input-field w-full text-xs" placeholder="Scene description..."></textarea>
                            </div>
                            <div class="flex gap-2">
                                <div class="flex-1">
                                    <label class="text-[10px] font-semibold text-gray-500 uppercase">Duration (s)</label>
                                    <input type="number" v-model.number="frame.duration" min="0.1" step="0.1" class="input-field w-full text-xs">
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <button @click="addKeyframe" class="w-full py-3 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg text-gray-400 hover:border-blue-400 hover:text-blue-500 transition-colors flex items-center justify-center gap-2 text-sm">
                        <IconPlus class="w-4 h-4" /> Add Keyframe
                    </button>
                </div>
            </div>

            <!-- Preview & Settings Area -->
            <div class="flex-grow flex flex-col min-w-0 bg-gray-100 dark:bg-gray-900 overflow-y-auto p-6">
                
                <div class="max-w-4xl mx-auto w-full space-y-6">
                    <!-- Global Settings -->
                    <div class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
                        <h3 class="font-semibold text-sm mb-4 border-b pb-2 dark:border-gray-700">Global Settings</h3>
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div>
                                <label class="label text-xs">Width</label>
                                <input type="number" v-model.number="width" class="input-field mt-1 w-full" step="64">
                            </div>
                            <div>
                                <label class="label text-xs">Height</label>
                                <input type="number" v-model.number="height" class="input-field mt-1 w-full" step="64">
                            </div>
                            <div>
                                <label class="label text-xs">FPS</label>
                                <input type="number" v-model.number="fps" class="input-field mt-1 w-full">
                            </div>
                            <div>
                                <label class="label text-xs">Transition (s)</label>
                                <input type="number" v-model.number="transitionDuration" class="input-field mt-1 w-full" step="0.1">
                            </div>
                            <div class="col-span-2">
                                <label class="label text-xs">Model</label>
                                <select v-model="selectedModel" class="input-field mt-1 w-full">
                                    <option v-for="m in compatibleModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                                </select>
                            </div>
                            <div class="col-span-2">
                                <label class="label text-xs">Negative Prompt (Global)</label>
                                <input type="text" v-model="negativePrompt" class="input-field mt-1 w-full">
                            </div>
                        </div>
                    </div>

                    <!-- Result Area -->
                    <div v-if="generatedResult" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 flex flex-col items-center">
                        <h3 class="font-semibold text-sm mb-4 w-full text-left">Result</h3>
                        
                        <div v-if="generatedResult.type === 'video'" class="w-full max-w-lg aspect-video bg-black rounded-lg overflow-hidden relative shadow-lg">
                            <video controls class="w-full h-full object-contain" :src="generatedResult.video_url"></video>
                        </div>
                        
                        <div v-else class="w-full overflow-x-auto p-2">
                            <p class="text-sm text-gray-500 mb-2">Video generation skipped or failed. Frames:</p>
                            <div class="flex gap-2">
                                <img v-for="(img, idx) in generatedResult.images" :key="idx" :src="img" class="h-32 w-auto rounded border border-gray-300 dark:border-gray-600">
                            </div>
                        </div>

                        <div class="mt-4 flex gap-3">
                            <a v-if="generatedResult.type === 'video'" :href="generatedResult.video_url" :download="generatedResult.filename" class="btn btn-primary gap-2">
                                <IconArrowDownTray class="w-4 h-4" /> Download Video
                            </a>
                        </div>
                    </div>
                    
                    <div v-else-if="isGenerating" class="flex flex-col items-center justify-center py-12 text-gray-400">
                        <IconAnimateSpin class="w-12 h-12 text-blue-500 mb-4 animate-spin" />
                        <p class="text-lg font-medium text-gray-600 dark:text-gray-300">Generating frames & compiling video...</p>
                        <p class="text-sm">This may take a while depending on the number of frames.</p>
                    </div>

                    <div v-else class="flex flex-col items-center justify-center py-12 text-gray-400 border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-lg">
                        <IconFilm class="w-12 h-12 mb-2" />
                        <p>Configure keyframes and click Generate</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, h } from 'vue';
import { useDataStore } from '../stores/data';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import apiClient from '../services/api';
import useEventBus from '../services/eventBus';

// Icons
import IconArrowLeft from '../assets/icons/IconArrowLeft.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconPlayCircle from '../assets/icons/IconPlayCircle.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';

// Custom Icon for Film
const IconFilm = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [
    h('rect', { x: '2', y: '2', width: '20', height: '20', rx: '2.18', ry: '2.18' }),
    h('line', { x1: '7', y1: '2', x2: '7', y2: '22' }),
    h('line', { x1: '17', y1: '2', x2: '17', y2: '22' }),
    h('line', { x1: '2', y1: '12', x2: '22', y2: '12' }),
    h('line', { x1: '2', y1: '7', x2: '7', y2: '7' }),
    h('line', { x1: '2', y1: '17', x2: '7', y2: '17' }),
    h('line', { x1: '17', y1: '17', x2: '22', y2: '17' }),
    h('line', { x1: '17', y1: '7', x2: '22', y2: '7' })
]) };

const dataStore = useDataStore();
const authStore = useAuthStore();
const uiStore = useUiStore();
const { on, off } = useEventBus();

const keyframes = ref([
    { prompt: 'A sunrise over a calm ocean', duration: 3.0 },
    { prompt: 'A sunny day at the beach with palm trees', duration: 3.0 },
    { prompt: 'A sunset over the ocean with vibrant colors', duration: 3.0 }
]);

const width = ref(512);
const height = ref(512);
const fps = ref(24);
const transitionDuration = ref(1.0);
const negativePrompt = ref('');
const selectedModel = ref('');
const isGenerating = ref(false);
const generatedResult = ref(null);
const activeTaskId = ref(null);

const compatibleModels = computed(() => dataStore.availableTtiModels);

onMounted(() => {
    if (authStore.user) {
        selectedModel.value = authStore.user.tti_binding_model_name || '';
    }
    if (compatibleModels.value.length === 0) {
        dataStore.fetchAvailableTtiModels();
    }
    on('task:completed', handleTaskCompletion);
    on('task:failed', handleTaskFailure);
});

onUnmounted(() => {
    off('task:completed', handleTaskCompletion);
    off('task:failed', handleTaskFailure);
});

function addKeyframe() {
    keyframes.value.push({ prompt: '', duration: 3.0 });
}

function removeKeyframe(index) {
    keyframes.value.splice(index, 1);
}

async function generateTimelapse() {
    if (keyframes.value.length < 2) {
        uiStore.addNotification('Add at least 2 keyframes.', 'warning');
        return;
    }
    if (!selectedModel.value) {
        uiStore.addNotification('Select a model.', 'warning');
        return;
    }

    isGenerating.value = true;
    generatedResult.value = null;

    try {
        const response = await apiClient.post('/api/image-studio/timelapse', {
            keyframes: keyframes.value,
            negative_prompt: negativePrompt.value,
            model: selectedModel.value,
            width: width.value,
            height: height.value,
            fps: fps.value,
            transition_duration: transitionDuration.value
        });
        if (response.data && response.data.id) {
            activeTaskId.value = response.data.id;
        }
        uiStore.addNotification('Timelapse task started.', 'info');
    } catch (e) {
        console.error(e);
        isGenerating.value = false;
        uiStore.addNotification('Failed to start task.', 'error');
    }
}

function handleTaskCompletion(task) {
    if (activeTaskId.value && task.id === activeTaskId.value) {
        isGenerating.value = false;
        if (task.status === 'completed' && task.result) {
            generatedResult.value = typeof task.result === 'string' ? JSON.parse(task.result) : task.result;
            uiStore.addNotification('Timelapse ready!', 'success');
        } else {
            uiStore.addNotification('Timelapse generation failed or cancelled.', 'error');
        }
        activeTaskId.value = null;
    }
}

function handleTaskFailure(task) {
    if (activeTaskId.value && task.id === activeTaskId.value) {
        isGenerating.value = false;
        activeTaskId.value = null;
        uiStore.addNotification('Timelapse generation failed.', 'error');
    }
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background-color: rgba(156, 163, 175, 0.5); border-radius: 20px; }
</style>
