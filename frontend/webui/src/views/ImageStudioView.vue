<!-- [UPDATE] frontend/webui/src/views/ImageStudioView.vue -->
<template>
    <Teleport to="#global-header-actions-target">
        <div class="flex items-center gap-2">
            <button @click="handleGenerateOrApply" class="btn btn-primary whitespace-nowrap" :disabled="isGenerating || isAnyEnhancing">
                <IconAnimateSpin v-if="isGenerating" class="w-5 h-5 mr-1 sm:mr-2 animate-spin" />
                <span class="hidden xs:inline">{{ isSelectionMode ? 'Apply Edit' : 'Generate' }}</span>
                <IconSparkles v-if="!isGenerating" class="w-5 h-5 xs:hidden" />
            </button>
            <button @click="showMobileSidebar = !showMobileSidebar" class="lg:hidden btn btn-secondary p-2" title="Toggle Settings">
                <IconAdjustmentsHorizontal class="w-6 h-6" />
            </button>
        </div>
    </Teleport>
    
    <div 
        class="h-full flex flex-col bg-gray-50 dark:bg-gray-900 overflow-hidden relative" 
        @dragover.prevent="handleDragOver"
        @dragleave.prevent="handleDragLeave"
        @drop.prevent="handleDrop"
    >
        <div v-if="isDraggingOver" class="absolute inset-0 bg-blue-500/20 border-4 border-dashed border-blue-500 rounded-lg z-50 flex items-center justify-center m-4 pointer-events-none">
            <p class="text-xl sm:text-2xl font-bold text-blue-600 text-center">Drop images to upload</p>
        </div>
        
        <div class="flex-grow min-h-0 flex relative overflow-hidden">
            <aside 
                class="absolute inset-y-0 left-0 z-30 bg-white dark:bg-gray-800 border-r dark:border-gray-700 transform transition-transform duration-300 ease-in-out lg:relative lg:translate-x-0 flex flex-col flex-shrink-0 shadow-lg"
                :class="showMobileSidebar ? 'translate-x-0' : '-translate-x-full'"
                :style="sidebarStyle"
            >
                <div 
                    @mousedown.prevent="startResizing"
                    class="hidden lg:block absolute top-0 right-0 bottom-0 w-1.5 cursor-col-resize z-50 hover:bg-blue-500/50 transition-colors"
                ></div>

                <div class="flex-grow p-4 space-y-6 overflow-y-auto custom-scrollbar">
                    <div class="flex items-center justify-between lg:hidden mb-4 border-b dark:border-gray-700 pb-2">
                        <span class="font-black uppercase tracking-widest text-xs text-gray-500">Studio Tools</span>
                        <button @click="showMobileSidebar = false" class="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
                            <IconXMark class="w-6 h-6" />
                        </button>
                    </div>

                    <!-- Prompting Area -->
                    <div class="space-y-4">
                        <div>
                            <div class="flex justify-between items-center mb-1">
                                <label for="prompt" class="text-[10px] font-black uppercase text-gray-400">Positive Prompt</label>
                                <button @click="openEnhanceModal('prompt')" class="text-blue-500 hover:text-blue-600 p-1 rounded" :disabled="isAnyEnhancing">
                                    <IconSparkles class="w-4 h-4" />
                                </button>
                            </div>
                            <div class="relative">
                                <textarea id="prompt" v-model="prompt" rows="4" class="input-field w-full resize-none !text-sm" :disabled="isEnhancingPrompt" placeholder="What do you want to see?"></textarea>
                                <div v-if="isEnhancingPrompt" class="absolute inset-0 flex items-center justify-center bg-white/40 dark:bg-black/40 backdrop-blur-sm rounded"><IconAnimateSpin class="w-6 h-6 text-blue-500 animate-spin" /></div>
                            </div>
                        </div>

                        <!-- STYLE LIBRARY (Categorized) -->
                        <div v-for="(group, category) in styleLibrary" :key="category" class="space-y-2 border-t dark:border-gray-700 pt-3">
                            <div class="flex items-center justify-between cursor-pointer group" @click="collapsedStyles[category] = !collapsedStyles[category]">
                                <span class="text-[10px] font-black text-gray-400 uppercase tracking-widest">{{ category }}</span>
                                <IconChevronUp class="w-3 h-3 text-gray-400 transition-transform" :class="{'rotate-180': collapsedStyles[category]}" />
                            </div>
                            
                            <div v-show="!collapsedStyles[category]" class="grid grid-cols-3 gap-1.5 animate-in fade-in slide-in-from-top-1">
                                <button v-for="style in group" :key="style.name" 
                                    @click="applyStyle(style)"
                                    class="flex flex-col items-center p-1.5 rounded-lg border dark:border-gray-700 transition-all hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20"
                                    :class="selectedStyle === style.name ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 ring-1 ring-blue-500' : 'bg-gray-50 dark:bg-gray-900/30'"
                                    :title="style.name"
                                >
                                    <span class="text-lg mb-0.5">{{ style.emoji }}</span>
                                    <span class="text-[8px] font-bold truncate w-full text-center leading-tight uppercase">{{ style.name }}</span>
                                </button>
                            </div>
                        </div>

                        <div>
                            <div class="flex justify-between items-center mb-1">
                                <label for="negative-prompt" class="text-[10px] font-black uppercase text-gray-400">Negative Prompt</label>
                                <button @click="openEnhanceModal('negative_prompt')" class="text-red-500 hover:text-red-600 p-1" :disabled="isAnyEnhancing">
                                    <IconSparkles class="w-4 h-4" />
                                </button>
                            </div>
                            <textarea id="negative-prompt" v-model="negativePrompt" rows="2" class="input-field w-full resize-none !text-xs opacity-80" placeholder="Avoid..."></textarea>
                        </div>
                    </div>

                    <!-- Layout & Seed -->
                    <div class="pt-4 border-t dark:border-gray-700 space-y-4">
                        <div class="space-y-2">
                            <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest">Aspect Ratio</label>
                            <div class="grid grid-cols-3 sm:flex sm:flex-wrap gap-2">
                                <button v-for="ratio in aspectRatios" :key="ratio.name"
                                    @click="imageSize = ratio.value"
                                    class="p-2 rounded-xl border dark:border-gray-700 flex flex-col items-center transition-all hover:bg-gray-100 dark:hover:bg-gray-700 flex-1 min-w-[60px]"
                                    :class="imageSize === ratio.value ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400' : 'bg-gray-50 dark:bg-gray-900/30 text-gray-500'"
                                >
                                    <div class="border-2 border-current rounded mb-1" :style="ratio.style"></div>
                                    <span class="text-[10px] font-black uppercase">{{ ratio.name }}</span>
                                </button>
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="label text-[10px] font-bold text-gray-400 uppercase">Count</label>
                                <input type="number" v-model.number="nImages" min="1" max="10" class="input-field mt-1 !text-xs">
                            </div>
                            <div>
                                <label class="label text-[10px] font-bold text-gray-400 uppercase">Seed</label>
                                <input v-model.number="seed" type="number" class="input-field mt-1 !text-xs font-mono" placeholder="-1">
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="p-4 border-t dark:border-gray-700 flex-shrink-0 bg-gray-50 dark:bg-gray-800/50">
                    <router-link to="/" class="flex items-center justify-center gap-3 px-4 py-3 text-xs font-black uppercase tracking-widest text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-xl transition-all">
                        <IconArrowLeft class="w-4 h-4" /> <span>Back to Chat</span>
                    </router-link>
                </div>
            </aside>

            <div v-if="showMobileSidebar" @click="showMobileSidebar = false" class="absolute inset-0 bg-black/40 z-20 lg:hidden backdrop-blur-sm"></div>

            <main class="flex-grow flex flex-col min-w-0 h-full relative">
                <div class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-2 sm:p-3 flex items-center justify-between flex-shrink-0 z-10 shadow-sm overflow-x-auto no-scrollbar">
                    <div class="flex items-center gap-3 sm:gap-4 whitespace-nowrap">
                        <div class="flex items-center gap-2">
                            <input type="checkbox" v-model="areAllSelected" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer" />
                            <h2 class="font-bold text-gray-800 dark:text-gray-200 text-xs uppercase tracking-widest">Library ({{ images.length }})</h2>
                        </div>
                        <div class="h-6 w-px bg-gray-300 dark:bg-gray-600"></div>
                        <div class="flex items-center gap-1">
                            <button @click="handleRefresh" class="btn-icon text-gray-400 hover:text-blue-600 p-1.5" title="Refresh"><IconRefresh class="w-5 h-5" /></button>
                            <label class="btn-icon text-gray-400 hover:text-blue-600 cursor-pointer p-1.5" title="Upload"><IconArrowDownTray class="w-5 h-5" /><input type="file" @change="handleUpload" class="hidden" accept="image/*" multiple></label>
                            <button @click="openCameraModal" class="btn-icon text-gray-400 hover:text-blue-600 p-1.5" title="Camera"><IconCamera class="w-5 h-5" /></button>
                            <button @click="handleNewBlankImage" class="btn-icon text-gray-400 hover:text-blue-600 p-1.5" title="New Canvas"><IconPlus class="w-5 h-5" /></button>
                        </div>
                    </div>

                    <div v-if="isSelectionMode" class="flex items-center gap-2 bg-blue-50 dark:bg-blue-900/30 px-2 py-1 rounded-xl border border-blue-100 dark:border-blue-800 transition-all ml-4 shadow-sm">
                        <span class="text-[10px] font-black text-blue-800 dark:text-blue-200 uppercase">{{ selectedImages.length }} selected</span>
                        <button @click="handleMoveToDiscussion" class="text-blue-600 dark:text-blue-400 p-1" title="Send to Chat"><IconSend class="w-5 h-5" /></button>
                        <button @click="handleDeleteSelected" class="text-red-500 p-1" title="Delete"><IconTrash class="w-5 h-5" /></button>
                    </div>
                </div>

                <div class="flex-grow overflow-y-auto p-4 custom-scrollbar bg-gray-50 dark:bg-gray-900">
                    <div v-if="imageGenerationTasksCount > 0" class="mb-8 grid grid-cols-1 xs:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4 animate-in fade-in zoom-in-95">
                         <div v-for="task in imageGenerationTasks" :key="task.id" class="relative aspect-square rounded-[2rem] bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm flex flex-col items-center justify-center p-6 overflow-hidden">
                            <div class="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-purple-500/5 animate-pulse"></div>
                            <IconAnimateSpin class="w-8 h-8 text-blue-500 mb-4 animate-spin" />
                            <p class="text-[10px] font-black text-blue-600 uppercase">{{ task.progress }}% Complete</p>
                            <div class="absolute bottom-0 left-0 right-0 h-1.5 bg-gray-100 dark:bg-gray-700"><div class="h-full bg-gradient-to-r from-blue-500 to-indigo-600" :style="{ width: task.progress + '%' }"></div></div>
                        </div>
                    </div>

                    <div v-if="isLoading && images.length === 0" class="h-64 flex flex-col items-center justify-center opacity-40"><IconAnimateSpin class="w-12 h-12 mb-4 text-blue-500 animate-spin" /><p class="text-xs font-black uppercase tracking-widest">Gathering images...</p></div>
                    
                    <div v-else-if="images.length === 0 && imageGenerationTasksCount === 0" class="h-full flex flex-col items-center justify-center text-gray-400 opacity-40"><IconPhoto class="w-20 h-20 mb-6" /><p class="text-xl font-black uppercase tracking-widest">No Creations Yet</p></div>

                    <div v-else class="grid grid-cols-1 xs:grid-cols-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-6 pb-20">
                        <div v-for="(image, index) in images" :key="image.id" @click="toggleSelection(image.id)" class="relative aspect-square rounded-[1.5rem] overflow-hidden group cursor-pointer border-2 transition-all duration-300 bg-gray-200 dark:bg-gray-800" :class="isSelected(image.id) ? 'border-blue-500 ring-4 ring-blue-500/10 scale-[0.98]' : 'border-transparent hover:border-gray-300 dark:hover:border-gray-700 hover:shadow-xl'">
                            <AuthenticatedImage :src="`/api/image-studio/${image.id}/file`" class="w-full h-full object-cover transition-transform duration-700 sm:group-hover:scale-110" />
                            <div class="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent flex flex-col justify-end p-3 transition-opacity duration-300 lg:opacity-0 lg:group-hover:opacity-100" :class="{'!opacity-100': isSelected(image.id)}">
                                <p class="text-white text-[10px] font-medium line-clamp-2 drop-shadow-lg mb-2 opacity-90">{{ image.prompt || 'No prompt' }}</p>
                                <div class="flex items-center justify-between pt-2 border-t border-white/20">
                                    <span class="text-[9px] text-gray-400 font-black uppercase tracking-tighter">{{ image.width }}x{{ image.height }}</span>
                                    <div class="flex gap-1.5">
                                        <button @click.stop="reusePrompt(image)" class="p-2 bg-white/10 hover:bg-blue-500 rounded-lg text-white backdrop-blur-md transition-all active:scale-90"><IconRefresh class="w-4 h-4" /></button>
                                        <button @click.stop="openInpaintingEditor(image)" class="p-2 bg-white/10 hover:bg-purple-500 rounded-lg text-white backdrop-blur-md transition-all active:scale-90"><IconPencil class="w-4 h-4" /></button>
                                        <button @click.stop="openImageViewer(image, index)" class="p-2 bg-white/10 hover:bg-white/30 rounded-lg text-white backdrop-blur-md transition-all active:scale-90"><IconMaximize class="w-4 h-4" /></button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch, markRaw } from 'vue';
