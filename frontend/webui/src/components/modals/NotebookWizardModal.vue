<script setup>
import { ref, computed, reactive } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useNotebookStore } from '../../stores/notebooks';
import { useAuthStore } from '../../stores/auth';
import { storeToRefs } from 'pinia';
import GenericModal from './GenericModal.vue';

// Icons
import IconArrowRight from '../../assets/icons/IconArrowRight.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconUpload from '../../assets/icons/IconUpload.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconWeb from '../../assets/icons/ui/IconWeb.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue'; 

const uiStore = useUiStore();
const notebookStore = useNotebookStore();
const authStore = useAuthStore();
const { user } = storeToRefs(authStore);

const currentStep = ref(0);
const isLoading = ref(false);
const fileInput = ref(null);
const urlInput = ref('');
const youtubeInput = ref('');
const activeSourceTab = ref('web'); // web, youtube, files, text

const hasLLM = computed(() => !!user.value?.lollms_model_name);
const hasTTI = computed(() => !!user.value?.tti_binding_model_name);

const formData = ref({
    type: 'generic',
    title: '',
    prompt: '',
    files: [],
    urls: [],
    youtube_urls: [],
    raw_text: '',
    structure: [],
    // Slide specifics
    slideFormat: '16:9',
    slideStyle: 'corporate',
    slideMode: 'image_only',
    customStyle: '',
    numSlides: 8 // Default number of slides
});

const notebookTypes = computed(() => [
    { id: 'generic', name: 'Empty Notebook', desc: 'Standard multi-tab scratchpad.', icon: IconFileText, available: true },
    { id: 'data_analysis', name: 'Data Analysis', desc: 'Extract specific information and build knowledge from documents.', icon: IconPresentationChartBar, available: hasLLM.value },
    { id: 'book_building', name: 'Book Building', desc: 'Structure, write, and compile chapters for a book or report.', icon: IconBookOpen, available: hasLLM.value },
    { id: 'slides_making', name: 'Slides Making', desc: 'Generate slide decks with visuals.', icon: IconPhoto, available: hasLLM.value && hasTTI.value },
    { id: 'benchmarks', name: 'Benchmarks', desc: 'Test and compare LLMs with input data.', icon: IconServer, available: hasLLM.value }
]);
const slideFormats = [ { value: '16:9', label: 'Widescreen (16:9)', width: 1920, height: 1080 }, { value: '4:3', label: 'Standard (4:3)', width: 1024, height: 768 }, { value: '1:1', label: 'Square (1:1)', width: 1080, height: 1080 } ];
const slideModes = [ { value: 'image_only', label: 'Visual (All-Image)', desc: 'AI generates full-slide images with embedded text/layout. Best for artistic decks.' }, { value: 'hybrid', label: 'Hybrid (Templates)', desc: 'AI fills standard layouts (Title, Bullets, Images). Editable and clean.' }, { value: 'text_only', label: 'Text Outline', desc: 'Simple bullet points and headers. No image generation.' } ];
const slideStyles = [ { value: 'corporate', label: 'Corporate', prompt: 'clean, professional, minimalist, blue and white color scheme, vector flat art' }, { value: 'creative', label: 'Creative', prompt: 'colorful, artistic, abstract shapes, vibrant gradients, modern design' }, { value: 'dark_tech', label: 'Dark Tech', prompt: 'dark mode, neon accents, futuristic, cyberpunk aesthetic, high contrast' }, { value: 'hand_drawn', label: 'Hand Drawn', prompt: 'sketch style, pencil texture, pastel colors, organic lines, playful' }, { value: 'nature', label: 'Nature', prompt: 'earth tones, green and brown, natural textures, soft lighting, eco-friendly feel' }, { value: 'custom', label: 'Custom...', prompt: '' } ];

function selectType(typeId) {
    const type = notebookTypes.value.find(t => t.id === typeId);
    if (!type.available) return;
    formData.value.type = typeId;
    if (typeId === 'generic') createNotebook(); 
    else currentStep.value = 1;
}

