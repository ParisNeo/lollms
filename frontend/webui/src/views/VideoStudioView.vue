<template>
    <!-- Header portals mirror the Image Studio pattern -->
    <Teleport to="#global-header-title-target" v-if="hasHeaderTarget">
        <div class="flex items-center gap-2 pointer-events-auto bg-gray-100/80 dark:bg-gray-800/80 px-3 py-1.5 rounded-xl border dark:border-gray-700/50 backdrop-blur-md transition-all shadow-inner">
            <div class="flex flex-col min-w-0">
                <span class="text-[9px] font-black uppercase tracking-widest text-primary leading-none">Video Studio</span>
                <h2 class="font-bold text-gray-800 dark:text-gray-200 text-xs truncate max-w-[220px]">
                    {{ activeProject?.title || 'No project selected' }}
                </h2>
            </div>
        </div>
    </Teleport>

    <Teleport to="#global-header-actions-target" v-if="hasHeaderTarget">
        <div class="flex items-center gap-2 pointer-events-auto">
            <button @click="refresh" class="btn-icon p-1.5 text-gray-500 hover:text-blue-600" title="Refresh">
                <IconRefresh class="w-4 h-4" :class="{ 'animate-spin': isLoading }" />
            </button>
            <button @click="newProject" class="btn btn-secondary px-3 py-2 text-xs font-bold flex items-center gap-1">
                <IconPlus class="w-4 h-4" />
                <span class="hidden sm:inline">New Project</span>
            </button>
        </div>
    </Teleport>

    <div class="h-full flex flex-col bg-gray-50 dark:bg-gray-950 overflow-hidden">
        <!-- No TTV notice -->
        <div v-if="!capabilities.ttv_available" class="p-6">
            <div class="max-w-xl mx-auto text-center p-8 rounded-2xl bg-white dark:bg-gray-900 border dark:border-gray-800 shadow-sm">
                <IconVideoCamera class="w-12 h-12 mx-auto mb-4 text-gray-400" />
                <h2 class="text-lg font-bold text-gray-800 dark:text-gray-200 mb-2">Text-to-Video is not configured</h2>
                <p class="text-sm text-gray-500 dark:text-gray-400">
                    Ask your administrator to activate a Text-to-Video (TTV) binding (e.g. <code class="text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">vllm_omni</code>) before creating video projects.
                </p>
            </div>
        </div>

        <div v-else class="grow min-h-0 flex overflow-hidden">
            <!-- ── PROJECTS LIST ── -->
            <aside class="w-72 shrink-0 border-r dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col">
                <div class="p-3 border-b dark:border-gray-800 flex items-center justify-between">
                    <div>
                        <p class="text-[10px] font-black uppercase tracking-widest text-gray-400">Projects</p>
                        <p class="text-xs text-gray-500">{{ projects.length }} {{ projects.length === 1 ? 'project' : 'projects' }}</p>
                    </div>
                    <button @click="newProject" class="btn-icon p-1.5 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-md" title="New Project">
                        <IconPlus class="w-4 h-4" />
                    </button>
                </div>

                <div class="grow overflow-y-auto p-2 space-y-1 custom-scrollbar">
                    <div v-if="isLoading && projects.length === 0" class="p-4 text-center text-xs text-gray-400">
                        Loading projects...
                    </div>
                    <div v-else-if="projects.length === 0" class="p-4 text-center text-xs text-gray-400">
                        <IconVideoCamera class="w-8 h-8 mx-auto mb-2 opacity-30" />
                        No projects yet.<br />Click <strong>New Project</strong> to start.
                    </div>
                    <button v-for="p in projects" :key="p.id"
                        @click="activeProjectId = p.id"
                        class="w-full text-left p-2.5 rounded-xl transition-colors border"
                        :class="activeProjectId === p.id
                            ? 'bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800'
                            : 'border-transparent hover:bg-gray-100 dark:hover:bg-gray-800'"
                    >
                        <div class="flex items-start justify-between gap-2">
                            <div class="min-w-0 flex-1">
                                <p class="text-xs font-bold text-gray-800 dark:text-gray-200 truncate">{{ p.title }}</p>
                                <p class="text-[10px] text-gray-400 truncate uppercase tracking-wider mt-0.5">
                                    {{ p.source_type }} • {{ p.width }}×{{ p.height }}
                                </p>
                                <span v-if="p.video_filename" class="inline-flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400 mt-1">
                                    <IconCheckCircle class="w-3 h-3" /> rendered
                                </span>
                                <span v-else class="inline-flex items-center gap-1 text-[10px] text-gray-400 mt-1">
                                    <IconClock class="w-3 h-3" /> not rendered
                                </span>
                            </div>
                            <button @click.stop="deleteProject(p)" class="p-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100" title="Delete">
                                <IconTrash class="w-3.5 h-3.5" />
                            </button>
                        </div>
                    </button>
                </div>
            </aside>

            <!-- ── PROJECT WORKBENCH ── -->
            <main class="grow min-w-0 flex flex-col overflow-hidden">
                <!-- Empty selection -->
                <div v-if="!activeProject" class="flex-1 flex items-center justify-center p-8 text-center">
                    <div>
                        <IconVideoCamera class="w-12 h-12 mx-auto mb-3 text-gray-300" />
                        <p class="text-sm text-gray-500">Select a project from the sidebar, or create a new one.</p>
                    </div>
                </div>

                <div v-else class="flex-1 flex min-h-0">
                    <!-- Left controls -->
                    <div class="w-[400px] shrink-0 border-r dark:border-gray-800 bg-white dark:bg-gray-900 overflow-y-auto custom-scrollbar p-4 space-y-4">
                        <div>
                            <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Title</label>
                            <input v-model="edit.title" @change="saveProject" class="input-field w-full text-sm" />
                        </div>

                        <div>
                            <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Source Type</label>
                            <div class="grid grid-cols-3 gap-1">
                                <button v-for="mode in sourceModes" :key="mode.value"
                                    @click="changeSourceType(mode.value)"
                                    class="py-1.5 text-[10px] font-bold uppercase rounded-lg border transition-all"
                                    :class="edit.source_type === mode.value
                                        ? 'bg-blue-500 text-white border-blue-500'
                                        : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-700'"
                                >
                                    {{ mode.label }}
                                </button>
                            </div>
                        </div>

                        <div>
                            <div class="flex items-center justify-between mb-1">
                                <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400">Prompt</label>
                                <button @click="clearPrompt" class="text-[9px] font-bold text-gray-400 hover:text-red-500 px-1.5 py-0.5 rounded transition-colors uppercase">
                                    Clear
                                </button>
                            </div>
                            <textarea v-model="edit.prompt" @change="saveProject" rows="5" class="input-field w-full text-sm resize-none" placeholder="Describe the desired video action, camera movement, mood..."></textarea>
                        </div>

                        <!-- Prominent Generate button (mirrors Image Studio) -->
                        <button
                            @click="renderCurrent"
                            class="btn btn-primary w-full py-3 text-xs font-black uppercase tracking-widest shadow-xl shadow-blue-500/20 flex items-center justify-center gap-2"
                            :disabled="isRendering"
                        >
                            <IconAnimateSpin v-if="isRendering" class="w-4 h-4 animate-spin" />
                            <IconPlayCircle v-else class="w-4 h-4" />
                            <span>{{ isRendering ? 'Rendering…' : 'Generate Video' }}</span>
                        </button>

                        <div>
                            <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Negative Prompt</label>
                            <textarea v-model="edit.negative_prompt" @change="saveProject" rows="2" class="input-field w-full text-xs resize-none" placeholder="blurry, distorted, low quality..."></textarea>
                        </div>

                        <div class="grid grid-cols-2 gap-2">
                            <div>
                                <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Width</label>
                                <input v-model.number="edit.width" @change="saveProject" type="number" class="input-field w-full text-xs" />
                            </div>
                            <div>
                                <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Height</label>
                                <input v-model.number="edit.height" @change="saveProject" type="number" class="input-field w-full text-xs" />
                            </div>
                            <div>
                                <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Frames</label>
                                <input v-model.number="edit.num_frames" @change="saveProject" type="number" class="input-field w-full text-xs" />
                            </div>
                            <div>
                                <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">FPS</label>
                                <input v-model.number="edit.fps" @change="saveProject" type="number" class="input-field w-full text-xs" />
                            </div>
                            <div>
                                <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Steps</label>
                                <input v-model.number="edit.num_inference_steps" @change="saveProject" type="number" class="input-field w-full text-xs" placeholder="auto" />
                            </div>
                            <div>
                                <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Seed</label>
                                <input v-model.number="edit.seed" @change="saveProject" type="number" class="input-field w-full text-xs" placeholder="random" />
                            </div>
                        </div>

                        <div>
                            <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Guidance Scale</label>
                            <input v-model.number="edit.guidance_scale" @change="saveProject" type="number" step="0.1" class="input-field w-full text-xs" placeholder="model default" />
                        </div>

                        <!-- Reference images (i2v / flf) -->
                        <div v-if="edit.source_type !== 't2v'" class="pt-2 border-t dark:border-gray-800 space-y-2">
                            <div>
                                <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">First Frame</label>
                                <div class="flex items-center gap-2">
                                    <label class="btn btn-secondary btn-xs flex items-center gap-1 cursor-pointer">
                                        <IconArrowUpTray class="w-3 h-3" />
                                        <span>Upload</span>
                                        <input type="file" accept="image/*" @change="onUploadFirst" class="hidden" />
                                    </label>
                                    <button v-if="capabilities.tti_available" @click="openTtiModal('first')" class="btn btn-secondary btn-xs flex items-center gap-1">
                                        <IconSparkles class="w-3 h-3" />
                                        <span>Generate</span>
                                    </button>
                                </div>
                                <img v-if="activeProject?.first_image" :src="`/api/video-studio/projects/${activeProject.id}/first-image?t=${refreshTick}`" class="mt-2 w-full max-h-40 object-contain rounded-lg border dark:border-gray-700 bg-black/10" />
                            </div>

                            <div v-if="edit.source_type === 'flf'">
                                <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Last Frame</label>
                                <div class="flex items-center gap-2">
                                    <label class="btn btn-secondary btn-xs flex items-center gap-1 cursor-pointer">
                                        <IconArrowUpTray class="w-3 h-3" />
                                        <span>Upload</span>
                                        <input type="file" accept="image/*" @change="onUploadLast" class="hidden" />
                                    </label>
                                    <button v-if="capabilities.tti_available" @click="openTtiModal('last')" class="btn btn-secondary btn-xs flex items-center gap-1">
                                        <IconSparkles class="w-3 h-3" />
                                        <span>Generate</span>
                                    </button>
                                </div>
                                <img v-if="activeProject?.last_image" :src="`/api/video-studio/projects/${activeProject.id}/last-image?t=${refreshTick}`" class="mt-2 w-full max-h-40 object-contain rounded-lg border dark:border-gray-700 bg-black/10" />
                            </div>
                        </div>
                    </div>

                    <!-- Right viewport -->
                    <div class="grow min-w-0 flex flex-col bg-black/5 dark:bg-gray-950">
                        <div class="grow flex items-center justify-center p-4 overflow-hidden">
                            <!-- Render active -->
                            <div v-if="activeRenderTask && activeRenderTask.status !== 'completed' && activeRenderTask.status !== 'failed'" class="text-center text-gray-500">
                                <IconAnimateSpin class="w-10 h-10 mx-auto mb-3 animate-spin text-blue-500" />
                                <p class="text-xs font-bold uppercase tracking-widest">{{ activeRenderTask.progress }}% — {{ activeRenderTask.status }}</p>
                                <p class="text-[11px] text-gray-400 mt-1 max-w-sm mx-auto">{{ activeRenderTask.description }}</p>
                            </div>

                            <!-- Rendered video -->
                            <video v-else-if="videoBlobUrl && !videoError"
                                :key="videoKey"
                                ref="videoEl"
                                :src="videoBlobUrl"
                                controls
                                class="max-h-full max-w-full rounded-lg shadow-2xl"
                                @error="videoError = true"
                            ></video>

                            <!-- Empty state -->
                            <div v-else-if="!activeRenderTask" class="text-center text-gray-400">
                                <IconVideoCamera class="w-14 h-14 mx-auto mb-3 opacity-30" />
                                <p class="text-sm font-bold text-gray-500">No rendered video</p>
                                <p class="text-xs">Fill in your prompt, then click <strong>Render</strong>.</p>
                            </div>
                        </div>

                        <!-- Action bar -->
                        <div class="p-3 border-t dark:border-gray-800 bg-white dark:bg-gray-900 flex items-center justify-between gap-2">
                            <div class="text-[11px] text-gray-500">
                                <span v-if="activeRenderTask" class="font-bold uppercase tracking-widest text-[10px]">{{ activeRenderTask.status }} • {{ activeRenderTask.progress }}%</span>
                                <span v-else-if="activeProject?.updated_at">Updated {{ new Date(activeProject.updated_at).toLocaleString() }}</span>
                            </div>
                            <div class="flex items-center gap-2">
                                <button v-if="activeProject?.video_filename" @click="downloadCurrent" class="btn btn-secondary text-xs flex items-center gap-1">
                                    <IconDownload class="w-3.5 h-3.5" />
                                    <span>Download</span>
                                </button>
                                <button @click="renderCurrent" class="btn btn-primary text-xs font-black uppercase tracking-widest flex items-center gap-2"
                                    :disabled="!!activeRenderTask && activeRenderTask.status !== 'completed' && activeRenderTask.status !== 'failed'">
                                    <IconAnimateSpin v-if="isRendering" class="w-3.5 h-3.5 animate-spin" />
                                    <IconPlayCircle v-else class="w-3.5 h-3.5" />
                                    <span>Render</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    </div>

    <!-- Simple TTI modal for generating reference frames -->
    <div v-if="ttiModal.open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" @click.self="ttiModal.open = false">
        <div class="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md">
            <div class="p-4 border-b dark:border-gray-800 flex items-center justify-between">
                <h3 class="text-sm font-black uppercase tracking-widest text-gray-700 dark:text-gray-200">
                    Generate {{ ttiModal.slot === 'first' ? 'First' : 'Last' }} Frame
                </h3>
                <button @click="ttiModal.open = false" class="p-1 text-gray-400 hover:text-red-500"><IconXMark class="w-4 h-4" /></button>
            </div>
            <div class="p-4 space-y-3">
                <div>
                    <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Prompt</label>
                    <textarea v-model="ttiModal.prompt" rows="3" class="input-field w-full text-xs"></textarea>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Width</label>
                        <input v-model.number="ttiModal.width" type="number" class="input-field w-full text-xs" />
                    </div>
                    <div>
                        <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Height</label>
                        <input v-model.number="ttiModal.height" type="number" class="input-field w-full text-xs" />
                    </div>
                </div>
                <div class="flex justify-end gap-2 pt-2">
                    <button @click="ttiModal.open = false" class="btn btn-secondary text-xs">Cancel</button>
                    <button @click="generateTtiImage" :disabled="ttiModal.busy" class="btn btn-primary text-xs flex items-center gap-1">
                        <IconAnimateSpin v-if="ttiModal.busy" class="w-3.5 h-3.5 animate-spin" />
                        <span>{{ ttiModal.busy ? 'Generating...' : 'Generate' }}</span>
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { useVideoStore } from '../stores/video';
import { useTasksStore } from '../stores/tasks';
import { useUiStore } from '../stores/ui';
import { storeToRefs } from 'pinia';
import apiClient from '../services/api';

