<script setup>
import { ref, computed, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import GenericModal from './GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import { useDataStore } from '../../stores/data';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconDatabase from '../../assets/icons/IconDatabase.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();
const dataStore = useDataStore();

const { funFactCategories } = storeToRefs(adminStore);
const { ownedDataStores, sharedDataStores } = storeToRefs(dataStore);

const modalData = computed(() => uiStore.modalData('generateFunFacts'));
const preselectedCategoryId = computed(() => modalData.value?.categoryId);
const initialNFacts = computed(() => modalData.value?.nFacts || 5);

const allDataStores = computed(() => [...ownedDataStores.value, ...sharedDataStores.value]);

const activeTab = ref('topic'); // topic, wikipedia, text, url, search, datastore

const form = ref({
    topic: '',
    text: '',
    url: '',
    searchQuery: '',
    datastoreId: '',
    datastoreQuery: '',
    wikiInput: '',
    
    categoryId: '',
    newCategoryName: '',
    nFacts: 5
});

const isGenerating = ref(false);

const currentCategoryName = computed(() => {
    if (form.value.categoryId === 'new') return form.value.newCategoryName;
    const cat = funFactCategories.value.find(c => c.id === form.value.categoryId);
    return cat ? cat.name : null;
});

onMounted(() => {
    if (dataStore.ownedDataStores.length === 0) {
        dataStore.fetchDataStores();
    }
    // Initialize form with passed data
    form.value.nFacts = initialNFacts.value;
    if (preselectedCategoryId.value) {
        form.value.categoryId = preselectedCategoryId.value;
    }
});

async function handleSubmit() {
    // Validation
    let content = '';
    let sourceType = activeTab.value;

    if (sourceType === 'topic') {
        if (!form.value.topic.trim()) { uiStore.addNotification('Topic is required.', 'warning'); return; }
        content = form.value.topic;
    } else if (sourceType === 'wikipedia') {
        if (!form.value.wikiInput.trim()) { uiStore.addNotification('Wikipedia Topic or URL is required.', 'warning'); return; }
        content = form.value.wikiInput;
    } else if (sourceType === 'text') {
        if (!form.value.text.trim()) { uiStore.addNotification('Text content is required.', 'warning'); return; }
        content = form.value.text;
    } else if (sourceType === 'url') {
        if (!form.value.url.trim()) { uiStore.addNotification('URL is required.', 'warning'); return; }
        content = form.value.url;
    } else if (sourceType === 'search') {
        if (!form.value.searchQuery.trim()) { uiStore.addNotification('Search query is required.', 'warning'); return; }
        content = form.value.searchQuery;
    } else if (sourceType === 'datastore') {
        if (!form.value.datastoreId) { uiStore.addNotification('Please select a DataStore.', 'warning'); return; }
        if (!form.value.datastoreQuery.trim()) { uiStore.addNotification('Query/Topic for DataStore is required.', 'warning'); return; }
        content = form.value.datastoreQuery;
    }

    const category = currentCategoryName.value; 

    isGenerating.value = true;
    try {
        const payload = {
            source_type: sourceType,
            content: content,
            category: category,
            n_facts: form.value.nFacts,
            datastore_id: form.value.datastoreId || null
        };
        
        await adminStore.generateFunFacts(payload); 

        uiStore.addNotification('Generation task started. Check Tasks for progress.', 'success');
        uiStore.closeModal('generateFunFacts');
    } catch (e) {
        console.error(e);
        uiStore.addNotification('Failed to start generation.', 'error');
    } finally {
        isGenerating.value = false;
    }
}
</script>

<template>
    <GenericModal modal-name="generateFunFacts" title="AI Fun Fact Generator" max-width-class="max-w-3xl">
        <template #body>
            <div class="space-y-6">
                <!-- Source Tabs -->
                <div class="border-b border-gray-200 dark:border-gray-700">
                    <nav class="-mb-px flex space-x-4 overflow-x-auto" aria-label="Tabs">
                        <button @click="activeTab = 'topic'" :class="[activeTab === 'topic' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap']">
                            <IconSparkles class="mr-2 h-5 w-5" /> Topic
                        </button>
                        <button @click="activeTab = 'wikipedia'" :class="[activeTab === 'wikipedia' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap']">
                            <IconBookOpen class="mr-2 h-5 w-5" /> Wikipedia
                        </button>
                        <button @click="activeTab = 'text'" :class="[activeTab === 'text' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap']">
                            <IconFileText class="mr-2 h-5 w-5" /> Raw Text
                        </button>
                        <button @click="activeTab = 'url'" :class="[activeTab === 'url' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap']">
                            <IconGlobeAlt class="mr-2 h-5 w-5" /> Web Page
                        </button>
                        <button @click="activeTab = 'search'" :class="[activeTab === 'search' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap']">
                            <IconMagnifyingGlass class="mr-2 h-5 w-5" /> Web Search
                        </button>
                        <button @click="activeTab = 'datastore'" :class="[activeTab === 'datastore' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap']">
                            <IconDatabase class="mr-2 h-5 w-5" /> DataStore
                        </button>
                    </nav>
                </div>

                <!-- Input Fields based on Tab -->
                <div class="mt-4">
                    <div v-if="activeTab === 'topic'">
                        <label class="block text-sm font-medium mb-1">Topic</label>
                        <input type="text" v-model="form.topic" class="input-field w-full" placeholder="e.g. Quantum Physics, Cats, The Moon">
                        <p class="text-xs text-gray-500 mt-1">The AI will use its internal knowledge to generate facts about this topic.</p>
                    </div>

                    <div v-if="activeTab === 'wikipedia'">
                        <label class="block text-sm font-medium mb-1">Wikipedia Topic or URL</label>
                        <input type="text" v-model="form.wikiInput" class="input-field w-full" placeholder="e.g. Marie Curie or https://en.wikipedia.org/wiki/Marie_Curie">
                        <p class="text-xs text-gray-500 mt-1">
                            Provide a specific topic title or a full Wikipedia URL. The system will retrieve the page content.
                            Supports multiple languages via URL (e.g. fr.wikipedia.org).
                        </p>
                    </div>

                    <div v-if="activeTab === 'text'">
                        <label class="block text-sm font-medium mb-1">Source Text</label>
                        <textarea v-model="form.text" rows="5" class="input-field w-full" placeholder="Paste article or text content here..."></textarea>
                        <p class="text-xs text-gray-500 mt-1">Facts will be extracted solely from this text.</p>
                    </div>

                    <div v-if="activeTab === 'url'">
                        <label class="block text-sm font-medium mb-1">URL</label>
                        <input type="url" v-model="form.url" class="input-field w-full" placeholder="https://example.com/article">
                        <p class="text-xs text-gray-500 mt-1">The system will scrape this page and extract facts.</p>
                    </div>

                    <div v-if="activeTab === 'search'">
                        <label class="block text-sm font-medium mb-1">Search Query</label>
                        <input type="text" v-model="form.searchQuery" class="input-field w-full" placeholder="e.g. Latest space discoveries 2024">
                        <p class="text-xs text-gray-500 mt-1">The system will perform a web search and generate facts from the top results.</p>
                    </div>

                    <div v-if="activeTab === 'datastore'">
                        <label class="block text-sm font-medium mb-1">Select DataStore</label>
                        <select v-model="form.datastoreId" class="input-field w-full mb-3">
                            <option value="" disabled>-- Select --</option>
                            <option v-for="ds in allDataStores" :key="ds.id" :value="ds.id">{{ ds.name }}</option>
                        </select>
                        <label class="block text-sm font-medium mb-1">Topic/Query</label>
                        <input type="text" v-model="form.datastoreQuery" class="input-field w-full" placeholder="e.g. Company History, Project X details">
                        <p class="text-xs text-gray-500 mt-1">The AI will retrieve relevant chunks from the selected DataStore to generate facts.</p>
                    </div>
                </div>

                <!-- Common Settings -->
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 border-t dark:border-gray-700 pt-4">
                    <div>
                        <label class="block text-sm font-medium mb-1">Target Category</label>
                        <select v-model="form.categoryId" class="input-field w-full">
                            <option value="">-- Auto-Detect / General --</option>
                            <option value="new">+ Create New Category</option>
                            <option v-for="cat in funFactCategories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
                        </select>
                        <div v-if="form.categoryId === 'new'" class="mt-2">
                            <input type="text" v-model="form.newCategoryName" class="input-field w-full" placeholder="New Category Name">
                        </div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-1">Number of Facts</label>
                        <input type="number" v-model.number="form.nFacts" min="1" max="20" class="input-field w-full">
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('generateFunFacts')" class="btn btn-secondary">Cancel</button>
                <button @click="handleSubmit" class="btn btn-primary" :disabled="isGenerating">
                    {{ isGenerating ? 'Starting Task...' : 'Generate Facts' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>
