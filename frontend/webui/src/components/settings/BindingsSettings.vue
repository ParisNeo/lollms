<script setup>
import { computed } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import IconSelectMenu from '../ui/IconSelectMenu.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';

const authStore = useAuthStore();
const dataStore = useDataStore();

const user = computed(() => authStore.user);

const activeLlmModel = computed({
  get: () => user.value?.lollms_model_name,
  set: (name) => authStore.updateUserPreferences({ lollms_model_name: name })
});

const activeTtiModel = computed({
  get: () => user.value?.tti_binding_model_name,
  set: (name) => authStore.updateUserPreferences({ tti_binding_model_name: name })
});

const llmModels = computed(() => dataStore.availableLollmsModelsGrouped);
const ttiModels = computed(() => dataStore.availableTtiModelsGrouped);

function openModelCard(model) {
    uiStore.openModal('modelCard', { model });
}
</script>

<template>
    <div class="space-y-8">
        <div>
            <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                Model Bindings
            </h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Select your preferred models for different generation tasks. These will be your defaults across all discussions.
            </p>
        </div>

        <div class="space-y-6">
            <!-- Text Generation (LLM) Selector -->
            <div>
                <label class="block text-base font-medium mb-2">Text Generation (LLM)</label>
                <IconSelectMenu 
                    v-model="activeLlmModel" 
                    :items="llmModels"
                    :is-loading="dataStore.isLoadingLollmsModels"
                    placeholder="Select a Text Model"
                >
                    <template #button="{ toggle, selectedItem }">
                        <button @click="toggle" class="toolbox-select truncate w-full flex items-center justify-between">
                            <div class="flex items-center space-x-3 truncate">
                                <img v-if="selectedItem?.icon_base_64" :src="selectedItem.icon_base_64" class="h-8 w-8 rounded-md object-cover"/>
                                <span v-else class="w-8 h-8 flex-shrink-0 text-gray-500 dark:text-gray-400 flex items-center justify-center bg-gray-200 dark:bg-gray-700 rounded-md"><IconCpuChip class="w-5 h-5" /></span>
                                <div class="min-w-0 text-left">
                                    <span class="block font-semibold truncate">{{ selectedItem?.name || 'Select a Text Model' }}</span>
                                </div>
                            </div>
                            <svg class="w-4 h-4 text-gray-400 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                        </button>
                    </template>
                    <template #placeholder-icon><IconCpuChip class="w-5 h-5" /></template>
                    <template #item-icon-default><IconCpuChip class="w-5 h-5" /></template>
                </IconSelectMenu>
            </div>

            <!-- Image Generation (TTI) Selector -->
            <div>
                <label class="block text-base font-medium mb-2">Image Generation (TTI)</label>
                 <IconSelectMenu 
                    v-model="activeTtiModel" 
                    :items="ttiModels"
                    :is-loading="dataStore.isLoadingTtiModels"
                    placeholder="Select an Image Model"
                >
                    <template #button="{ toggle, selectedItem }">
                        <button @click="toggle" class="toolbox-select truncate w-full flex items-center justify-between">
                            <div class="flex items-center space-x-3 truncate">
                                <img v-if="selectedItem?.icon_base_64" :src="selectedItem.icon_base_64" class="h-8 w-8 rounded-md object-cover"/>
                                <span v-else class="w-8 h-8 flex-shrink-0 text-gray-500 dark:text-gray-400 flex items-center justify-center bg-gray-200 dark:bg-gray-700 rounded-md"><IconPhoto class="w-5 h-5" /></span>
                                <div class="min-w-0 text-left">
                                    <span class="block font-semibold truncate">{{ selectedItem?.name || 'Select an Image Model' }}</span>
                                </div>
                            </div>
                            <svg class="w-4 h-4 text-gray-400 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                        </button>
                    </template>
                    <template #placeholder-icon><IconPhoto class="w-5 h-5" /></template>
                    <template #item-icon-default><IconPhoto class="w-5 h-5" /></template>
                </IconSelectMenu>
            </div>

            <!-- Placeholder for future binding types -->
            <div class="p-4 text-center border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
                <p class="text-sm text-gray-500">More binding types like Text-to-Video and Text-to-Music will appear here when available.</p>
            </div>
        </div>
    </div>
</template>

<style scoped>
.toolbox-select {
    @apply w-full text-left text-sm px-2.5 py-1.5 bg-gray-50 dark:bg-gray-700/50 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500;
}
</style>