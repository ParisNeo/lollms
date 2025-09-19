<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import IconTag from '../../assets/icons/IconTag.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';

const uiStore = useUiStore();
const props = computed(() => uiStore.modalData('appDetails'));
const app = computed(() => props.value?.app);

const details = computed(() => {
    if (!app.value) return [];
    return [
        { label: 'Author', value: app.value.author },
        { label: 'Version', value: app.value.version },
        { label: 'Category', value: app.value.category },
        { label: 'Creation Date', value: app.value.creation_date },
        { label: 'Last Updated', value: app.value.last_update_date },
        { label: 'License', value: app.value.license },
        { label: 'Model', value: app.value.model },
    ].filter(item => item.value);
});

const links = computed(() => {
    if (!app.value) return [];
    return [
        { label: 'Repository', value: app.value.repo_url },
        { label: 'Documentation', value: app.value.documentation },
    ].filter(item => item.value);
})
</script>

<template>
    <GenericModal
        modal-name="appDetails"
        :title="app ? app.name : 'App Details'"
        max-width-class="max-w-2xl"
    >
        <template #body>
            <div v-if="app" class="space-y-6">
                <div class="flex items-start gap-4">
                    <img v-if="app.icon" :src="app.icon" class="h-20 w-20 rounded-lg object-cover flex-shrink-0" alt="App Icon">
                    <div class="flex-grow">
                        <p class="text-lg text-gray-600 dark:text-gray-300">{{ app.description }}</p>
                    </div>
                </div>

                <div v-if="app.tags && app.tags.length" class="flex flex-wrap gap-2">
                    <span v-for="tag in app.tags" :key="tag" class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300">
                        <IconTag class="w-3 h-3 mr-1.5" />
                        {{ tag }}
                    </span>
                </div>
                
                <div v-if="details.length" class="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
                    <div v-for="detail in details" :key="detail.label" class="flex">
                        <span class="font-semibold w-28 flex-shrink-0 text-gray-800 dark:text-gray-200">{{ detail.label }}:</span>
                        <span class="text-gray-600 dark:text-gray-400 truncate" :title="detail.value">{{ detail.value }}</span>
                    </div>
                </div>

                <div v-if="links.length" class="space-y-2">
                     <h4 class="font-semibold text-gray-800 dark:text-gray-200">Links</h4>
                    <ul class="list-disc list-inside text-sm space-y-1">
                        <li v-for="link in links" :key="link.label">
                           <a :href="link.value" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:underline dark:text-blue-400">
                                {{ link.label }}
                            </a>
                        </li>
                    </ul>
                </div>
                
                <div v-if="app.features && app.features.length" class="space-y-2">
                    <h4 class="font-semibold text-gray-800 dark:text-gray-200">Features</h4>
                    <ul class="list-disc list-inside text-sm space-y-1 text-gray-600 dark:text-gray-400">
                        <li v-for="(feature, index) in app.features" :key="index">{{ feature }}</li>
                    </ul>
                </div>

                <div v-if="app.disclaimer" class="p-3 bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-400 text-yellow-800 dark:text-yellow-300 text-sm">
                     <p><strong class="font-semibold">Disclaimer:</strong> {{ app.disclaimer }}</p>
                </div>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('appDetails')" class="btn btn-primary">Close</button>
        </template>
    </GenericModal>
</template>