import { useRouter } from 'vue-router';
import { useImageStore } from '../stores/images';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import { useDiscussionsStore } from '../stores/discussions';
import { useTasksStore } from '../stores/tasks';
import { storeToRefs } from 'pinia';
import AuthenticatedImage from '../components/ui/AuthenticatedImage.vue';
import apiClient from '../services/api';

import IconPhoto from '../assets/icons/IconPhoto.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconSend from '../assets/icons/IconSend.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconMaximize from '../assets/icons/IconMaximize.vue';
import IconArrowLeft from '../assets/icons/IconArrowLeft.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue'; 
import IconChevronUp from '../assets/icons/IconChevronUp.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconCamera from '../assets/icons/IconCamera.vue';
import IconXMark from '../assets/icons/IconXMark.vue';
import IconAdjustmentsHorizontal from '../assets/icons/IconAdjustmentsHorizontal.vue';

const imageStore = useImageStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const tasksStore = useTasksStore();
const router = useRouter();

const { images, isLoading, isGenerating, prompt, negativePrompt, imageSize, nImages, seed, generationParams } = storeToRefs(imageStore);
const { user } = storeToRefs(authStore);
const { imageGenerationTasks, imageGenerationTasksCount } = storeToRefs(tasksStore);
const { currentModelVisionSupport } = storeToRefs(discussionsStore);

