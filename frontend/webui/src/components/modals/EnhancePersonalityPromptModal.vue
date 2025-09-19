<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import { useTasksStore } from '../../stores/tasks';
import GenericModal from './GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const dataStore = useDataStore();
const tasksStore = useTasksStore();

const modalProps = computed(() => uiStore.modalData('enhancePersonalityPrompt'));
const originalPrompt = computed(() => modalProps.value?.prompt_text || '');
const onApply = computed(() => modalProps.value?.onApply);

const modificationPromptInput = ref('');

const viewState = ref('confirm'); // confirm, running, completed, failed
const taskId = ref(null);

const runningTask = computed(() => {
    if (!taskId.value) return null;
    return tasksStore.getTaskById(taskId.value);
});

const enhancedPrompt = computed(() => {
    if (runningTask.value?.result && typeof runningTask.value.result === 'string') {
        try {
            const resultObj = JSON.parse(runningTask.value.result);
            return resultObj.enhanced_system_prompt || '';
        } catch (e) {
            console.error("Failed to parse task result JSON for enhanced prompt:", e);
            return '';
        }
    }
    return '';
});

async function startEnhancement() {
    viewState.value = 'running';
    try {
        const taskInfo = await dataStore.enhancePersonalityPrompt(originalPrompt.value, modificationPromptInput.value);
        if (taskInfo && taskInfo.task_id) {
            taskId.value = taskInfo.task_id;
            // The global polling in App.vue will pick up the task.
        } else {
            throw new Error("Failed to start enhancement task.");
        }
    } catch (error) {
        viewState.value = 'failed';
    }
}

watch(runningTask, (currentTask) => {
    if (currentTask && ['completed', 'failed', 'cancelled'].includes(currentTask.status)) {
        viewState.value = currentTask.status === 'completed' ? 'completed' : 'failed';
    }
});

function handleApply() {
    if (onApply.value && enhancedPrompt.value) {
        onApply.value(enhancedPrompt.value);
    }
    closeModal();
}

function closeModal() {
    taskId.value = null;
    viewState.value = 'confirm';
    modificationPromptInput.value = '';
    uiStore.closeModal('enhancePersonalityPrompt');
}

watch(() => uiStore.isModalOpen('enhancePersonalityPrompt'), (isOpen) => {
    if (!isOpen) {
        taskId.value = null;
        viewState.value = 'confirm';
        modificationPromptInput.value = '';
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
                        <p class="mt-1 text-sm text-gray-600 dark:text-gray-400 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-md whitespace-pre-wrap font-mono max-h-40 overflow-y-auto">{{ originalPrompt || '(No prompt provided)' }}</p>
                    </div>
                    <div>
                        <label for="modification-prompt-input" class="block font-semibold text-gray-800 dark:text-gray-200">Enhancement Instructions (optional)</label>
                        <textarea id="modification-prompt-input" v-model="modificationPromptInput" rows="3" class="input-field mt-1" placeholder="e.g., Make the personality more formal and professional..."></textarea>
                        <p class="mt-1 text-xs text-gray-500">The AI will refine the original prompt based on your instructions. If left blank, a general enhancement will be applied.</p>
                    </div>
                </div>

                <!-- Running View -->
                <div v-if="viewState === 'running'" class="space-y-4">
                    <div class="flex items-center space-x-3 text-lg font-semibold">
                        <IconAnimateSpin class="w-6 h-6 text-blue-500" />
                        <span>Enhancing prompt...</span>
                    </div>
                    <div v-if="runningTask">
                        <div class="w-full bg-gray-200 rounded-full dark:bg-gray-700 h-2.5">
                            <div class="bg-blue-600 h-2.5 rounded-full transition-all duration-300" :style="{ width: `${runningTask.progress}%` }"></div>
                        </div>
                        <p class="text-center text-sm mt-2">{{ runningTask.progress }}%</p>
                        <div v-if="runningTask.logs && runningTask.logs.length > 0" class="mt-4 max-h-40 overflow-y-auto bg-gray-900 text-white font-mono text-xs p-3 rounded-md">
                            <p v-for="(log, index) in runningTask.logs" :key="index">
                                <span class="text-gray-500 mr-2">{{ new Date(log.timestamp).toLocaleTimeString() }}:</span>
                                <span>{{ log.message }}</span>
                            </p>
                        </div>
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
                     <div v-else class="text-sm bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 p-3 rounded-md">
                        An unknown error occurred. Please check the server console for more details.
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