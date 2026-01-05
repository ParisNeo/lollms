<template>
    <GenericModal modal-name="notebookWizard" title="New Production Wizard" max-width-class="max-w-4xl">
        <template #body>
            <div class="flex flex-col h-full gap-6">
                <!-- Step Indicator -->
                <div class="flex items-center justify-center space-x-4 mb-4">
                    <div v-for="step in 3" :key="step" class="flex items-center">
                        <div class="w-8 h-8 rounded-full flex items-center justify-center font-bold transition-all"
                             :class="currentStep >= step ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500 dark:bg-gray-700'">
                            {{ step }}
                        </div>
                        <div v-if="step < 3" class="w-12 h-1 bg-gray-200 dark:bg-gray-700 mx-2">
                            <div class="h-full bg-blue-600 transition-all" :style="{ width: currentStep > step ? '100%' : '0%' }"></div>
                        </div>
                    </div>
                </div>

                <!-- STEP 1: Basic Info & Config -->
                <div v-if="currentStep === 1" class="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
                    <div>
                        <label class="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">Project Title</label>
                        <input v-model="form.title" class="input-field w-full text-lg" placeholder="e.g. Quantum Computing Overview" autofocus />
                    </div>
                    
                    <div>
                        <label class="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">Production Type</label>
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <button v-for="type in projectTypes" :key="type.id" 
                                @click="form.type = type.id"
                                class="p-4 rounded-xl border-2 transition-all flex flex-col items-center gap-2 text-center hover:bg-gray-50 dark:hover:bg-gray-800"
                                :class="form.type === type.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-200 dark:border-gray-700'">
                                <component :is="type.icon" class="w-8 h-8" :class="form.type === type.id ? 'text-blue-500' : 'text-gray-400'" />
                                <span class="font-bold text-sm">{{ type.label }}</span>
                            </button>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label class="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">Language</label>
                            <select v-model="form.language" class="input-field w-full">
                                <option value="en">English</option>
                                <option value="fr">French</option>
                                <option value="es">Spanish</option>
                                <option value="de">German</option>
                                <option value="zh">Chinese</option>
                                <option value="it">Italian</option>
                                <option value="pt">Portuguese</option>
                                <option value="ja">Japanese</option>
                                <option value="ru">Russian</option>
                                <option value="ar">Arabic</option>
                            </select>
                        </div>

                        <!-- SLIDE SPECIFIC SETTINGS -->
                        <div v-if="form.type === 'slides_making'" class="col-span-2 grid grid-cols-1 sm:grid-cols-3 gap-4 p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg border dark:border-gray-700">
                            <div>
                                <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Slide Count</label>
                                <input v-model.number="form.num_slides" type="number" min="3" max="50" class="input-field w-full" />
                            </div>
                            <div>
                                <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Visual Style</label>
                                <select v-model="form.style_preset" class="input-field w-full">
                                    <option value="Corporate">Corporate</option>
                                    <option value="Creative">Creative</option>
                                    <option value="Minimalist">Minimalist</option>
                                    <option value="Academic">Academic</option>
                                    <option value="Cyberpunk">Cyberpunk</option>
                                    <option value="Hand-drawn">Hand-drawn</option>
                                    <option value="Photorealistic">Photorealistic</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Layout Template</label>
                                <select v-model="form.template_name" class="input-field w-full">
                                    <option value="Modern">Modern</option>
                                    <option value="Classic">Classic</option>
                                    <option value="Bold">Bold</option>
                                    <option value="Grid">Grid</option>
                                </select>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- STEP 2: Sources & Data -->
                <div v-if="currentStep === 2" class="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300 h-full overflow-y-auto custom-scrollbar pr-2">
                    <p class="text-sm text-gray-500">Add knowledge sources to ground your content in facts. The AI will read these before generating.</p>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <!-- Left Column: Web Sources -->
                        <div class="space-y-4">
                            <!-- URLs -->
                            <div class="space-y-2">
                                <label class="text-xs font-bold uppercase text-gray-500 flex justify-between">
                                    <span>Web Links</span>
                                    <button @click="form.urls.push('')" class="text-blue-500 hover:underline flex items-center gap-1"><IconPlus class="w-3 h-3"/> Add</button>
                                </label>
                                <div v-for="(url, idx) in form.urls" :key="'url-'+idx" class="flex gap-2">
                                    <input v-model="form.urls[idx]" class="input-field flex-grow py-1 text-sm" placeholder="https://example.com/article" />
                                    <button @click="form.urls.splice(idx, 1)" class="text-red-500 p-1.5 hover:bg-red-50 rounded"><IconTrash class="w-4 h-4"/></button>
                                </div>
                                <div v-if="form.urls.length === 0" class="text-xs text-gray-400 italic">No URLs added.</div>
                            </div>

                            <!-- YouTube -->
                            <div class="space-y-2">
                                <label class="text-xs font-bold uppercase text-gray-500 flex justify-between">
                                    <span>YouTube Videos</span>
                                    <button @click="form.youtube_urls.push('')" class="text-red-500 hover:underline flex items-center gap-1"><IconPlus class="w-3 h-3"/> Add</button>
                                </label>
                                <div v-for="(yt, idx) in form.youtube_urls" :key="'yt-'+idx" class="flex gap-2">
                                    <input v-model="form.youtube_urls[idx]" class="input-field flex-grow py-1 text-sm" placeholder="https://youtube.com/watch?v=..." />
                                    <button @click="form.youtube_urls.splice(idx, 1)" class="text-red-500 p-1.5 hover:bg-red-50 rounded"><IconTrash class="w-4 h-4"/></button>
                                </div>
                                <div v-if="form.youtube_urls.length === 0" class="text-xs text-gray-400 italic">No videos added.</div>
                            </div>

                            <!-- Wikipedia -->
                            <div class="space-y-2">
                                <label class="text-xs font-bold uppercase text-gray-500 flex justify-between">
                                    <span>Wikipedia Topics</span>
                                    <button @click="form.wikipedia_urls.push('')" class="text-gray-600 dark:text-gray-400 hover:underline flex items-center gap-1"><IconPlus class="w-3 h-3"/> Add</button>
                                </label>
                                <div v-for="(wiki, idx) in form.wikipedia_urls" :key="'wiki-'+idx" class="flex gap-2">
                                    <input v-model="form.wikipedia_urls[idx]" class="input-field flex-grow py-1 text-sm" placeholder="Topic name or URL" />
                                    <button @click="form.wikipedia_urls.splice(idx, 1)" class="text-red-500 p-1.5 hover:bg-red-50 rounded"><IconTrash class="w-4 h-4"/></button>
                                </div>
                                <div v-if="form.wikipedia_urls.length === 0" class="text-xs text-gray-400 italic">No topics added.</div>
                            </div>
                        </div>

                        <!-- Right Column: Local Data -->
                        <div class="space-y-4">
                            <!-- Local Files -->
                            <div class="space-y-2">
                                <label class="text-xs font-bold uppercase text-gray-500">Local Files</label>
                                <div class="border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-lg p-4 text-center hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors cursor-pointer" @click="triggerFileUpload">
                                    <IconUpload class="w-6 h-6 mx-auto text-gray-400 mb-2"/>
                                    <span class="text-sm text-gray-500">Click to upload documents</span>
                                    <input type="file" ref="fileInput" multiple class="hidden" @change="handleFileSelection" />
                                </div>
                                <div v-if="fileList.length > 0" class="space-y-1 max-h-32 overflow-y-auto custom-scrollbar">
                                    <div v-for="(file, idx) in fileList" :key="'file-'+idx" class="flex items-center justify-between p-2 bg-gray-100 dark:bg-gray-800 rounded text-sm">
                                        <span class="truncate max-w-[180px]">{{ file.name }}</span>
                                        <button @click="removeFile(idx)" class="text-gray-500 hover:text-red-500"><IconXMark class="w-4 h-4"/></button>
                                    </div>
                                </div>
                            </div>

                            <!-- Raw Text -->
                            <div class="space-y-2">
                                <label class="text-xs font-bold uppercase text-gray-500">Raw Text / Notes</label>
                                <textarea v-model="form.raw_text" class="input-field w-full h-32 resize-none text-sm" placeholder="Paste snippets, notes, or data here directly..."></textarea>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- STEP 3: Prompt & Launch -->
                <div v-if="currentStep === 3" class="space-y-6 animate-in fade-in slide-in-from-right-4 duration-300">
                    <div>
                        <label class="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">Instruction Prompt</label>
                        <textarea v-model="form.initialPrompt" class="input-field w-full h-40 resize-none text-base shadow-sm p-4" 
                            placeholder="Describe what you want to create in detail. 