const isConfigVisible = ref(true);
const selectedStyle = ref('None');
const showMobileSidebar = ref(false);
const sidebarWidth = ref(384); 
const isResizing = ref(false);
const collapsedStyles = ref({ 'Art Style': false, 'Artist Style': true, 'Enhancements': true, 'Technical': true });

const sidebarStyle = computed(() => ({
    width: window.innerWidth >= 1024 ? `${sidebarWidth.value}px` : undefined,
    minWidth: window.innerWidth >= 1024 ? '320px' : undefined
}));

function startResizing(event) {
    isResizing.value = true;
    const startX = event.clientX, startWidth = sidebarWidth.value;
    const handleMouseMove = (e) => { if (!isResizing.value) return; sidebarWidth.value = Math.max(320, Math.min(startWidth + (e.clientX - startX), 700)); };
    const handleMouseUp = () => { isResizing.value = false; localStorage.setItem('lollms_image_studio_sidebar_width', sidebarWidth.value); window.removeEventListener('mousemove', handleMouseMove); window.removeEventListener('mouseup', handleMouseUp); };
    window.addEventListener('mousemove', handleMouseMove); window.addEventListener('mouseup', handleMouseUp);
}

const styleLibrary = {
    'Art Style': [
        { name: 'Photo', emoji: '📸', prompt: 'photorealistic, RAW photo, 8k uhd, high detailed', negative: 'cartoon, anime, illustration, blurred' },
        { name: 'Cinematic', emoji: '🎬', prompt: 'cinematic lighting, dramatic, epic scale, highly detailed', negative: 'grainy, simple, low res' },
        { name: 'Anime', emoji: '🎌', prompt: 'anime style, vibrant colors, cell shaded, high quality 2d', negative: '3d, realistic, blurry' },
        { name: 'Digital Art', emoji: '🎨', prompt: 'digital art, sharp focus, intricate detail, artstation style', negative: 'hand drawn, blurry' },
        { name: 'Oil Paint', emoji: '🖼️', prompt: 'oil painting, thick brushstrokes, textured canvas, classical art', negative: 'photography, smooth, plastic' },
        { name: 'Watercolor', emoji: '🖌️', prompt: 'watercolor painting, soft edges, paper texture, elegant', negative: 'dark, heavy, photography' },
        { name: 'Cyberpunk', emoji: '🌃', prompt: 'cyberpunk aesthetic, neon lights, futuristic city, rainy night', negative: 'nature, pastoral' },
        { name: 'Comic', emoji: '🗯️', prompt: 'comic book style, bold lines, halftone dots, vibrant', negative: 'photorealistic' },
    ],
    'Artist Style': [
        { name: 'Van Gogh', emoji: '🌻', prompt: 'in the style of Vincent Van Gogh, post-impressionism, swirling colors', negative: '' },
        { name: 'Dali', emoji: '⏳', prompt: 'in the style of Salvador Dali, surrealism, melting objects, dreamlike', negative: '' },
        { name: 'Ghibli', emoji: '🌳', prompt: 'Studio Ghibli style, Hayao Miyazaki, lush environments, whimsical', negative: '' },
        { name: 'Picasso', emoji: '🧊', prompt: 'cubism style, Pablo Picasso, abstract geometry, fragmented', negative: '' },
        { name: 'Shinkai', emoji: '✨', prompt: 'Makoto Shinkai style, breathtaking sky, detailed light, emotional', negative: '' },
    ],
    'Enhancements': [
        { name: 'Hyperreal', emoji: '💎', prompt: 'hyperrealistic, insanely detailed, micro texture, masterpiece', negative: 'ugly, deformed' },
        { name: 'HDR', emoji: '🌈', prompt: 'high dynamic range, rich colors, deep contrast', negative: 'flat, dull' },
        { name: 'Retro 8-bit', emoji: '🕹️', prompt: '8-bit style, pixel art, low resolution game aesthetic', negative: 'high definition, smooth' },
        { name: 'Macro', emoji: '🔍', prompt: 'macro photography, shallow depth of field, extreme close-up', negative: 'wide angle' },
    ],
    'Thematic': [
        { name: 'Horror', emoji: '🎃', prompt: 'horror aesthetic, dark, eerie, macabre, halloween theme', negative: 'bright, cheerful' },
        { name: 'Minecraft', emoji: '🧱', prompt: 'minecraft style, blocky, voxel art, cubic shapes', negative: 'curved lines' },
        { name: 'Steampunk', emoji: '⚙️', prompt: 'steampunk aesthetic, copper, brass, Victorian industrial', negative: 'modern' },
    ]
};

