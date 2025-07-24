<script setup>
import { ref, computed, watch, onUnmounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import GenericModal from '../ui/GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const dataStore = useDataStore();
const tasksStore = useTasksStore();

const { isEnhancingPrompt } = storeToRefs(dataStore); // Keep this for button state on parent

const modalProps = computed(() => uiStore.modalData('enhancePersonalityPrompt'));
const originalPrompt = computed(() => modalProps.value?.prompt_text || '');
const modificationPrompt = computed(() => modalProps.value?.modification_prompt || '');
const onApply = computed(() => modalProps.value?.onApply);

const viewState = ref('confirm'); // confirm, running, completed, failed
const taskId = ref(null);
let pollInterval = null;

const runningTask = computed(() => {
    if (!taskId.value) return null;
    return tasksStore.getTaskById(taskId.value);
});

const enhancedPrompt = computed(() => runningTask.value?.result?.enhanced_prompt || '');

async function startEnhancement() {
    viewState.value = 'running';
    try {
        const taskInfo = await dataStore.enhancePersonalityPrompt(originalPrompt.value, modificationPrompt.value);
        if (taskInfo && taskInfo.id) {
            taskId.value = taskInfo.id;
            startPolling();
        } else {
            throw new Error("Failed to start enhancement task.");
        }
    } catch (error) {
        viewState.value = 'failed';
    }
}

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(async () => {
        if (taskId.value) {
            await tasksStore.fetchTask(taskId.value);
            const task = tasksStore.getTaskById(taskId.value);
            if (task && (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled')) {
                clearInterval(pollInterval);
                viewState.value = task.status === 'completed' ? 'completed' : 'failed';
            }
        }
    }, 2000);
}

function handleApply() {
    if (onApply.value && enhancedPrompt.value) {
        onApply.value(enhancedPrompt.value);
    }
    closeModal();
}

function closeModal() {
    clearInterval(pollInterval);
    taskId.value = null;
    viewState.value = 'confirm';
    uiStore.closeModal('enhancePersonalityPrompt');
}

onUnmounted(() => {
    clearInterval(pollInterval);
});

watch(() => uiStore.isModalOpen('enhancePersonalityPrompt'), (isOpen) => {
    if (!isOpen) {
        clearInterval(pollInterval);
        taskId.value = null;
        viewState.value = 'confirm';
    }
});
</script>

<template>
    <GenericModal modal-name="enhancePersonalityPrompt" title="Enhance System Prompt with AI" maxWidthClass="max-w-4xl" :allow-overlay-close="viewState !== 'running'">
        <template #body>
            <div class="p-6 space-y-6">
                <!-- Confirmation View -->
                <div v-if="viewState === 'confirm'" class="space-y-4">
                    <div>
                        <h4 class="font-semibold text-gray-800 dark:text-gray-200">Original Prompt</h4>
                        <p class="mt-1 text-sm text-gray-600 dark:text-gray-400 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-md whitespace-pre-wrap font-mono">{{ originalPrompt || '(No prompt provided)' }}</p>
                    </div>
                    <div v-if="modificationPrompt">
                        <h4 class="font-semibold text-gray-800 dark:text-gray-200">With Instructions</h4>
                        <p class="mt-1 text-sm text-gray-600 dark:text-gray-400 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-md whitespace-pre-wrap font-mono">{{ modificationPrompt }}</p>
                    </div>
                    <p class="text-sm text-gray-500">The AI will refine the original prompt based on your instructions. Are you ready to proceed?</p>
                </div>

                <!-- Running View -->
                <div v-if="viewState === 'running' && runningTask" class="space-y-4">
                    <div class="flex items-center space-x-3 text-lg font-semibold">
                        <IconAnimateSpin class="w-6 h-6 text-blue-500" />
                        <span>Enhancing prompt...</span>
                    </div>
                    <div>
                        <div class="w-full bg-gray-200 rounded-full dark:bg-gray-700 h-2.5">
                            <div class="bg-blue-600 h-2.5 rounded-full transition-all duration-300" :style="{ width: `${runningTask.progress}%` }"></div>
                        </div>
                        <p class="text-center text-sm mt-2">{{ runningTask.progress }}%</p>
                    </div>
                    <div v-if="runningTask.logs && runningTask.logs.length > 0" class="max-h-40 overflow-y-auto bg-gray-900 text-white font-mono text-xs p-3 rounded-md">
                        <p v-for="(log, index) in runningTask.logs" :key="index">
                            <span class="text-gray-500 mr-2">{{ new Date(log.timestamp).toLocaleTimeString() }}:</span>
                            <span>{{ log.message }}</span>
                        </p>
                    </div>
                </div>

                <!-- Completed View -->
                <div v-if="viewState === 'completed'" class="space-y-4">
                    <h3 class="text-lg font-semibold text-green-600 dark:text-green-400">Enhancement Complete!</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <h4 class="font-semibold text-gray-800 dark:text-gray-200 mb-1">Original</h4>
                            <p class="text-sm h-64 overflow-y-auto text-gray-600 dark:text-gray-400 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-md whitespace-pre-wrap font-mono">{{ originalPrompt }}</p>
                        </div>
                        <div>
                            <h4 class="font-semibold text-gray-800 dark:text-gray-200 mb-1">Enhanced</h4>
                            <p class="text-sm h-64 overflow-y-auto text-gray-800 dark:text-gray-200 p-3 bg-green-50 dark:bg-green-900/20 rounded-md whitespace-pre-wrap font-mono">{{ enhancedPrompt }}</p>
                        </div>
                    </div>
                </div>
                
                <!-- Failed View -->
                 <div v-if="viewState === 'failed'" class="space-y-4">
                     <h3 class="text-lg font-semibold text-red-600 dark:text-red-400">Enhancement Failed</h3>
                     <p class="text-sm text-gray-600 dark:text-gray-400">The task could not be completed. See the error and logs below for details.</p>
                     <div v-if="runningTask?.error" class="text-sm bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 p-3 rounded-md font-mono">
                        <strong>Error:</strong> {{ runningTask.error }}
                     </div>
                     <div v-if="runningTask?.logs && runningTask.logs.length > 0">
                         <h4 class="font-semibold text-gray-800 dark:text-gray-200 mb-1 text-sm">Task Logs</h4>
                        <div class="max-h-48 overflow-y-auto bg-gray-900 text-white font-mono text-xs p-3 rounded-md">
                            <p v-for="(log, index) in runningTask.logs" :key="index" :class="{'text-red-400': log.level === 'CRITICAL' || log.level === 'ERROR'}">
                                <span class="text-gray-500 mr-2">{{ new Date(log.timestamp).toLocaleTimeString() }}:</span>
                                <span>{{ log.message }}</span>
                            </p>
                        </div>
                    </div>
                 </div>

            </div>
        </template>
        <template #footer>
            <div v-if="viewState === 'confirm'">
                <button type="button" @click="closeModal" class="btn btn-secondary">Cancel</button>
                <button type="button" @click="startEnhancement" class="btn btn-primary ml-3">Start Enhancement</button>
            </div>
            <div v-if="viewState === 'running'">
                <button type="button" class="btn btn-secondary" disabled>Running...</button>
            </div>
             <div v-if="viewState === 'completed'">
                <button type="button" @click="closeModal" class="btn btn-secondary">Discard</button>
                <button type="button" @click="handleApply" class="btn btn-primary ml-3">Apply Changes</button>
            </div>
            <div v-if="viewState === 'failed'">
                 <button type="button" @click="closeModal" class="btn btn-secondary">Close</button>
            </div>
        </template>
    </GenericModal>
</template>