function triggerFileUpload() { fileInput.value.click(); }
function handleFileUpload(e) { formData.value.files.push(...Array.from(e.target.files)); e.target.value = ''; }
function addUrl() { if (urlInput.value.trim()) { formData.value.urls.push(urlInput.value.trim()); urlInput.value = ''; } }
function addYoutubeUrl() { if (youtubeInput.value.trim()) { formData.value.youtube_urls.push(youtubeInput.value.trim()); youtubeInput.value = ''; } }
function removeFile(index) { formData.value.files.splice(index, 1); }
function removeUrl(index) { formData.value.urls.splice(index, 1); }
function removeYoutubeUrl(index) { formData.value.youtube_urls.splice(index, 1); }

const computedStylePrompt = computed(() => {
    if (formData.value.type !== 'slides_making') return '';
    const styleObj = slideStyles.find(s => s.value === formData.value.slideStyle);
    let styleText = styleObj ? styleObj.prompt : '';
    if (formData.value.slideStyle === 'custom' || (formData.value.customStyle && formData.value.slideStyle !== 'custom')) {
        if (styleText) styleText += ', ';
        styleText += formData.value.customStyle;
    }
    return styleText;
});

const totalSourcesCount = computed(() => formData.value.files.length + formData.value.urls.length + formData.value.youtube_urls.length + (formData.value.raw_text ? 1 : 0));

