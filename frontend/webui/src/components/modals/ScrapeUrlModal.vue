<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from './GenericModal.vue';
import IconWeb from '../../assets/icons/ui/IconWeb.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconWikipedia from '../../assets/icons/IconWikipedia.vue';
import IconYoutube from '../../assets/icons/IconYoutube.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const modalData = computed(() => uiStore.modalData('scrapeUrl'));
const discussionId = computed(() => modalData.value?.discussionId);

const url = ref('');
const depth = ref(0);
const processWithAi = ref(false);
const isLoading = ref(false);
const mode = ref('url');
const wikiQuery = ref('');
const youtubeUrl = ref('');
const youtubeLanguage = ref(''); // Added for language input

watch(() => uiStore.isModalOpen('scrapeUrl'), async (isOpen) => {
    if (isOpen) {
        url.value = '';
        depth.value = 0;
        processWithAi.value = false;
        wikiQuery.value = '';
        youtubeUrl.value = '';
        youtubeLanguage.value = ''; // Reset language
        
        await nextTick();
        const data = uiStore.modalData('scrapeUrl');
        mode.value = data?.mode || 'url';
    }
});

async function handleSubmit() {
    if (!discussionId.value) return;

    if (mode.value === 'url') {
        if (!url.value.trim()) {
            uiStore.addNotification('URL is required.', 'warning');
            return;
        }
        isLoading.value = true;
        try {
            await discussionsStore.importArtefactFromUrl(
                discussionId.value, 
                url.value.trim(), 
                depth.value, 
                processWithAi.value
            );
            uiStore.closeModal('scrapeUrl');
        } finally {
            isLoading.value = false;
        }
    } else if (mode.value === 'wikipedia') {
        if (!wikiQuery.value.trim()) {
            uiStore.addNotification('Search query is required.', 'warning');
            return;
        }
        isLoading.value = true;
        try {
            await discussionsStore.importWikipediaArtefact(
                discussionId.value,
                wikiQuery.value.trim()
            );
            uiStore.closeModal('scrapeUrl');
        } finally {
            isLoading.value = false;
        }
    } else if (mode.value === 'youtube') {
        if (!youtubeUrl.value.trim()) {
            uiStore.addNotification('Video URL is required.', 'warning');
            return;
        }
        isLoading.value = true;
        try {
            await discussionsStore.importYoutubeTranscript(
                discussionId.value,
                youtubeUrl.value.trim(),
                youtubeLanguage.value.trim() // Pass language code
            );
            uiStore.closeModal('scrapeUrl');
        } finally {
            isLoading.value = false;
        }
    }
}
</script>