import IconVideoCamera from '../assets/icons/IconVideoCamera.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconCheckCircle from '../assets/icons/IconCheckCircle.vue';
import IconClock from '../assets/icons/IconClock.vue';
import IconArrowUpTray from '../assets/icons/IconArrowUpTray.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconPlayCircle from '../assets/icons/IconPlayCircle.vue';
import IconDownload from '../assets/icons/IconDownload.vue';
import IconXMark from '../assets/icons/IconXMark.vue';

const store = useVideoStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();

const { projects, isLoading, capabilities, activeProjectId, activeProject } = storeToRefs(store);
const { tasks } = storeToRefs(tasksStore);

const hasHeaderTarget = ref(false);
const refreshTick = ref(Date.now());
const videoKey = ref(Date.now());
const videoError = ref(false);
const videoBlobUrl = ref(null);
const videoEl = ref(null);
const activeRenderTaskId = ref(null);

const edit = reactive({
    title: '',
    prompt: '',
    negative_prompt: '',
    source_type: 't2v',
    width: 512,
    height: 512,
    num_frames: 48,
    fps: 12,
    num_inference_steps: null,
    guidance_scale: null,
    seed: null,
});

const sourceModes = [
    { value: 't2v', label: 'T2V' },
    { value: 'i2v', label: 'Image+Text' },
    { value: 'flf', label: 'First+Last' },
];