const stylePresets = styleLibrary['Art Style']; // Fallback for applyStyle logic compatibility

const aspectRatios = [
    { name: '1:1', value: '1024x1024', style: { width: '16px', height: '16px' } },
    { name: '16:9', value: '1344x768', style: { width: '22px', height: '12px' } },
    { name: '9:16', value: '768x1344', style: { width: '12px', height: '22px' } },
    { name: '4:3', value: '1152x896', style: { width: '20px', height: '15px' } },
    { name: '3:2', value: '1216x832', style: { width: '21px', height: '14px' } }
];

const isEnhancingPrompt = ref(false), isEnhancingNegative = ref(false);
const isAnyEnhancing = computed(() => isEnhancingPrompt.value || isEnhancingNegative.value);
const selectedImages = ref([]);
const isSelectionMode = computed(() => selectedImages.value.length > 0);
const areAllSelected = computed({ get: () => images.value.length > 0 && selectedImages.value.length === images.value.length, set: (v) => { selectedImages.value = v ? images.value.map(i => i.id) : []; } });
const isDraggingOver = ref(false);
const selectedModel = computed(() => user.value?.tti_binding_model_name);

const modelConfigurableParameters = computed(() => {
    const details = dataStore.availableTtiModels.find(m => m.id === selectedModel.value);
    if (!details?.binding_params) return [];
    const params = isSelectionMode.value ? (details.binding_params.edit_parameters || []) : (details.binding_params.generation_parameters || []);
    return params.filter(p => !['prompt', 'negative_prompt', 'image', 'mask', 'width', 'height', 'n', 'seed', 'size'].includes(p.name));
});

