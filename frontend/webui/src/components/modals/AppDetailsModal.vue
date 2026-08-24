<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import IconTag from '../../assets/icons/IconTag.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue';

const uiStore = useUiStore();
const props = computed(() => uiStore.modalData('appDetails'));
const app = computed(() => props.value?.app);

const details = computed(() => {
    if (!app.value) return [];
    return [
        { label: 'Author', value: app.value.author },
        { label: 'Version', value: app.value.version ? `v${app.value.version}` : null },
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
});
</script>

<template>
    <GenericModal
        modal-name="appDetails"
        :title="app ? app.name : 'App Details'"
        max-width-class="max-w-2xl"
    >
        <template #body>
            <div v-if="app" class="space-y-5">
                <!-- Hero Header -->
                <div class="flex items-start gap-4 p-4 rounded-2xl bg-gray-50/80 dark:bg-gray-800/60 border border-gray-200/80 dark:border-gray-700/60">
                    <img 
                        v-if="app.icon" 
                        :src="app.icon" 
                        class="h-16 w-16 rounded-2xl object-cover bg-white dark:bg-gray-700 p-1 border border-gray-200 dark:border-gray-600 shrink-0 shadow-inner" 
                        alt="App Icon"
                    >
                    <div class="grow min-w-0">
                        <div class="flex items-center gap-2 flex-wrap">
                            <h3 class="text-base font-bold text-gray-900 dark:text-white">{{ app.name }}</h3>
                            <span v-if="app.category" class="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300">
                                {{ app.category }}
                            </span>
                            <span v-if="app.version" class="px-2 py-0.5 rounded-md text-[10px] font-mono bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
                                v{{ app.version }}
                            </span>
                        </div>
                        <p class="text-xs text-gray-600 dark:text-gray-300 mt-1.5 leading-relaxed">{{ app.description }}</p>
                    </div>
                </div>

                <!-- Tags Area -->
                <div v-if="app.tags && app.tags.length" class="flex flex-wrap gap-1.5">
                    <span 
                        v-for="tag in app.tags" 
                        :key="tag" 
                        class="inline-flex items-center px-2.5 py-1 rounded-lg text-[11px] font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200/60 dark:border-gray-700"
                    >
                        <IconTag class="w-3 h-3 mr-1 text-gray-400" />
                        {{ tag }}
                    </span>
                </div>
                
                <!-- Details Grid -->
                <div v-if="details.length" class="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4 rounded-2xl bg-white dark:bg-gray-800/40 border border-gray-200/80 dark:border-gray-700/60 text-xs">
                    <div v-for="detail in details" :key="detail.label" class="flex items-center justify-between py-1 border-b border-gray-100 dark:border-gray-750 last:border-0">
                        <span class="font-semibold text-gray-500 dark:text-gray-400">{{ detail.label }}:</span>
                        <span class="font-medium text-gray-900 dark:text-gray-200 truncate pl-2" :title="detail.value">{{ detail.value }}</span>
                    </div>
                </div>

                <!-- Features Section -->
                <div v-if="app.features && app.features.length" class="space-y-2 p-4 rounded-2xl bg-gray-50 dark:bg-gray-800/30 border border-gray-200/80 dark:border-gray-700/60">
                    <h4 class="font-bold text-xs uppercase tracking-wider text-gray-700 dark:text-gray-300">Key Features</h4>
                    <ul class="space-y-1 text-xs text-gray-600 dark:text-gray-300">
                        <li v-for="(feature, index) in app.features" :key="index" class="flex items-start gap-2">
                            <span class="text-blue-500 font-bold">•</span>
                            <span>{{ feature }}</span>
                        </li>
                    </ul>
                </div>

                <!-- Documentation Links -->
                <div v-if="links.length" class="space-y-2">
                    <h4 class="font-bold text-xs uppercase tracking-wider text-gray-700 dark:text-gray-300">External Links</h4>
                    <div class="flex flex-wrap gap-2">
                        <a 
                            v-for="link in links" 
                            :key="link.label" 
                            :href="link.value" 
                            target="_blank" 
                            rel="noopener noreferrer" 
                            class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors border border-blue-200/60 dark:border-blue-800/40"
                        >
                            <IconGlobeAlt class="w-3.5 h-3.5" />
                            {{ link.label }}
                        </a>
                    </div>
                </div>

                <!-- Disclaimer -->
                <div v-if="app.disclaimer" class="p-3.5 bg-amber-50 dark:bg-amber-950/30 border border-amber-300/60 dark:border-amber-700/40 rounded-xl text-amber-800 dark:text-amber-300 text-xs leading-relaxed">
                    <p><strong class="font-bold">Disclaimer:</strong> {{ app.disclaimer }}</p>
                </div>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('appDetails')" class="btn btn-secondary btn-sm">Close</button>
        </template>
    </GenericModal>
</template>