const ttiModal = reactive({
    open: false,
    slot: 'first',
    busy: false,
    prompt: '',
    width: 512,
    height: 512,
});

const activeRenderTask = computed(() => {
    if (!activeRenderTaskId.value) return null;
    return tasks.value.find(t => t.id === activeRenderTaskId.value) || null;
});

const isRendering = computed(() =>
    !!activeRenderTask.value
    && activeRenderTask.value.status !== 'completed'
    && activeRenderTask.value.status !== 'failed'
);

// Fetch the rendered video as a blob so the Authorization header is included.
async function loadVideoBlob() {
    // Release any previous blob URL
    if (videoBlobUrl.value) {
        try { URL.revokeObjectURL(videoBlobUrl.value); } catch (_) {}
        videoBlobUrl.value = null;
    }
    videoError.value = false;

    if (!activeProject.value?.video_filename) return;
    try {
        const res = await apiClient.get(
            `/api/video-studio/projects/${activeProject.value.id}/video`,
            { responseType: 'blob' }
        );
        videoBlobUrl.value = URL.createObjectURL(res.data);
        videoKey.value = Date.now();
    } catch (e) {
        console.warn('Failed to load rendered video blob:', e);
        videoError.value = true;
    }
}

// Sync active project into editable model
watch(activeProject, async (p) => {
    if (!p) return;
    edit.title = p.title || '';
    edit.prompt = p.prompt || '';
    edit.negative_prompt = p.negative_prompt || '';
    edit.source_type = p.source_type || 't2v';
    edit.width = p.width ?? 512;
    edit.height = p.height ?? 512;
    edit.num_frames = p.num_frames ?? 48;
    edit.fps = p.fps ?? 12;
    edit.num_inference_steps = p.num_inference_steps ?? null;
    edit.guidance_scale = p.guidance_scale ?? null;
    edit.seed = p.seed ?? null;
    await loadVideoBlob();
}, { immediate: true });