Example: Create a slide deck explaining the basics of quantum entanglement for high school students. Use metaphors and keep it visual."></textarea>
                    </div>
                    
                    <div class="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg flex items-start gap-3 border border-blue-100 dark:border-blue-800">
                        <IconSparkles class="w-6 h-6 text-blue-500 flex-shrink-0 mt-1" />
                        <div>
                            <h4 class="font-bold text-sm text-blue-700 dark:text-blue-300">AI Workflow</h4>
                            <ul class="text-xs text-blue-600 dark:text-blue-400 list-disc list-inside mt-1 space-y-1">
                                <li>Ingest and analyze {{ sourceCount }} external sources + {{ fileList.length }} files</li>
                                <li>Extract key information and facts using LCP</li>
                                <li>Generate structured {{ form.type }} content ({{ form.num_slides }} slides if applicable)</li>
                                <li>Build production assets (slides/chapters)</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </template>

        <template #footer>
            <div class="flex justify-between w-full">
                <button v-if="currentStep > 1" @click="currentStep--" class="btn btn-secondary">Back</button>
                <div v-else></div> <!-- Spacer -->
                
                <div class="flex gap-2">
                    <button @click="uiStore.closeModal('notebookWizard')" class="btn btn-secondary">Cancel</button>
                    <button v-if="currentStep < 3" @click="currentStep++" class="btn btn-primary" :disabled="!form.title">Next</button>
                    <button v-else @click="createNotebook" class="btn btn-primary shadow-lg shadow-blue-500/30" :disabled="!form.initialPrompt || isCreating">
                        <IconAnimateSpin v-if="isCreating" class="w-4 h-4 mr-2 animate-spin" />
                        {{ isCreating ? 'Initializing...' : 'Launch Production' }}
                    </button>
                </div>
            </div>
        </template>
    </GenericModal>
