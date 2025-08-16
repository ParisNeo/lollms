<script setup>
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import SimpleSelectMenu from '../ui/SimpleSelectMenu.vue';

const authStore = useAuthStore();
const dataStore = useDataStore();
const uiStore = useUiStore();

const selectedTtiBindingId = ref(authStore.user?.active_tti_id || null);

const availableTtiBindings = computed(() => {
    return dataStore.availableTtiBindings.map(binding => ({
        id: binding.id,
        name: binding.alias,
        description: binding.name
    }));
});

onMounted(() => {
    dataStore.fetchAvailableTtiBindings();
});

async function handleSave() {
    await authStore.updateUserPreferences({ active_tti_id: selectedTtiBindingId.value });
}
</script>

<template>
    <div class="space-y-6">
        <div>
            <h3 class="text-lg font-medium leading-6 text-gray-900 dark:text-white">Text-to-Image (TTI) Settings</h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Configure your preferred model for generating images.</p>
        </div>

        <div v-if="dataStore.isLoadingTtiModels" class="text-center">
            Loading TTI models...
        </div>
        <div v-else-if="availableTtiBindings.length === 0" class="p-4 bg-yellow-50 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200 rounded-lg">
            No active Text-to-Image bindings are available. An administrator needs to configure one in the Admin Panel.
        </div>
        <div v-else class="space-y-4">
            <div>
                <label for="tti-model-select" class="block text-sm font-medium">Active TTI Binding</label>
                <SimpleSelectMenu 
                    v-model="selectedTtiBindingId" 
                    :items="availableTtiBindings" 
                    placeholder="Select a TTI Binding" 
                />
                <p class="mt-2 text-xs text-gray-500">This will be your default binding for image generation tasks.</p>
            </div>

            <div class="flex justify-end pt-4 border-t dark:border-gray-700">
                <button @click="handleSave" class="btn btn-primary">Save TTI Settings</button>
            </div>
        </div>
    </div>
</template>