// When a render completes, refresh the video element and re-fetch projects.
watch(tasks, async () => {
    if (!activeRenderTask.value) return;
    if (activeRenderTask.value.status === 'completed') {
        refreshTick.value = Date.now();
        await store.fetchProjects();
        videoError.value = false;
        await loadVideoBlob();
    }
}, { deep: true });

async function newProject() {
    if (isRendering.value) {
        uiStore.addNotification(
            'A render is in progress. Wait for it to finish before creating a new project.',
            'warning'
        );
        return;
    }
    try {
        await store.createProject({
            title: 'Untitled Video',
            prompt: '',
            source_type: 't2v',
            width: 512,
            height: 512,
            num_frames: 48,
            fps: 12,
        });
    } catch (e) {
        console.error('Failed to create video project:', e);
        uiStore.addNotification(
            e?.response?.data?.detail || 'Failed to create video project.',
            'error'
        );
    }
}

async function deleteProject(p) {
    const { confirmed } = await uiStore.showConfirmation({
        title: `Delete "${p.title}"?`,
        message: 'This will permanently remove the project and any rendered video.',
        confirmText: 'Delete',
        danger: true,
    });
    if (confirmed) await store.deleteProject(p.id);
}

function clearPrompt() {
    edit.prompt = '';
    saveProject();
}