</template>

<script setup>
import { ref, computed, reactive } from 'vue';
import { useRouter } from 'vue-router';
import { useNotebookStore } from '../../stores/notebooks';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';

// Icons
import IconServer from '../../assets/icons/IconServer.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconVideoCamera from '../../assets/icons/IconVideoCamera.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconUpload from '../../assets/icons/IconUpload.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';

const router = useRouter();
const notebookStore = useNotebookStore();
const uiStore = useUiStore();

const currentStep = ref(1);
const isCreating = ref(false);
const fileInput = ref(null);
const fileList = ref([]);

const form = reactive({
    title: '',
    type: 'slides_making', // Default to presentation
    language: 'en',
    initialPrompt: '',
    urls: [],
    youtube_urls: [],
    wikipedia_urls: [],
    raw_text: '',
    // Slide specific
    num_slides: 8,
    style_preset: 'Corporate',
    template_name: 'Modern'
});

const projectTypes = [
    { id: 'generic', label: 'Generic / Research', icon: IconServer },
    { id: 'slides_making', label: 'Presentation Deck', icon: IconPresentationChartBar },
    { id: 'book_building', label: 'Book / Long Form', icon: IconBookOpen },
    { id: 'youtube_video', label: 'Video Script', icon: IconVideoCamera }
];

const sourceCount = computed(() => {
    return form.urls.length + form.youtube_urls.length + form.wikipedia_urls.length + (form.raw_text ? 1 : 0);
});

function triggerFileUpload() {
    fileInput.value?.click();
}

function handleFileSelection(event) {
    const files = Array.from(event.target.files);
    fileList.value.push(...files);
    event.target.value = ''; // Reset for re-selection
}

function removeFile(index) {
    fileList.value.splice(index, 1);
}

async function createNotebook() {
    isCreating.value = true;
    try {
        const hasFiles = fileList.value.length > 0;
        
        // Construct Metadata
        const metadata = {
            num_slides: form.num_slides,
            style_preset: form.style_preset,
            template_name: form.template_name,
            style: form.style_preset // for backward compatibility
        };

        // Clean up empty inputs
        const payload = {
            title: form.title,
            type: form.type,
            language: form.language,
            // If files exist, delay automatic generation until after uploads
            initialPrompt: hasFiles ? null : form.initialPrompt, 
            raw_text: form.raw_text,
            urls: form.urls.filter(u => u.trim()),
            youtube_urls: form.youtube_urls.filter(u => u.trim()),
            wikipedia_urls: form.wikipedia_urls.filter(u => u.trim()),
            youtube_configs: form.youtube_urls.filter(u => u.trim()).map(url => ({ url, lang: form.language })),
            metadata: metadata
        };

        const newNotebook = await notebookStore.createStructuredNotebook(payload);
        
        // Directly update active notebook to ensure UI state consistency before navigation
        notebookStore.activeNotebook = newNotebook;

        // 2. Upload Files if present
        if (hasFiles) {
            uiStore.addNotification(`Uploading ${fileList.value.length} files...`, 'info');
            
            for (const file of fileList.value) {
                try {
                    await notebookStore.uploadSource(file); // Default uses docling=false
                } catch (err) {
                    console.error("File upload failed", err);
                }
            }
            
            // 3. Trigger Generation Manually now that files are uploaded
            // Only if we suppressed it earlier (which we did if hasFiles was true)
            
            let action = 'initial_process';
            if (form.type === 'youtube_video') action = 'generate_script';
            else if (form.type === 'book_building') action = 'generate_book_plan';
            
            uiStore.addNotification("Starting analysis...", "info");
            await notebookStore.processWithAi(form.initialPrompt, [], action);
        }
        
        uiStore.closeModal('notebookWizard');
        
        // Reset form
        Object.assign(form, {
            title: '', type: 'slides_making', language: 'en', initialPrompt: '', 
            urls: [], youtube_urls: [], wikipedia_urls: [], raw_text: '',
            num_slides: 8, style_preset: 'Corporate', template_name: 'Modern'
        });
        fileList.value = [];
        currentStep.value = 1;

        // Navigate to studio (State is already set via direct assignment above)
        router.push('/notebooks');
        
    } catch (e) {
        console.error(e);
        uiStore.addNotification("Failed to launch wizard.", "error");
    } finally {
        isCreating.value = false;
    }
}
</script>
