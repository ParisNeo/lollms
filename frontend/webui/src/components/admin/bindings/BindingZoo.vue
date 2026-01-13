<!-- frontend/webui/src/components/admin/bindings/BindingZoo.vue -->
<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useUiStore } from '../../../stores/ui';
import { useAdminStore } from '../../../stores/admin';
import { useTasksStore } from '../../../stores/tasks';
import { storeToRefs } from 'pinia';
import IconArrowDownTray from '../../../assets/icons/IconArrowDownTray.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';

const props = defineProps({
    binding: { type: Object, required: true },
    bindingType: { type: String, required: true } // 'llm', 'tti', 'tts', 'stt', 'ttv', 'ttm'
});

const uiStore = useUiStore();
const adminStore = useAdminStore();
const tasksStore = useTasksStore();
const { tasks } = storeToRefs(tasksStore);

const zooModels = ref([]);
const isLoadingZoo = ref(false);
const installingIndex = ref(null);
const searchTerm = ref('');

const filteredZooModels = computed(() => {
    if (!searchTerm.value) return zooModels.value;
    const term = searchTerm.value.toLowerCase();
    return zooModels.value.filter(m => m.name.toLowerCase().includes(term));
});

async function fetchZoo() {
    isLoadingZoo.value = true;
    try {
        let models = [];
        if (props.bindingType === 'llm') models = await adminStore.fetchBindingZoo(props.binding.id);
        else if (props.bindingType === 'tti') models = await adminStore.fetchTtiBindingZoo(props.binding.id);
        else if (props.bindingType === 'tts') models = await adminStore.fetchTtsBindingZoo(props.binding.id);
        else if (props.bindingType === 'stt') models = await adminStore.fetchSttBindingZoo(props.binding.id);
        else if (props.bindingType === 'ttv') models = await adminStore.fetchTtvBindingZoo(props.binding.id);
        else if (props.bindingType === 'ttm') models = await adminStore.fetchTtmBindingZoo(props.binding.id);
        
        zooModels.value = models || [];
    } catch (e) {
        console.error(e);
        uiStore.addNotification('Failed to fetch zoo models.', 'error');
    } finally {
        isLoadingZoo.value = false;
    }
}

async function installModel(model, index) {
    if (installingIndex.value !== null) return;
    installingIndex.value = index;
    try {
        let task;
        if (props.bindingType === 'llm') task = await adminStore.installLlmFromZoo(props.binding.id, index);
        else if (props.bindingType === 'tti') task = await adminStore.installTtiFromZoo(props.binding.id, index);
        else if (props.bindingType === 'tts') task = await adminStore.installTtsFromZoo(props.binding.id, index);
        else if (props.bindingType === 'stt') task = await adminStore.installSttFromZoo(props.binding.id, index);
        else if (props.bindingType === 'ttv') task = await adminStore.installTtvFromZoo(props.binding.id, index);
        else if (props.bindingType === 'ttm') task = await adminStore.installTtmFromZoo(props.binding.id, index);
        
        if (task) {
            uiStore.addNotification(`Installing ${model.name}...`, 'info');
        }
    } catch (e) {
        console.error(e);
        uiStore.addNotification('Installation failed to start.', 'error');
    } finally {
        installingIndex.value = null;
    }
}

onMounted(() => {
    fetchZoo();
});

watch(() => props.binding, () => {
    zooModels.value = [];
    fetchZoo();
});
</script>

<template>
    <div class="flex flex-col h-[600px]">
        <div class="mb-4 flex items-center justify-between">
            <h3 class="font-semibold text-lg">Models Zoo: {{ binding.alias }}</h3>
            <button @click="fetchZoo" class="text-blue-600 hover:underline text-sm" :disabled="isLoadingZoo">Refresh</button>
        </div>
        
        <div class="mb-4 relative">
             <input type="text" v-model="searchTerm" placeholder="Search zoo..." class="input-field w-full pl-8" />
             <div class="absolute inset-y-0 left-0 pl-2 flex items-center pointer-events-none text-gray-400">
                 <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
             </div>
        </div>

        <div v-if="isLoadingZoo" class="flex-grow flex items-center justify-center">
             <div class="text-center">
                <IconAnimateSpin class="w-8 h-8 text-blue-500 mx-auto mb-2" />
                <p>Loading zoo...</p>
            </div>
        </div>
        
        <div v-else-if="zooModels.length === 0" class="flex-grow flex items-center justify-center text-gray-500">
            No models found in zoo for this binding.
        </div>
        
        <div v-else class="flex-grow overflow-y-auto space-y-3 pr-2">
            <div v-for="(model, index) in filteredZooModels" :key="index" class="bg-white dark:bg-gray-700/50 p-4 rounded-lg border border-gray-200 dark:border-gray-600 flex flex-col sm:flex-row gap-4">
                <div class="flex-grow">
                    <h4 class="font-bold text-gray-900 dark:text-white">{{ model.name }}</h4>
                    <p class="text-sm text-gray-600 dark:text-gray-300 mt-1">{{ model.description }}</p>
                    <div class="flex flex-wrap gap-2 mt-2 text-xs text-gray-500 dark:text-gray-400">
                         <span v-if="model.size" class="bg-gray-100 dark:bg-gray-600 px-2 py-0.5 rounded">Size: {{ model.size }}</span>
                         <span v-if="model.type" class="bg-gray-100 dark:bg-gray-600 px-2 py-0.5 rounded">Type: {{ model.type }}</span>
                    </div>
                </div>
                <div class="flex-shrink-0 flex items-center">
                    <button 
                        @click="installModel(model, index)" 
                        class="btn btn-primary btn-sm flex items-center gap-2"
                        :disabled="installingIndex !== null"
                    >
                        <IconArrowDownTray class="w-4 h-4" />
                        Install
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>