async function saveProject() {
    if (!activeProject.value) return;
    await store.updateProject(activeProject.value.id, {
        title: edit.title,
        prompt: edit.prompt,
        negative_prompt: edit.negative_prompt,
        source_type: edit.source_type,
        width: edit.width,
        height: edit.height,
        num_frames: edit.num_frames,
        fps: edit.fps,
        num_inference_steps: edit.num_inference_steps,
        guidance_scale: edit.guidance_scale,
        seed: edit.seed,
    });
}

async function changeSourceType(mode) {
    edit.source_type = mode;
    await saveProject();
}

async function onUploadFirst(event) {
    const file = event.target.files?.[0];
    if (!file || !activeProject.value) return;
    await store.uploadFirstImage(activeProject.value.id, file);
    activeProject.value.first_image = true;
    refreshTick.value = Date.now();
    await store.fetchProjects();
    event.target.value = '';
}

async function onUploadLast(event) {
    const file = event.target.files?.[0];
    if (!file || !activeProject.value) return;
    await store.uploadLastImage(activeProject.value.id, file);
    activeProject.value.last_image = true;
    refreshTick.value = Date.now();
    await store.fetchProjects();
    event.target.value = '';
}

async function renderCurrent() {
    if (!activeProject.value) return;
    await saveProject();
    try {
        const task = await store.renderProject(activeProject.value.id);
        activeRenderTaskId.value = task.id;
        videoError.value = false;
    } catch (e) {
        uiStore.addNotification('Failed to start render.', 'error');
    }
}