function applyStyle(style) {
    if (selectedStyle.value === style.name) selectedStyle.value = 'None';
    else {
        selectedStyle.value = style.name;
        if (style.name !== 'None') {
            prompt.value = prompt.value.trim() ? `${prompt.value}, ${style.prompt}` : style.prompt;
            if (style.negative) negativePrompt.value = negativePrompt.value.trim() ? `${negativePrompt.value}, ${style.negative}` : style.negative;
        }
    }
}

watch(imageGenerationTasksCount, (n, o) => { if (o > 0 && n === 0) setTimeout(() => imageStore.fetchImages(), 1000); });

onMounted(() => {
    const savedWidth = localStorage.getItem('lollms_image_studio_sidebar_width');
    if (savedWidth) sidebarWidth.value = parseInt(savedWidth, 10);
    uiStore.setPageTitle({ title: 'Image Studio', icon: markRaw(IconPhoto) });
    imageStore.fetchImages();
    if (dataStore.availableTtiModels.length === 0) dataStore.fetchAvailableTtiModels();
    window.addEventListener('paste', handlePaste);
});

onUnmounted(() => { uiStore.setPageTitle({ title: '' }); window.removeEventListener('paste', handlePaste); });

function toggleSelection(id) { const i = selectedImages.value.indexOf(id); if (i > -1) selectedImages.value.splice(i, 1); else selectedImages.value.push(id); }
function isSelected(id) { return selectedImages.value.includes(id); }

