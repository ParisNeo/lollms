<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from './GenericModal.vue';
import IconWeb from '../../assets/icons/ui/IconWeb.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const modalData = computed(() => uiStore.modalData('scrapeUrl'));
const discussionId = computed(() => modalData.value?.discussionId);

const url = ref('');
const depth = ref(0);
const processWithAi = ref(false);
const isLoading = ref(false);

watch(() => uiStore.isModalOpen('scrapeUrl'), (isOpen) => {
    if (isOpen) {
        url.value = '';
        depth.value = 0;
        processWithAi.value = false;
    }
});

async function handleSubmit() {
    if (!url.value.trim()) {
        uiStore.addNotification('URL is required.', 'warning');
        return;
    }
    if (!discussionId.value) return;

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
}
</script>

<template>
    <GenericModal
        modalName="scrapeUrl"
        title="Scrape URL to Workspace"
        maxWidthClass="max-w-lg"
    >
        <template #body>
            <div class="space-y-4 p-1">
                <p class="text-sm text-gray-600 dark:text-gray-300">
                    Extract content from a website and save it as an artefact in your discussion.
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
                            required
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
                        <p class="text-[10px] text-gray-500 mt-1">
                            0: This page only. <br>
                            1+: Follow internal links.
                        </p>
                    </div>

                    <div class="flex flex-col justify-end pb-1">
                        <label class="relative inline-flex items-center cursor-pointer">
                            <input type="checkbox" v-model="processWithAi" class="sr-only peer">
                            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                            <span class="ml-3 text-sm font-medium text-gray-700 dark:text-gray-300">AI Processing</span>
                        </label>
                        <p class="text-[10px] text-gray-500 mt-1">Clean boilerplate & structure content.</p>
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('scrapeUrl')" type="button" class="btn btn-secondary">Cancel</button>
                <button @click="handleSubmit" type="button" class="btn btn-primary" :disabled="isLoading || !url.trim()">
                    <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
                    {{ isLoading ? 'Starting...' : 'Scrape & Import' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>