function downloadCurrent() {
    store.downloadVideo(activeProject.value);
}

async function refresh() {
    await Promise.all([store.fetchProjects(), store.fetchCapabilities()]);
    refreshTick.value = Date.now();
}

function openTtiModal(slot) {
    ttiModal.slot = slot;
    ttiModal.prompt = edit.prompt || '';
    ttiModal.width = edit.width || 512;
    ttiModal.height = edit.height || 512;
    ttiModal.open = true;
}

// Called by the sidebar's plus button via the `lollms:new-video-project` event.
// We always create the project — the "TTV not configured" banner inside the
// studio is the single authoritative gate, matching how Image Studio lets
// users create albums before any TTI model is validated.
async function onNewProjectEvent() {
    await newProject();
}

async function generateTtiImage() {
    if (!ttiModal.prompt.trim()) return;
    ttiModal.busy = true;
    try {
        const b64 = await store.generateReferenceImage({
            prompt: ttiModal.prompt,
            width: ttiModal.width,
            height: ttiModal.height,
        });
        // Convert base64 to blob, then upload via the studio upload endpoint
        const bin = atob(b64);
        const arr = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
        const blob = new Blob([arr], { type: 'image/png' });
        const file = new File([blob], `${ttiModal.slot}.png`, { type: 'image/png' });

        if (ttiModal.slot === 'first') {
            await store.uploadFirstImage(activeProject.value.id, file);
            activeProject.value.first_image = true;
        } else {
            await store.uploadLastImage(activeProject.value.id, file);
            activeProject.value.last_image = true;
        }
        refreshTick.value = Date.now();
        await store.fetchProjects();
        ttiModal.open = false;
    } catch (e) {
        uiStore.addNotification('Failed to generate reference image.', 'error');
    } finally {
        ttiModal.busy = false;
    }
}

onMounted(async () => {
    nextTick(() => {
        hasHeaderTarget.value = !!document.getElementById('global-header-title-target')
            && !!document.getElementById('global-header-actions-target');
    });
    window.addEventListener('lollms:new-video-project', onNewProjectEvent);
    await Promise.all([store.fetchProjects(), store.fetchCapabilities()]);
    if (!activeProjectId.value && projects.value.length) {
        activeProjectId.value = projects.value[0].id;
    }
});

onUnmounted(() => {
    window.removeEventListener('lollms:new-video-project', onNewProjectEvent);
    videoEl.value = null;
    if (videoBlobUrl.value) {
        try { URL.revokeObjectURL(videoBlobUrl.value); } catch (_) {}
        videoBlobUrl.value = null;
    }
});
</script>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>