async function handleGenerateOrApply() {
    if (!prompt.value.trim() || !selectedModel.value) return;
    showMobileSidebar.value = false;
    const payload = { prompt: prompt.value, negative_prompt: negativePrompt.value, model: selectedModel.value, seed: seed.value, ...generationParams.value };
    if (isSelectionMode.value) {
        const [w, h] = imageSize.value.split('x').map(Number);
        await imageStore.editImage({ ...payload, image_ids: selectedImages.value, width: w, height: h });
    } else {
        await imageStore.generateImage({ ...payload, size: imageSize.value, n: nImages.value });
    }
}

async function handleEnhance(type, options = {}) {
    if (type !== 'negative_prompt' && !prompt.value.trim()) return;
    if (type === 'prompt' || type === 'both') isEnhancingPrompt.value = true;
    if (type === 'negative_prompt' || type === 'both') isEnhancingNegative.value = true;
    const payload = { prompt: prompt.value, negative_prompt: negativePrompt.value, target: type, model: authStore.user?.lollms_model_name, instructions: options.instructions || '', mode: options.mode || 'description' };
    try {
        const task = await imageStore.enhanceImagePrompt(payload);
        if (task?.id) monitorEnhancementTask(task.id, type);
        else resetEnhancingFlags(type);
    } catch (e) { resetEnhancingFlags(type); }
}

