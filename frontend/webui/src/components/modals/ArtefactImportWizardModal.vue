<script setup>
import { ref, computed } from 'vue';
import { useNotebookStore } from '../../stores/notebooks';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';

// Icons
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconWeb from '../../assets/icons/IconWeb.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconVideoCamera from '../../assets/icons/IconVideoCamera.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const notebookStore = useNotebookStore();
const uiStore = useUiStore();

const modalData = computed(() => uiStore.modalData('artefactImportWizard'));
const notebookId = computed(() => modalData.value?.notebookId);

const activeTab = ref('files');
const isProcessing = ref(false);

const form = ref({
    urls: [],
    wikipedia_urls: [],
    youtube_configs: [], // { url: '', lang: 'en' }
    files: [],
    manual_title: '',
    manual_content: ''
});

const languages = [
    { code: 'en', name: 'English' },
    { code: 'fr', name: 'French' },
    { code: 'es', name: 'Spanish' },
    { code: 'de', name: 'German' },
    { code: 'it', name: 'Italian' },
    { code: 'pt', name: 'Portuguese' },
    { code: 'zh', name: 'Chinese' },
    { code: 'ja', name: 'Japanese' },
    { code: 'ru', name: 'Russian' }
];

// Temp inputs
const tempUrl = ref('');
const tempWiki = ref('');
const tempYt = ref({ url: '', lang: 'en' });
const fileInput = ref(null);

const addUrl = () => { if (tempUrl.value.trim()) { form.value.urls.push(tempUrl.value.trim()); tempUrl.value = ''; } };
const addWiki = () => { if (tempWiki.value.trim()) { form.value.wikipedia_urls.push(tempWiki.value.trim()); tempWiki.value = ''; } };
const addYt = () => { if (tempYt.value.url.trim()) { form.value.youtube_configs.push({ ...tempYt.value }); tempYt.value.url = ''; } };
const onFileChange = (e) => { form.value.files.push(...Array.from(e.target.files)); e.target.value = ''; };

const hasContent = computed(() => {
    return form.value.urls.length > 0 || 
           form.value.wikipedia_urls.length > 0 || 
           form.value.youtube_configs.length > 0 || 
           form.value.files.length > 0 || 
           (form.value.manual_title.trim() && form.value.manual_content.trim());
});

async function handleImport() {
    if (!notebookId.value) return;
    isProcessing.value = true;
    try {
        // 1. Process List-based imports (URLs, Wiki, YouTube)
        if (form.value.urls.length || form.value.wikipedia_urls.length || form.value.youtube_configs.length) {
            await notebookStore.importSources({
                urls: form.value.urls,
                wikipedia_urls: form.value.wikipedia_urls,
                youtube_configs: form.value.youtube_configs
            });
        }

        // 2. Process Files
        for (const file of form.value.files) {
            await notebookStore.uploadSource(file, true);
        }

        // 3. Process Manual Text
        if (form.value.manual_title && form.value.manual_content) {
            await notebookStore.createManualArtefact(form.value.manual_title, form.value.manual_content);
        }

        uiStore.addNotification("Knowledge import tasks started.", "success");
        uiStore.closeModal('artefactImportWizard');
    } catch (e) {
        uiStore.addNotification("Import failed.", "error");
    } finally {
        isProcessing.value = false;
    }
}

const tabs = [
    { id: 'files', label: 'Documents', icon: IconFileText },
    { id: 'web', label: 'Links', icon: IconWeb },
    { id: 'wiki', label: 'Wikipedia', icon: IconBookOpen },
    { id: 'youtube', label: 'YouTube', icon: IconVideoCamera },
    { id: 'manual', label: 'Manual Text', icon: IconPencil }
];
</script>