async function createNotebook() {
    if (!formData.value.title && formData.value.type !== 'generic') {
        formData.value.title = formData.value.prompt.slice(0, 30) || 'New Notebook';
    } else if (!formData.value.title) {
        formData.value.title = 'New Notebook';
    }

    isLoading.value = true;
    try {
        notebookStore.activeNotebook = null;

        const metadata = { topic: formData.value.prompt };
        if (formData.value.type === 'slides_making') {
            const formatObj = slideFormats.find(f => f.value === formData.value.slideFormat);
            metadata.format = formatObj || slideFormats[0];
            metadata.style_prompt = computedStylePrompt.value;
            metadata.slide_mode = formData.value.slideMode;
        }

        const notebook = await notebookStore.createStructuredNotebook({
            title: formData.value.title,
            type: formData.value.type,
            urls: formData.value.urls,
            youtube_urls: formData.value.youtube_urls,
            raw_text: formData.value.raw_text,
            metadata: metadata,
            initialPrompt: formData.value.prompt 
        });

        notebookStore.activeNotebook = notebook;

        if (formData.value.files.length > 0) {
            // Upload files (assuming docling support for complex formats)
            await Promise.all(formData.value.files.map(f => notebookStore.uploadSource(f, true)));
        }

        if (formData.value.type !== 'generic' && formData.value.prompt) {
            let action = 'text';
            let finalPrompt = formData.value.prompt;

            if (formData.value.type === 'slides_making') {
                action = 'generate_slides_text';
                // Enforce slide count and structure in the prompt
                finalPrompt = `Create a presentation with approximately ${formData.value.numSlides || 8} slides about: "${formData.value.prompt}".`;
            }
            else if (formData.value.type === 'data_analysis') action = 'analyze_data';
            else if (formData.value.type === 'book_building') action = 'generate_outline';
            else if (formData.value.type === 'benchmarks') action = 'generate_test_cases';

            await notebookStore.processWithAi(
                finalPrompt, 
                [], 
                action,
                null
            );
        }

        uiStore.closeModal('notebookWizard');
        currentStep.value = 0;
        // Reset form
        formData.value = { type: 'generic', title: '', prompt: '', files: [], urls: [], youtube_urls: [], raw_text: '', structure: [], slideFormat: '16:9', slideStyle: 'corporate', slideMode: 'image_only', customStyle: '', numSlides: 8 };

    } catch (e) {
        console.error(e);
        uiStore.addNotification("Failed to create notebook.", "error");
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal modal-name="notebookWizard" title="Create New Notebook" max-width-class="max-w-4xl">
        <template #body>
            <div class="min-h-[400px]">
                <!-- Step Indicator -->
                <div class="flex items-center justify-center mb-6">
                    <div class="flex items-center text-sm">
                        <span class="font-bold cursor-pointer" @click="currentStep=0" :class="currentStep >= 0 ? 'text-blue-600' : 'text-gray-400'">Type</span>
                        <IconArrowRight class="w-4 h-4 mx-2 text-gray-400" />
                        <span class="font-bold cursor-pointer" @click="currentStep=1" :class="currentStep >= 1 ? 'text-blue-600' : 'text-gray-400'">Details</span>
                        <IconArrowRight class="w-4 h-4 mx-2 text-gray-400" />
                        <span class="font-bold cursor-pointer" @click="currentStep=2" :class="currentStep >= 2 ? 'text-blue-600' : 'text-gray-400'">Sources</span>
                    </div>
                </div>

                <!-- STEP 0: TYPE -->
                <div v-if="currentStep === 0" class="space-y-4">
                    <p class="text-gray-500 dark:text-gray-400 text-sm text-center mb-6">Select a template to get started.</p>
                    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        <div v-for="type in notebookTypes" :key="type.id" @click="selectType(type.id)"
                             class="group relative p-4 border rounded-xl transition-all duration-200"
                             :class="[type.available ? 'cursor-pointer hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800' : 'cursor-not-allowed opacity-60 border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-900']">
                            <div class="flex items-start justify-between mb-3">
                                <component :is="type.icon" class="w-8 h-8 text-gray-400 group-hover:text-blue-500 transition-colors" />
                                <span v-if="!type.available" class="text-[10px] uppercase font-bold text-red-400 bg-red-50 dark:bg-red-900/20 px-2 py-0.5 rounded">Unavailable</span>
                            </div>
                            <h3 class="font-bold text-gray-900 dark:text-gray-100 mb-1">{{ type.name }}</h3>
                            <p class="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">{{ type.desc }}</p>
                        </div>
                    </div>
                </div>

                <!-- STEP 1: CONFIG -->
                <div v-if="currentStep === 1" class="space-y-6">
                    <div class="grid grid-cols-1 gap-6">
                        <div class="space-y-4">
                            <div>
                                <label class="block text-sm font-medium mb-1">Notebook Title</label>
                                <input v-model="formData.title" type="text" class="input-field w-full" placeholder="e.g., Q3 Report">
                            </div>
                            <div>
                                <label class="block text-sm font-medium mb-1">Topic / Goal</label>
                                <textarea v-model="formData.prompt" class="input-field w-full h-32 resize-none" placeholder="Describe what you want to achieve..."></textarea>
                            </div>
                        </div>
                    </div>

                    <!-- SLIDE SETTINGS -->
                    <div v-if="formData.type === 'slides_making'" class="border-t dark:border-gray-700 pt-4">
                        <h4 class="font-bold text-gray-700 dark:text-gray-200 mb-4 flex items-center gap-2">
                            <IconPresentationChartBar class="w-4 h-4" /> Slide Settings
                        </h4>
                        
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div class="space-y-4">
                                <div>
                                    <label class="block text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">Generation Mode</label>
                                    <div class="space-y-2">
                                        <label v-for="mode in slideModes" :key="mode.value" 
                                            class="flex items-start p-2 border rounded cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                                            :class="formData.slideMode === mode.value ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/10' : 'border-gray-200 dark:border-gray-700'">
                                            <input type="radio" v-model="formData.slideMode" :value="mode.value" class="mt-1 text-blue-600 focus:ring-blue-500">
                                            <div class="ml-3">
                                                <span class="block text-sm font-medium">{{ mode.label }}</span>
                                                <span class="block text-xs text-gray-500">{{ mode.desc }}</span>
                                            </div>
                                        </label>
                                    </div>
                                </div>
                                <!-- Target Number of Slides -->
                                <div>
                                    <label class="block text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">Target Slide Count</label>
                                    <input type="number" v-model.number="formData.numSlides" min="1" max="50" class="input-field w-full text-sm" placeholder="e.g. 10">
                                </div>
                            </div>
                            
                            <div class="space-y-4">
                                <div>
                                    <label class="block text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">Format</label>
                                    <div class="flex flex-wrap gap-2">
                                        <label v-for="fmt in slideFormats" :key="fmt.value" 
                                               class="cursor-pointer border rounded px-3 py-2 text-xs flex items-center gap-2 hover:border-blue-400 transition-colors"
                                               :class="formData.slideFormat === fmt.value ? 'bg-blue-50 border-blue-500 text-blue-700' : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-600'">
                                            <input type="radio" v-model="formData.slideFormat" :value="fmt.value" class="hidden">
                                            {{ fmt.label }}
                                        </label>
                                    </div>
                                </div>
                                <div>
                                    <label class="block text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">Visual Style</label>
                                    <select v-model="formData.slideStyle" class="input-field w-full text-sm">
                                        <option v-for="style in slideStyles" :key="style.value" :value="style.value">{{ style.label }}</option>
                                    </select>
                                    <div class="mt-2">
                                        <input v-model="formData.customStyle" type="text" class="input-field w-full text-xs" placeholder="Additional style keywords (e.g. 'purple and gold, energetic')...">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- STEP 2: SOURCES -->
                <div v-if="currentStep === 2" class="space-y-4 h-full flex flex-col">
                    <div class="flex justify-between items-center mb-2">
                        <p class="text-sm text-gray-600 dark:text-gray-400">Add knowledge sources for the AI.</p>
                        <div class="text-xs font-bold bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 px-2 py-1 rounded">
                            Total Sources: {{ totalSourcesCount }}
                        </div>
                    </div>
                    
                    <!-- Tabs -->
                    <div class="flex border-b border-gray-200 dark:border-gray-700">
                        <button @click="activeSourceTab = 'web'" :class="['px-4 py-2 text-sm font-medium border-b-2 transition-colors', activeSourceTab === 'web' ? 'border-blue-500 text-blue-600 dark:text-blue-400' : 'border-transparent text-gray-500 hover:text-gray-700']">Web & Wiki</button>
                        <button @click="activeSourceTab = 'youtube'" :class="['px-4 py-2 text-sm font-medium border-b-2 transition-colors', activeSourceTab === 'youtube' ? 'border-red-500 text-red-600 dark:text-red-400' : 'border-transparent text-gray-500 hover:text-gray-700']">YouTube</button>
                        <button @click="activeSourceTab = 'files'" :class="['px-4 py-2 text-sm font-medium border-b-2 transition-colors', activeSourceTab === 'files' ? 'border-purple-500 text-purple-600 dark:text-purple-400' : 'border-transparent text-gray-500 hover:text-gray-700']">Files</button>
                        <button @click="activeSourceTab = 'text'" :class="['px-4 py-2 text-sm font-medium border-b-2 transition-colors', activeSourceTab === 'text' ? 'border-green-500 text-green-600 dark:text-green-400' : 'border-transparent text-gray-500 hover:text-gray-700']">Raw Text</button>
                    </div>

                    <!-- Content -->
                    <div class="flex-grow py-4">
                        <!-- WEB TAB -->
                        <div v-show="activeSourceTab === 'web'" class="space-y-4">
                            <div class="flex gap-2">
                                <input v-model="urlInput" @keyup.enter="addUrl" type="text" class="input-field flex-grow text-sm" placeholder="https://wikipedia.org/wiki/...">
                                <button @click="addUrl" class="btn btn-primary px-3"><IconPlus class="w-4 h-4"/></button>
                            </div>
                            <div class="space-y-1 max-h-48 overflow-y-auto">
                                <div v-for="(url, idx) in formData.urls" :key="idx" class="flex items-center justify-between text-xs bg-gray-100 dark:bg-gray-700 p-2 rounded">
                                    <span class="truncate max-w-[300px] flex items-center gap-2"><IconWeb class="w-3 h-3 text-blue-500"/> {{ url }}</span>
                                    <button @click="removeUrl(idx)" class="text-red-500 hover:text-red-700"><IconTrash class="w-3 h-3" /></button>
                                </div>
                                <p v-if="formData.urls.length === 0" class="text-xs text-gray-400 italic text-center py-2">No URLs added.</p>
                            </div>
                        </div>

                        <!-- YOUTUBE TAB -->
                        <div v-show="activeSourceTab === 'youtube'" class="space-y-4">
                            <div class="flex gap-2">
                                <input v-model="youtubeInput" @keyup.enter="addYoutubeUrl" type="text" class="input-field flex-grow text-sm" placeholder="...">
                                <button @click="addYoutubeUrl" class="btn btn-primary px-3 bg-red-600 hover:bg-red-700 border-red-600"><IconPlus class="w-4 h-4"/></button>
                            </div>
                            <div class="space-y-1 max-h-48 overflow-y-auto">
                                <div v-for="(url, idx) in formData.youtube_urls" :key="idx" class="flex items-center justify-between text-xs bg-gray-100 dark:bg-gray-700 p-2 rounded">
                                    <span class="truncate max-w-[300px] flex items-center gap-2"><IconPlayCircle class="w-3 h-3 text-red-500"/> {{ url }}</span>
                                    <button @click="removeYoutubeUrl(idx)" class="text-red-500 hover:text-red-700"><IconTrash class="w-3 h-3" /></button>
                                </div>
                                <p v-if="formData.youtube_urls.length === 0" class="text-xs text-gray-400 italic text-center py-2">No videos added.</p>
                            </div>
                        </div>

                        <!-- FILES TAB -->
                        <div v-show="activeSourceTab === 'files'" class="space-y-4">
                            <div class="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-6 flex flex-col items-center justify-center text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors cursor-pointer" @click="triggerFileUpload">
                                <IconUpload class="w-8 h-8 mb-2" />
                                <span class="text-sm font-medium">Click to upload files</span>
                                <span class="text-xs text-gray-400">PDF, DOCX, PPTX (Docling conversion enabled)</span>
                                <input type="file" ref="fileInput" @change="handleFileUpload" multiple class="hidden">
                            </div>
                            <div class="space-y-1 max-h-48 overflow-y-auto">
                                <div v-for="(file, idx) in formData.files" :key="idx" class="flex items-center justify-between text-xs bg-gray-100 dark:bg-gray-700 p-2 rounded">
                                    <span class="truncate max-w-[300px] font-medium">{{ file.name }}</span>
                                    <button @click="removeFile(idx)" class="text-red-500 hover:text-red-700"><IconTrash class="w-3 h-3" /></button>
                                </div>
                            </div>
                        </div>

                        <!-- RAW TEXT TAB -->
                        <div v-show="activeSourceTab === 'text'" class="h-full">
                            <textarea v-model="formData.raw_text" class="input-field w-full h-48 resize-none font-mono text-xs" placeholder="Paste any raw text context here..."></textarea>
                        </div>
                    </div>
                </div>
            </div>
        </template>

        <template #footer>
            <div class="flex justify-between w-full">
                <button v-if="currentStep > 0" @click="currentStep--" class="btn btn-secondary">Back</button>
                <div v-else class="flex-grow"></div> 
                <div class="flex gap-2">
                    <button @click="uiStore.closeModal('notebookWizard')" class="btn btn-secondary">Cancel</button>
                    <button v-if="currentStep < 2" @click="currentStep++" class="btn btn-primary">
                        Next <IconArrowRight class="w-4 h-4 ml-2" />
                    </button>
                    <button v-else @click="createNotebook" class="btn btn-primary" :disabled="isLoading">
                        <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
                        {{ isLoading ? 'Creating...' : 'Create Notebook' }}
                    </button>
                </div>
            </div>
        </template>
    </GenericModal>
</template>
