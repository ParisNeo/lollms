<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import { useDataStore } from '../../stores/data';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import GenericModal from './GenericModal.vue';
import IconDatabase from '../../assets/icons/IconDatabase.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();
const dataStore = useDataStore();
const tasksStore = useTasksStore();

const { availableVectorizers } = storeToRefs(dataStore);
const modalProps = computed(() => uiStore.modalProps.createDataStoreFromArtefacts || {});

const mode = ref('create'); // 'create' or 'existing'
const selectedStoreId = ref('');
const storeName = ref('');
const storeDescription = ref('');
const selectedVectorizerKey = ref(null);
const CHUNKING_STRATEGIES = [
    { value: 'recursive', label: 'Recursive Tree (Recommended)' },
    { value: 'structure', label: 'Structure-Aware (Markdown headers)' },
    { value: 'token', label: 'Token Window' },
    { value: 'semantic', label: 'Semantic Valley (Topic shift)' },
    { value: 'contextual', label: 'Contextual Retrieval (Anthropic)' },
    { value: 'late', label: 'Late Chunking (Jina AI)' },
    { value: 'paragraph', label: 'Paragraph Blocks' },
    { value: 'character', label: 'Fixed Character' }
];

const chunkingStrategy = ref('recursive');
const chunkSize = ref(2048);
const chunkOverlap = ref(256);
const linkToDiscussion = ref(true);

const isSubmitting = ref(false);
const activeTaskId = ref(null);

const titles = computed(() => modalProps.value.titles || (modalProps.value.title ? [modalProps.value.title] : []));
const discussionId = computed(() => modalProps.value.discussionId || discussionsStore.currentDiscussionId);

const vectorizerOptions = computed(() => availableVectorizers.value);

const selectedVectorizerDetails = computed(() => {
    if (!selectedVectorizerKey.value) return null;
    const parts = selectedVectorizerKey.value.split('/');
    if (parts.length < 2) return null;
    const bindingAlias = parts[0];
    const modelValue = parts.slice(1).join('/');
    const foundBinding = vectorizerOptions.value.find(group => group.alias === bindingAlias);
    if (foundBinding) {
        return {
            ...foundBinding,
            selectedModelName: modelValue
        };
    }
    return null;
});

const currentTask = computed(() => {
    if (!activeTaskId.value) return null;
    return tasksStore.tasks.find(t => t.id === activeTaskId.value);
});

onMounted(async () => {
    if (dataStore.availableVectorizers.length === 0) {
        await dataStore.fetchAvailableVectorizers();
    }
    if (dataStore.ownedDataStores.length === 0) {
        await dataStore.fetchDataStores();
    }
    if (vectorizerOptions.value.length > 0 && !selectedVectorizerKey.value) {
        const first = vectorizerOptions.value[0];
        if (first.models && first.models.length > 0) {
            selectedVectorizerKey.value = `${first.alias}/${first.models[0].value}`;
        }
    }
});

watch(() => uiStore.isModalOpen('createDataStoreFromArtefacts'), (isOpen) => {
    if (isOpen) {
        mode.value = modalProps.value.initialMode || 'create';
        selectedStoreId.value = modalProps.value.targetDatastoreId || (dataStore.ownedDataStores[0]?.id || '');
        storeName.value = modalProps.value.defaultName || (titles.value.length === 1 ? `${titles.value[0].replace(/\.[^/.]+$/, '')} KB` : 'New Knowledge Base');
        storeDescription.value = '';
        isSubmitting.value = false;
        activeTaskId.value = null;
    }
});

async function handleSubmit() {
    if (!discussionId.value) return;

    isSubmitting.value = true;
    try {
        if (mode.value === 'existing') {
            if (!selectedStoreId.value) {
                uiStore.addNotification('Please select a DataStore.', 'warning');
                isSubmitting.value = false;
                return;
            }
            const task = await discussionsStore.batchSendArtefactsToDataStore({
                discussionId: discussionId.value,
                artefactTitles: titles.value,
                datastoreId: selectedStoreId.value
            });
            if (task?.id) {
                activeTaskId.value = task.id;
            }
        } else {
            if (!storeName.value.trim()) {
                uiStore.addNotification('DataStore name is required.', 'warning');
                isSubmitting.value = false;
                return;
            }

            const vecConfig = selectedVectorizerDetails.value?.vectorizer_config ? { ...selectedVectorizerDetails.value.vectorizer_config } : {};
            if (selectedVectorizerDetails.value?.selectedModelName) {
                vecConfig['model_name'] = selectedVectorizerDetails.value.selectedModelName;
            }

            const res = await discussionsStore.createDataStoreFromArtefacts({
                discussionId: discussionId.value,
                name: storeName.value.trim(),
                description: storeDescription.value.trim(),
                vectorizerName: selectedVectorizerDetails.value?.vectorizer_name || 'st',
                vectorizerConfig: vecConfig,
                chunkSize: chunkSize.value,
                chunkOverlap: chunkOverlap.value,
                chunkingStrategy: chunkingStrategy.value,
                chunkingKwargs: {},
                artefactTitles: titles.value,
                linkToDiscussion: linkToDiscussion.value
            });

            if (res?.task_id) {
                activeTaskId.value = res.task_id;
            } else {
                uiStore.closeModal('createDataStoreFromArtefacts');
            }
        }
    } catch (e) {
        isSubmitting.value = false;
    }
}
</script>

