<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useFlowStore } from '../../stores/flow';
import { useUiStore } from '../../stores/ui';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconShare from '../../assets/icons/IconShare.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const emit = defineEmits(['close']);
const router = useRouter();
const flowStore = useFlowStore();
const uiStore = useUiStore();

const name = ref('');
const description = ref('');
const isCreating = ref(false);

async function handleCreate() {
    if (!name.value.trim()) {
        uiStore.addNotification("Please enter a flow name", "warning");
        return;
    }

    isCreating.value = true;
    try {
        const newFlow = await flowStore.createFlow(name.value, description.value);
        if (newFlow) {
            uiStore.addNotification("Flow created successfully", "success");
            emit('close');
            // Navigate to flow studio
            router.push('/flow-studio');
        }
    } catch (error) {
        console.error(error);
        uiStore.addNotification("Failed to create flow", "error");
    } finally {
        isCreating.value = false;
    }
}
</script>

<template>
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
        <div class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-lg flex flex-col border dark:border-gray-700 overflow-hidden transform transition-all scale-100">
            <!-- Header -->
            <div class="p-4 border-b dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-800/80">
                <div class="flex items-center gap-3">
                    <div class="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg text-blue-600 dark:text-blue-400">
                        <IconShare class="w-5 h-5" />
                    </div>
                    <h3 class="text-lg font-bold text-gray-800 dark:text-gray-100">Create New Workflow</h3>
                </div>
                <button @click="$emit('close')" class="text-gray-400 hover:text-red-500 transition-colors p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full">
                    <IconXMark class="w-5 h-5"/>
                </button>
            </div>

            <!-- Body -->
            <div class="p-6 space-y-5">
                <div>
                    <label class="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-1.5">Flow Name</label>
                    <input 
                        v-model="name" 
                        type="text" 
                        class="input-field w-full" 
                        placeholder="e.g. Text Summarization Pipeline" 
                        @keydown.enter="handleCreate"
                        autofocus
                    >
                </div>
                
                <div>
                    <label class="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-1.5">Description <span class="font-normal text-gray-400 text-xs">(Optional)</span></label>
                    <textarea 
                        v-model="description" 
                        class="input-field w-full h-32 resize-none py-2" 
                        placeholder="Describe what this workflow does..."
                    ></textarea>
                </div>
            </div>

            <!-- Footer -->
            <div class="p-4 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex justify-end gap-3">
                <button @click="$emit('close')" class="btn btn-secondary" :disabled="isCreating">Cancel</button>
                <button @click="handleCreate" class="btn btn-primary min-w-[120px]" :disabled="isCreating || !name.trim()">
                    <span v-if="!isCreating">Create Flow</span>
                    <span v-else class="flex items-center gap-2">
                        <IconAnimateSpin class="w-4 h-4 animate-spin" /> Creating...
                    </span>
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.input-field {
    @apply bg-white dark:bg-gray-950 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all;
}
</style>
