<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from './GenericModal.vue';
import IconWeb from '../../assets/icons/ui/IconWeb.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconWikipedia from '../../assets/icons/IconWikipedia.vue';
import IconYoutube from '../../assets/icons/IconYoutube.vue';
import IconServer from '../../assets/icons/IconServer.vue'; // Using for Arxiv
import apiClient from '../../services/api';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const modalData = computed(() => uiStore.modalData('scrapeUrl'));
const discussionId = computed(() => modalData.value?.discussionId);

const url = ref('');
const depth = ref(0);
const processWithAi = ref(false);
const isLoading = ref(false);
const mode = ref('url');
const youtubeUrl = ref('');
const youtubeLanguage = ref('en');

// Search Results state
const searchResults = ref([]);
const selectedIndices = ref(new Set());
const isSearching = ref(false);

// Wikipedia state
const wikiQuery = ref('');

// Arxiv state
const arxivQuery = ref('');
const arxivAuthor = ref('');
const arxivYear = ref(null);
const arxivMax = ref(5);
const arxivModes = ref({}); // Map of ID -> "abstract" or "full"

watch(() => uiStore.isModalOpen('scrapeUrl'), async (isOpen) => {
    if (isOpen) {
        url.value = '';
        depth.value = 0;
        processWithAi.value = false;
        wikiQuery.value = '';
        youtubeUrl.value = '';
        youtubeLanguage.value = 'en';
        searchResults.value = [];
        selectedIndices.value.clear();
        
        await nextTick();
        const data = uiStore.modalData('scrapeUrl');
        mode.value = data?.mode || 'url';
    }
});

async function handleSearch() {
    isSearching.value = true;
    searchResults.value = [];
    selectedIndices.value.clear();
    try {
        if (mode.value === 'wikipedia') {
            const resp = await apiClient.post(`/api/discussions/${discussionId.value}/artefacts/wikipedia/search`, { query: wikiQuery.value });
            searchResults.value = resp.data;
        } else if (mode.value === 'arxiv') {
            const resp = await apiClient.post(`/api/discussions/${discussionId.value}/artefacts/arxiv/search`, { 
                query: arxivQuery.value,
                author: arxivAuthor.value,
                year: arxivYear.value,
                max_results: arxivMax.value
            });
            searchResults.value = resp.data;
            // Initialize modes
            resp.data.forEach(r => arxivModes.value[r.id] = 'abstract');
        }
    } catch (e) {
        uiStore.addNotification("Search failed.", "error");
    } finally {
        isSearching.value = false;
    }
}