<template>
    <GenericModal
        modalName="scrapeUrl"
        :title="mode === 'url' ? 'Scrape URL' : mode === 'wikipedia' ? 'Import Wikipedia' : 'Import YouTube Transcript'"
        maxWidthClass="max-w-lg"
    >
        <template #body>
            <div class="space-y-4 p-1">
                <!-- Mode Toggle Tabs -->
                <div class="flex border-b border-gray-200 dark:border-gray-700 mb-4">
                    <button 
                        @click="mode = 'url'"
                        class="flex-1 pb-2 text-sm font-medium text-center border-b-2 transition-colors flex items-center justify-center gap-2"
                        :class="mode === 'url' ? 'border-blue-500 text-blue-600 dark:text-blue-400' : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    >
                        <IconWeb class="w-4 h-4" />
                        Web
                    </button>
                    <button 
                        @click="mode = 'wikipedia'"
                        class="flex-1 pb-2 text-sm font-medium text-center border-b-2 transition-colors flex items-center justify-center gap-2"
                        :class="mode === 'wikipedia' ? 'border-blue-500 text-blue-600 dark:text-blue-400' : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    >
                        <IconWikipedia class="w-4 h-4" />
                        Wikipedia
                    </button>
                    <button 
                        @click="mode = 'youtube'"
                        class="flex-1 pb-2 text-sm font-medium text-center border-b-2 transition-colors flex items-center justify-center gap-2"
                        :class="mode === 'youtube' ? 'border-red-500 text-red-600 dark:text-red-400' : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    >
                        <IconYoutube class="w-4 h-4" />
                        YouTube
                    </button>
                </div>

                <!-- URL Mode Content -->
                <div v-if="mode === 'url'" class="space-y-4">
                    <p class="text-sm text-gray-600 dark:text-gray-300">
                        Extract content from a website and save it as an artefact.
                    </p>

                    <div>
                        <label for="scrape-url" class="label">Target URL</label>
                        <div class="relative mt-1">
                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                <IconWeb class="h-4 w-4 text-gray-400" />
                            </div>
                            <input
                                id="scrape-url"
                                v-model="url"
                                type="url"
                                class="input-field pl-10"
                                placeholder="https://example.com/article"
                                @keyup.enter="handleSubmit"
                            />
                        </div>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label for="scrape-depth" class="label">Scraping Depth</label>
                            <input
                                id="scrape-depth"
                                v-model.number="depth"
                                type="number"
                                min="0"
                                max="5"
                                class="input-field mt-1"
                            />
                            <p class="text-[10px] text-gray-500 mt-1">0: This page only.</p>
                        </div>

                        <div class="flex flex-col justify-end pb-1">
                            <label class="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" v-model="processWithAi" class="sr-only peer">
                                <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                                <span class="ml-3 text-sm font-medium text-gray-700 dark:text-gray-300">AI Processing</span>
                            </label>
                        </div>
                    </div>
                </div>

                <!-- Wikipedia Mode Content -->
                <div v-if="mode === 'wikipedia'" class="space-y-4">
                    <p class="text-sm text-gray-600 dark:text-gray-300">
                        Search for a Wikipedia article to import.
                    </p>
                    
                    <div>
                        <label for="wiki-query" class="label">Search Query</label>
                        <div class="relative mt-1">
                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                <IconWikipedia class="h-4 w-4 text-gray-400" />
                            </div>
                            <input
                                id="wiki-query"
                                v-model="wikiQuery"
                                type="text"
                                class="input-field pl-10"
                                placeholder="e.g. Artificial Intelligence"
                                @keyup.enter="handleSubmit"
                            />
                        </div>
                    </div>
                </div>

                <!-- YouTube Mode Content -->
                <div v-if="mode === 'youtube'" class="space-y-4">
                    <p class="text-sm text-gray-600 dark:text-gray-300">
                        Extract transcript from a YouTube video.
                    </p>
                    
                    <div>
                        <label for="youtube-url" class="label">Video URL</label>
                        <div class="relative mt-1">
                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                <IconYoutube class="h-4 w-4 text-red-500" />
                            </div>
                            <input
                                id="youtube-url"
                                v-model="youtubeUrl"
                                type="url"
                                class="input-field pl-10"
                                placeholder="https://www.youtube.com/watch?v=..."
                                @keyup.enter="handleSubmit"
                            />
                        </div>
                    </div>

                    <!-- New Language Input -->
                    <div>
                        <label for="youtube-lang" class="label">Language Code (Optional)</label>
                        <input
                            id="youtube-lang"
                            v-model="youtubeLanguage"
                            type="text"
                            class="input-field mt-1"
                            placeholder="e.g. en, fr, es"
                            @keyup.enter="handleSubmit"
                        />
                        <p class="text-[10px] text-gray-500 mt-1">
                            Leave empty for auto-detect (English priority).
                        </p>
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('scrapeUrl')" type="button" class="btn btn-secondary">Cancel</button>
                <button @click="handleSubmit" type="button" class="btn btn-primary" 
                    :disabled="isLoading || (mode === 'url' && !url.trim()) || (mode === 'wikipedia' && !wikiQuery.trim()) || (mode === 'youtube' && !youtubeUrl.trim())">
                    <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
                    {{ isLoading ? 'Importing...' : 'Import' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>
