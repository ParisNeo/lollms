<template>
    <GenericModal modal-name="modelCard" :title="model.alias.title || 'Model Information'" maxWidthClass="max-w-lg">
        <template #body>
            <div v-if="model && model.alias" class="space-y-4">
                <div class="flex items-center gap-4">
                    <img v-if="model.alias.icon" :src="model.alias.icon" class="w-16 h-16 rounded-lg object-cover border dark:border-gray-600">
                    <IconCpuChip v-else class="w-16 h-16 text-gray-400 p-2 border dark:border-gray-600 rounded-lg" />
                    <div>
                        <h2 class="text-xl font-bold">{{ model.alias.title || model.name }}</h2>
                        <p class="text-sm font-mono text-gray-500">{{ model.id }}</p>
                    </div>
                </div>
                <div>
                    <h3 class="font-semibold mb-1">Description</h3>
                    <p class="text-gray-600 dark:text-gray-300 whitespace-pre-wrap">{{ model.alias.description || 'No description provided.' }}</p>
                </div>
                <div>
                    <h3 class="font-semibold mb-1">Vision Support</h3>
                    <p class="text-sm px-2 py-0.5 rounded-full inline-block"
                       :class="model.alias.has_vision ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300' : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300'">
                        {{ model.alias.has_vision ? 'Enabled' : 'Disabled' }}
                    </p>
                </div>
                <div v-if="model.alias.ctx_size">
                    <h3 class="font-semibold mb-1">Context Size</h3>
                    <p class="text-sm font-mono text-gray-600 dark:text-gray-300">{{ model.alias.ctx_size.toLocaleString() }} tokens</p>
                </div>
            </div>
             <div v-else class="text-center p-4 text-gray-500">
                Model information not available.
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('modelCard')" class="btn btn-primary">Close</button>
        </template>
    </GenericModal>
</template>

<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';

const uiStore = useUiStore();
const model = computed(() => uiStore.modalData('modelCard')?.model);
</script>