function toggleSelection(idx) {
    if (selectedIndices.value.has(idx)) selectedIndices.value.delete(idx);
    else selectedIndices.value.add(idx);
}

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
        if (selectedIndices.value.size === 0) return;
        isLoading.value = true;
        try {
            const items = Array.from(selectedIndices.value).map(idx => searchResults.value[idx]);
            await apiClient.post(`/api/discussions/${discussionId.value}/artefacts/wikipedia/import`, { items, auto_load: true });
            uiStore.addNotification("Articles imported.", "success");
            await discussionsStore.fetchArtefacts(discussionId.value);
            uiStore.closeModal('scrapeUrl');
        } finally {
            isLoading.value = false;
        }
    } else if (mode.value === 'arxiv') {
        if (selectedIndices.value.size === 0) return;
        isLoading.value = true;
        try {
            const items = Array.from(selectedIndices.value).map(idx => {
                const r = searchResults.value[idx];
                return { id: r.id, title: r.title, mode: arxivModes.value[r.id] };
            });
            await apiClient.post(`/api/discussions/${discussionId.value}/artefacts/arxiv/import`, { items, auto_load: true });
            uiStore.addNotification("Papers imported.", "success");
            await discussionsStore.fetchArtefacts(discussionId.value);
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
                    <button 
                        @click="mode = 'arxiv'"
                        class="flex-1 pb-2 text-sm font-medium text-center border-b-2 transition-colors flex items-center justify-center gap-2"
                        :class="mode === 'arxiv' ? 'border-orange-500 text-orange-600 dark:text-orange-400' : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    >
                        <IconServer class="w-4 h-4" />
                        Arxiv
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
                    <div class="flex gap-2">
                        <div class="relative flex-grow">
                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                <IconWikipedia class="h-4 w-4 text-gray-400" />
                            </div>
                            <input
                                v-model="wikiQuery"
                                type="text"
                                class="input-field pl-10"
                                placeholder="Article title or URL"
                                @keyup.enter="handleSearch"
                            />
                        </div>
                        <button @click="handleSearch" class="btn btn-secondary" :disabled="isSearching || !wikiQuery">
                            <IconAnimateSpin v-if="isSearching" class="w-4 h-4 animate-spin" />
                            <span v-else>Search</span>
                        </button>
                    </div>

                    <!-- Search Results -->
                    <div v-if="searchResults.length > 0" class="max-h-60 overflow-y-auto space-y-2 border rounded p-2 bg-gray-50 dark:bg-gray-900/50">
                        <div v-for="(res, idx) in searchResults" :key="idx" 
                             @click="toggleSelection(idx)"
                             class="p-2 border rounded cursor-pointer transition-colors"
                             :class="selectedIndices.has(idx) ? 'bg-blue-50 border-blue-500 dark:bg-blue-900/30' : 'bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-750'">
                            <div class="flex items-center gap-2">
                                <input type="checkbox" :checked="selectedIndices.has(idx)" class="rounded text-blue-600">
                                <span class="font-bold text-sm">{{ res.title }}</span>
                            </div>
                            <p class="text-[10px] text-gray-500 line-clamp-1 mt-1">{{ res.snippet }}</p>
                        </div>
                    </div>
                </div>

                <!-- Arxiv Mode Content -->
                <div v-if="mode === 'arxiv'" class="space-y-4">
                    <div class="grid grid-cols-2 gap-2">
                        <div class="col-span-2">
                            <label class="text-[10px] font-bold uppercase text-gray-400">Search Query</label>
                            <input v-model="arxivQuery" type="text" class="input-field" placeholder="Topic keywords...">
                        </div>
                        <div>
                            <label class="text-[10px] font-bold uppercase text-gray-400">Author</label>
                            <input v-model="arxivAuthor" type="text" class="input-field" placeholder="Einstein">
                        </div>
                        <div>
                            <label class="text-[10px] font-bold uppercase text-gray-400">Year</label>
                            <input v-model.number="arxivYear" type="number" class="input-field" placeholder="2024">
                        </div>
                    </div>
                    <div class="flex justify-between items-center">
                         <div class="flex items-center gap-2">
                             <label class="text-xs">Count:</label>
                             <input v-model.number="arxivMax" type="number" class="input-field !w-16" min="1" max="50">
                         </div>
                         <button @click="handleSearch" class="btn btn-primary" :disabled="isSearching || (!arxivQuery && !arxivAuthor)">
                            <IconAnimateSpin v-if="isSearching" class="w-4 h-4 animate-spin mr-2" />
                            Search Arxiv
                        </button>
                    </div>

                    <!-- Arxiv Results -->
                    <div v-if="searchResults.length > 0" class="max-h-60 overflow-y-auto space-y-2 border rounded p-2 bg-gray-50 dark:bg-gray-900/50">
                        <div v-for="(res, idx) in searchResults" :key="idx" 
                             class="p-2 border rounded bg-white dark:bg-gray-800"
                             :class="selectedIndices.has(idx) ? 'border-orange-500' : 'dark:border-gray-700'">
                            <div class="flex items-start gap-2">
                                <input type="checkbox" :checked="selectedIndices.has(idx)" @change="toggleSelection(idx)" class="mt-1 rounded text-orange-600">
                                <div class="flex-grow min-w-0">
                                    <div class="font-bold text-xs truncate" :title="res.title">{{ res.title }}</div>
                                    <div class="text-[9px] text-gray-500">{{ res.authors.join(', ') }} ({{ res.year }})</div>
                                    
                                    <!-- Mode Toggle -->
                                    <div class="mt-2 flex gap-1 bg-gray-100 dark:bg-gray-900 p-0.5 rounded-lg w-fit">
                                        <button @click="arxivModes[res.id] = 'abstract'" 
                                                class="px-2 py-0.5 text-[9px] font-bold rounded transition-all"
                                                :class="arxivModes[res.id] === 'abstract' ? 'bg-white dark:bg-gray-700 shadow-sm text-orange-600' : 'text-gray-400'">
                                            Abstract
                                        </button>
                                        <button @click="arxivModes[res.id] = 'full'" 
                                                class="px-2 py-0.5 text-[9px] font-bold rounded transition-all"
                                                :class="arxivModes[res.id] === 'full' ? 'bg-white dark:bg-gray-700 shadow-sm text-orange-600' : 'text-gray-400'">
                                            Full Text
                                        </button>
                                    </div>
                                </div>
                            </div>
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

                    <!-- Language Selection -->
                    <div>
                        <label for="youtube-lang" class="label">Transcript Language</label>
                        <select
                            id="youtube-lang"
                            v-model="youtubeLanguage"
                            class="input-field mt-1"
                        >
                            <option v-for="lang in commonLanguages" :key="lang.value" :value="lang.value">
                                {{ lang.label }} ({{ lang.value }})
                            </option>
                        </select>
                        <p class="text-[10px] text-gray-500 mt-1">
                            The system will try to find this language or translate the original captions to it.
                        </p>
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('scrapeUrl')" type="button" class="btn btn-secondary">Cancel</button>
                
                <!-- Conditionally show Select Count -->
                <span v-if="(mode === 'wikipedia' || mode === 'arxiv') && selectedIndices.size > 0" class="text-xs text-gray-500 self-center">
                    {{ selectedIndices.size }} selected
                </span>

                <button @click="handleSubmit" type="button" class="btn btn-primary" 
                    :disabled="isLoading || 
                              (mode === 'url' && !url.trim()) || 
                              (mode === 'wikipedia' && selectedIndices.size === 0) || 
                              (mode === 'arxiv' && selectedIndices.size === 0) ||
                              (mode === 'youtube' && !youtubeUrl.trim())">
                    <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
                    {{ isLoading ? 'Importing...' : 'Import' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>