<template>
    <GenericModal modalName="artefactImportWizard" title="Knowledge Import Wizard" maxWidthClass="max-w-2xl">
        <template #body>
            <div class="flex flex-col h-[500px]">
                <!-- Tab Navigation -->
                <div class="flex border-b dark:border-gray-700 overflow-x-auto no-scrollbar bg-gray-50 dark:bg-gray-800/50 p-1">
                    <button v-for="tab in tabs" :key="tab.id" @click="activeTab = tab.id"
                        class="flex items-center gap-2 px-4 py-2 text-[10px] font-black uppercase tracking-widest transition-all rounded-lg"
                        :class="activeTab === tab.id ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'">
                        <component :is="tab.icon" class="w-4 h-4" />
                        {{ tab.label }}
                    </button>
                </div>

                <!-- Tab Content -->
                <div class="flex-grow p-6 overflow-y-auto custom-scrollbar">
                    
                    <!-- FILES -->
                    <div v-if="activeTab === 'files'" class="space-y-4">
                        <div @click="fileInput.click()" class="border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-3xl p-12 text-center cursor-pointer hover:bg-blue-50 dark:hover:bg-blue-900/10 transition-all group">
                            <IconPlus class="w-12 h-12 mx-auto text-gray-300 group-hover:text-blue-500 mb-4 transition-colors" />
                            <p class="text-sm font-black uppercase tracking-tighter text-gray-500">Drop Documents Here</p>
                            <p class="text-[10px] text-gray-400 mt-1 uppercase tracking-widest">PDF, DOCX, PPTX, TXT, MD</p>
                            <input type="file" ref="fileInput" @change="onFileChange" multiple class="hidden" />
                        </div>
                        <div class="flex flex-wrap gap-2">
                            <div v-for="(f, i) in form.files" :key="i" class="px-3 py-1.5 bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded-xl text-[10px] font-bold flex items-center gap-2 border border-purple-100 dark:border-purple-800">
                                <span class="truncate max-w-[200px]">{{ f.name }}</span>
                                <button @click="form.files.splice(i,1)" class="hover:text-red-500"><IconXMark class="w-3 h-3"/></button>
                            </div>
                        </div>
                    </div>

                    <!-- WEB URLS -->
                    <div v-if="activeTab === 'web'" class="space-y-4">
                        <div class="flex gap-2">
                            <input v-model="tempUrl" @keyup.enter="addUrl" placeholder="Enter link (https://...)" class="input-field flex-grow" />
                            <button @click="addUrl" class="btn btn-secondary"><IconPlus class="w-5 h-5" /></button>
                        </div>
                        <div class="space-y-2">
                            <div v-for="(u, i) in form.urls" :key="i" class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-xl text-xs border dark:border-gray-700">
                                <span class="truncate pr-4 font-medium">{{ u }}</span>
                                <button @click="form.urls.splice(i,1)" class="text-red-500 hover:scale-110 transition-transform"><IconXMark class="w-4 h-4"/></button>
                            </div>
                        </div>
                    </div>

                    <!-- WIKIPEDIA -->
                    <div v-if="activeTab === 'wiki'" class="space-y-4">
                        <div class="p-4 bg-blue-50 dark:bg-blue-900/10 rounded-2xl border border-blue-100 dark:border-blue-900/30 text-[10px] text-blue-700 dark:text-blue-300 font-bold uppercase tracking-widest">
                            Ground your notebook with full Wikipedia articles.
                        </div>
                        <div class="flex gap-2">
                            <input v-model="tempWiki" @keyup.enter="addWiki" placeholder="Article Title or Wiki URL..." class="input-field flex-grow" />
                            <button @click="addWiki" class="btn btn-secondary"><IconPlus class="w-5 h-5" /></button>
                        </div>
                        <div class="space-y-2">
                            <div v-for="(u, i) in form.wikipedia_urls" :key="i" class="flex items-center justify-between p-3 bg-gray-100 dark:bg-gray-850 rounded-xl text-xs border-l-4 border-gray-400">
                                <span class="truncate pr-4 font-bold">{{ u }}</span>
                                <button @click="form.wikipedia_urls.splice(i,1)" class="text-red-500 hover:scale-110"><IconXMark class="w-4 h-4"/></button>
                            </div>
                        </div>
                    </div>

                    <!-- YOUTUBE -->
                    <div v-if="activeTab === 'youtube'" class="space-y-4">
                        <div class="flex gap-2">
                            <input v-model="tempYt.url" placeholder="YouTube Video URL..." class="input-field flex-grow" />
                            <select v-model="tempYt.lang" class="input-field w-32">
                                <option v-for="l in languages" :key="l.code" :value="l.code">{{ l.name }}</option>
                            </select>
                            <button @click="addYt" class="btn btn-secondary"><IconPlus class="w-5 h-5" /></button>
                        </div>
                        <div class="space-y-2">
                            <div v-for="(y, i) in form.youtube_configs" :key="i" class="flex items-center justify-between p-3 bg-red-50 dark:bg-red-900/10 rounded-xl text-xs border-l-4 border-red-500">
                                <span class="truncate pr-4 font-bold text-red-700 dark:text-red-400">{{ y.url }}</span>
                                <div class="flex items-center gap-3">
                                    <span class="text-[9px] font-black uppercase px-2 py-1 bg-white dark:bg-gray-800 rounded border border-red-200">{{ y.lang }}</span>
                                    <button @click="form.youtube_configs.splice(i,1)" class="text-red-500 hover:scale-110"><IconXMark class="w-4 h-4"/></button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- MANUAL TEXT -->
                    <div v-if="activeTab === 'manual'" class="space-y-4 h-full flex flex-col">
                        <input v-model="form.manual_title" placeholder="Artefact Title (e.g. Brainstorming Notes)" class="input-field font-bold" />
                        <textarea v-model="form.manual_content" placeholder="Paste or type content here..." class="flex-grow input-field text-sm leading-relaxed min-h-[200px] resize-none"></textarea>
                    </div>

                </div>

                <!-- Footer -->
                <div class="p-6 border-t dark:border-gray-700 flex justify-end items-center gap-3 bg-gray-50 dark:bg-gray-800/30">
                    <button @click="uiStore.closeModal('artefactImportWizard')" class="btn btn-secondary px-6">Cancel</button>
                    <button @click="handleImport" :disabled="!hasContent || isProcessing" class="btn btn-primary px-10 relative shadow-lg shadow-blue-500/20 font-black uppercase text-xs tracking-widest">
                        <IconAnimateSpin v-if="isProcessing" class="w-4 h-4 mr-2 animate-spin" />
                        Start Ingestion
                    </button>
                </div>
            </div>
        </template>
    </GenericModal>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>