function monitorEnhancementTask(id, type) {
    const unwatch = watch(() => tasksStore.tasks.find(t => t.id === id), (t) => {
        if (!t) return;
        if (t.status === 'completed') {
            let res = typeof t.result === 'string' ? JSON.parse(t.result) : t.result;
            if (res) { if (res.prompt) imageStore.prompt = res.prompt; if (res.negative_prompt) imageStore.negativePrompt = res.negative_prompt; }
            resetEnhancingFlags(type); unwatch();
        } else if (['failed', 'cancelled'].includes(t.status)) { resetEnhancingFlags(type); unwatch(); }
    }, { deep: true, immediate: true });
}

function resetEnhancingFlags(type) { if (type === 'prompt' || type === 'both') isEnhancingPrompt.value = false; if (type === 'negative_prompt' || type === 'both') isEnhancingNegative.value = false; }
function openEnhanceModal(target) { uiStore.openModal('enhancePrompt', { onConfirm: (opts) => handleEnhance(target, opts) }); }
function handleNewBlankImage() { router.push('/image-studio/edit/new'); }
function reusePrompt(img) { prompt.value = img.prompt; negativePrompt.value = img.negative_prompt; seed.value = img.seed; }
function openInpaintingEditor(img) { router.push(`/image-studio/edit/${img.id}`); }
function openImageViewer(img, idx) { uiStore.openImageViewer({ imageList: images.value.map(i => ({ ...i, src: `/api/image-studio/${i.id}/file` })), startIndex: idx }); }
async function handleUpload(e) { if (e.target.files.length) await imageStore.uploadImages(Array.from(e.target.files)); }
async function handleDeleteSelected() { if (await uiStore.showConfirmation({ title: 'Delete Images?' })) { await Promise.all(selectedImages.value.map(id => imageStore.deleteImage(id))); selectedImages.value = []; } }
async function handleMoveToDiscussion() {
    const { confirmed, value: id } = await uiStore.showConfirmation({ title: 'Move to Discussion', inputType: 'select', inputOptions: discussionsStore.sortedDiscussions.map(d => ({ text: d.title, value: d.id })) });
    if (confirmed && id) { await Promise.all(selectedImages.value.map(imgId => imageStore.moveImageToDiscussion(imgId, id))); selectedImages.value = []; }
}
function handleDragOver(e) { e.preventDefault(); isDraggingOver.value = true; }
function handleDragLeave(e) { if (!e.currentTarget.contains(e.relatedTarget)) isDraggingOver.value = false; }
async function handleDrop(e) { e.preventDefault(); isDraggingOver.value = false; const f = Array.from(e.dataTransfer.files).filter(i => i.type.startsWith('image/')); if (f.length) await imageStore.uploadImages(f); }
async function handlePaste(e) { const items = (e.clipboardData || window.clipboardData).items; const files = []; for (const i of items) { if (i.kind === 'file' && i.type.startsWith('image/')) { const f = i.getAsFile(); if (f) files.push(new File([f], `pasted_${Date.now()}.png`, { type: f.type })); } } if (files.length) { e.preventDefault(); await imageStore.uploadImages(files); } }
function openCameraModal() { uiStore.openModal('cameraCapture'); }
function handleRefresh() { imageStore.fetchImages(); }
function parseOptions(o) { return typeof o === 'string' ? o.split(',').map(v => v.trim()).filter(Boolean) : Array.isArray(o) ? o : []; }
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background-color: rgba(156, 163, 175, 0.5); border-radius: 20px; }
.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>