<template>
    <GenericModal modalName="createDataStoreFromArtefacts" :title="mode === 'create' ? 'Create DataStore & Vectorize' : 'Vectorize into Existing DataStore'" maxWidthClass="max-w-xl">
        <template #body>
            <div class="space-y-6 p-1">
                <!-- Task Progress State -->
                <div v-if="currentTask" class="p-6 rounded-2xl bg-blue-50/70 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-center space-y-4 animate-in fade-in">
                    <div class="flex items-center justify-center">
                        <IconAnimateSpin v-if="currentTask.status === 'running' || currentTask.status === 'pending'" class="w-10 h-10 text-blue-600 animate-spin" />
                        <IconCheckCircle v-else class="w-10 h-10 text-green-500" />
                    </div>
                    <div>
                        <h4 class="font-bold text-sm text-gray-900 dark:text-white">{{ currentTask.name }}</h4>
                        <p class="text-xs text-gray-500 mt-1">{{ currentTask.description || 'Processing document chunks...' }}</p>
                    </div>
                    <!-- Progress Bar -->
                    <div class="w-full bg-gray-200 dark:bg-gray-700 h-2.5 rounded-full overflow-hidden shadow-inner">
                        <div class="bg-blue-600 h-full transition-all duration-300 rounded-full" :style="{ width: `${currentTask.progress || 10}%` }"></div>
                    </div>
                    <span class="text-xs font-mono font-bold text-blue-600 dark:text-blue-400">{{ currentTask.progress }}%</span>
                </div>

                <!-- Form Configuration State -->
                <div v-else class="space-y-5">
                    <!-- Target Items Summary Banner -->
                    <div class="p-3 bg-gray-50 dark:bg-gray-800/60 rounded-xl border dark:border-gray-700/80 flex items-center justify-between text-xs">
                        <span class="font-semibold text-gray-600 dark:text-gray-300">Selected for Vectorization:</span>
                        <span class="font-bold font-mono px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">
                            {{ titles.length }} document{{ titles.length > 1 ? 's' : '' }}
                        </span>
                    </div>

                    <!-- Mode Toggle -->
                    <div class="flex p-1 bg-gray-100 dark:bg-gray-800 rounded-xl">
                        <button type="button" @click="mode = 'create'" class="flex-1 py-1.5 text-xs font-bold rounded-lg transition-all" :class="mode === 'create' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500'">
                            + New DataStore
                        </button>
                        <button type="button" @click="mode = 'existing'" class="flex-1 py-1.5 text-xs font-bold rounded-lg transition-all" :class="mode === 'existing' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500'">
                            Existing DataStore
                        </button>
                    </div>

                    <!-- Mode: Existing DataStore -->
                    <div v-if="mode === 'existing'" class="space-y-4">
                        <div>
                            <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Target Knowledge Base</label>
                            <select v-model="selectedStoreId" class="input-field text-xs">
                                <option v-for="ds in dataStore.ownedDataStores" :key="ds.id" :value="ds.id">
                                    {{ ds.name }} ({{ ds.vectorizer_name }})
                                </option>
                            </select>
                        </div>
                    </div>

                    <!-- Mode: Create New DataStore -->
                    <div v-else class="space-y-4">
                        <div>
                            <label class="block text-xs font-bold uppercase text-gray-500 mb-1">DataStore Name *</label>
                            <input v-model="storeName" type="text" class="input-field text-xs" placeholder="e.g. Project Specs RAG" required />
                        </div>

                        <div>
                            <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Description (Optional)</label>
                            <textarea v-model="storeDescription" rows="2" class="input-field text-xs" placeholder="Knowledge domain details..."></textarea>
                        </div>

                        <div>
                            <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Embedding Vectorizer</label>
                            <select v-model="selectedVectorizerKey" class="input-field text-xs">
                                <optgroup v-for="group in vectorizerOptions" :key="group.id" :label="group.alias || group.vectorizer_name">
                                    <option v-for="model in group.models" :key="`${group.id}-${model.value}`" :value="`${group.alias}/${model.value}`">
                                        {{ model.name }}
                                    </option>
                                </optgroup>
                            </select>
                        </div>

                        <div>
                            <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Chunking Strategy</label>
                            <select v-model="chunkingStrategy" class="input-field text-xs">
                                <option v-for="strat in CHUNKING_STRATEGIES" :key="strat.value" :value="strat.value">
                                    {{ strat.label }}
                                </option>
                            </select>
                        </div>

                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Chunk Size</label>
                                <input v-model.number="chunkSize" type="number" min="100" max="16000" class="input-field text-xs" />
                            </div>
                            <div>
                                <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Overlap</label>
                                <input v-model.number="chunkOverlap" type="number" min="0" max="4000" class="input-field text-xs" />
                            </div>
                        </div>

                        <label class="flex items-center gap-2 cursor-pointer pt-2">
                            <input type="checkbox" v-model="linkToDiscussion" class="rounded text-blue-600" />
                            <span class="text-xs font-bold text-gray-700 dark:text-gray-300">Auto-link to current discussion</span>
                        </label>
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end gap-2 w-full">
                <button type="button" @click="uiStore.closeModal('createDataStoreFromArtefacts')" class="btn btn-secondary" :disabled="isSubmitting && !!currentTask && currentTask.status === 'running'">
                    {{ currentTask && currentTask.status === 'completed' ? 'Close' : 'Cancel' }}
                </button>
                <button v-if="!currentTask || currentTask.status !== 'completed'" type="button" @click="handleSubmit" class="btn btn-primary" :disabled="isSubmitting">
                    <IconAnimateSpin v-if="isSubmitting" class="w-4 h-4 mr-2 animate-spin" />
                    <span>{{ mode === 'create' ? 'Create & Vectorize' : 'Vectorize into Store' }}</span>
                </button>
            </div>
        </template>
    </GenericModal>
</template>

<style scoped>
@reference "tailwindcss";
</style>