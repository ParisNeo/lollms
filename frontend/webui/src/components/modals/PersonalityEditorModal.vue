<script setup>
import { ref, watch, computed, onUnmounted } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useTasksStore } from '../../stores/tasks'; // NEW IMPORT
import GenericModal from '../ui/GenericModal.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore(); // NEW INSTANCE

const modalData = computed(() => uiStore.modalData('personalityEditor'));

const form = ref({});
const isLoading = ref(false);
const iconPreview = ref(null);

const modalTitle = computed(() => form.value.id ? 'Edit Personality' : 'Create Personality');

const isEnhancingPrompt = ref(false);
const promptEnhanceTaskId = ref(null);
const showCustomEnhancePrompt = ref(false);
const customEnhancePrompt = ref('');
let enhancePollInterval = null;

const currentEnhanceTask = computed(() => { // NEW COMPUTED FOR PROGRESS
    if (!promptEnhanceTaskId.value) return null;
    return tasksStore.tasks.find(t => t.id === promptEnhanceTaskId.value);
});


function stopEnhancePolling() {
    if (enhancePollInterval) {
        clearInterval(enhancePollInterval);
        enhancePollInterval = null;
    }
}

watch(modalData, (newData, oldData) => {
    if (newData?.personality) {
        form.value = { ...newData.personality };
        iconPreview.value = newData.personality.icon_base64 || null;
    }
    if (!newData && oldData) {
        stopEnhancePolling();
        isEnhancingPrompt.value = false;
    }
}, { immediate: true });

onUnmounted(() => {
    stopEnhancePolling();
});

function compressImage(file, maxSize = 96) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                let { width, height } = img;

                if (width > height) {
                    if (width > maxSize) {
                        height = Math.round(height * (maxSize / width));
                        width = maxSize;
                    }
                } else {
                    if (height > maxSize) {
                        width = Math.round(width * (maxSize / height));
                        height = maxSize;
                    }
                }

                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);

                const dataUrl = canvas.toDataURL('image/webp', 0.8);
                if (dataUrl.length > 10) {
                    resolve(dataUrl);
                } else {
                    resolve(canvas.toDataURL('image/jpeg', 0.85));
                }
            };
            img.onerror = reject;
            img.src = e.target.result;
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

async function handleIconUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
        uiStore.addNotification('Image file is too large (max 5MB).', 'error');
        return;
    }

    try {
        const compressedDataUrl = await compressImage(file);
        form.value.icon_base64 = compressedDataUrl;
        iconPreview.value = compressedDataUrl;
    } catch(error) {
        console.error("Image compression failed:", error);
        uiStore.addNotification('Failed to process image.', 'error');
    }
}

async function handleSave() {
  if (!form.value.name || !form.value.prompt_text) {
    uiStore.addNotification('Name and System Prompt are required.', 'error');
    return;
  }
  
  isLoading.value = true;
  const action = form.value.id ? dataStore.updatePersonality : dataStore.addPersonality;
  
  try {
    await action(form.value);
    uiStore.closeModal('personalityEditor');
  } catch (error) {
    // Error is handled by interceptor, don't close modal on failure
  } finally {
    isLoading.value = false;
  }
}

async function handleEnhancePrompt() {
    if (!form.value.prompt_text.trim()) {
        uiStore.addNotification('System prompt cannot be empty for enhancement.', 'warning');
        return;
    }
    
    isEnhancingPrompt.value = true;
    promptEnhanceTaskId.value = null;
    
    try {
        const response = await dataStore.enhancePersonalityPrompt(form.value.prompt_text, customEnhancePrompt.value || null);
        promptEnhanceTaskId.value = response.task_id;
        uiStore.addNotification('Prompt enhancement started in the background.', 'info');
        
        await tasksStore.fetchTasks(); // CORRECTED: Use tasksStore
        
        // Start polling
        enhancePollInterval = setInterval(async () => {
            await tasksStore.fetchTasks(); // CORRECTED: Use tasksStore
            const task = tasksStore.tasks.find(t => t.id === promptEnhanceTaskId.value);
            if (task && (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled')) {
                stopEnhancePolling();
                isEnhancingPrompt.value = false;
                
                if (task.status === 'completed') {
                    let resultData = null;
                    if (task.result && typeof task.result === 'string') {
                        try { resultData = JSON.parse(task.result); } catch (e) { console.error("Failed to parse enhancement result", e); }
                    } else {
                        resultData = task.result;
                    }

                    if (resultData?.enhanced_prompt_text) {
                        form.value.prompt_text = resultData.enhanced_prompt_text; // DIRECT UPDATE
                        uiStore.addNotification('System prompt enhanced successfully!', 'success');
                    } else {
                        uiStore.addNotification('Enhancement finished, but no new text was returned.', 'warning');
                    }
                } else {
                    uiStore.addNotification(`Prompt enhancement failed: ${task.error || 'Unknown error.'}`, 'error');
                }
            }
        }, 3000);

    } catch (error) {
        uiStore.addNotification(`Failed to start prompt enhancement: ${error.response?.data?.detail || error.message}`, 'error');
        isEnhancingPrompt.value = false;
    }
}
</script>

<template>
  <GenericModal modalName="personalityEditor" :title="modalTitle" maxWidthClass="max-w-4xl">
    <template #body>
      <!-- NEW: Progress Indicator for Enhancement -->
      <div v-if="isEnhancingPrompt" class="text-center p-6 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
          <IconAnimateSpin class="w-8 h-8 mx-auto text-blue-500 animate-spin" />
          <p class="mt-4 font-semibold">Enhancing Prompt...</p>
          <div v-if="currentEnhanceTask">
              <p class="text-sm text-gray-500 mt-2">{{ currentEnhanceTask.description }}</p>
              <div class="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-600 mt-4">
                  <div class="bg-blue-600 h-2.5 rounded-full" :style="{ width: currentEnhanceTask.progress + '%' }"></div>
              </div>
              <p class="text-xs text-gray-500 mt-1">{{ currentEnhanceTask.progress }}%</p>
          </div>
          <p v-else class="text-sm text-gray-500 mt-2">Initializing enhancement task...</p>
      </div>
      
      <!-- Existing Form (now using v-show) -->
      <form v-show="!isEnhancingPrompt" @submit.prevent="handleSave" class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium">Name*</label>
              <input type="text" v-model="form.name" required class="input-field mt-1" placeholder="e.g., Creative Writer">
            </div>
            <div>
              <label class="block text-sm font-medium">Category</label>
              <input type="text" v-model="form.category" class="input-field mt-1" placeholder="e.g., Writing, Coding, Fun">
            </div>
            <div>
                <label class="block text-sm font-medium">Author</label>
                <input type="text" v-model="form.author" class="input-field mt-1" placeholder="Your name or alias">
            </div>
            <div>
                <label class="block text-sm font-medium">Icon (Image, max 5MB)</label>
                <div class="flex items-center space-x-4">
                    <input type="file" @change="handleIconUpload" accept="image/png, image/jpeg, image/webp" class="input-field mt-1 file:mr-4 file:py-1 file:px-2 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-blue-900/50 dark:file:text-blue-300 dark:hover:file:bg-blue-900">
                    <img v-if="iconPreview" :src="iconPreview" alt="Icon Preview" class="h-12 w-12 object-cover rounded-md border dark:border-gray-600 bg-gray-100 dark:bg-gray-700 flex-shrink-0"/>
                </div>
            </div>
        </div>
        <div>
          <label class="block text-sm font-medium">Description</label>
          <textarea v-model="form.description" rows="2" class="input-field mt-1" placeholder="Briefly describe this personality's purpose and style..."></textarea>
        </div>
        <div>
          <label class="block text-sm font-medium">Disclaimer</label>
          <textarea v-model="form.disclaimer" rows="2" class="input-field mt-1" placeholder="Any warnings or disclaimers for the user..."></textarea>
        </div>
        <div>
            <div class="flex items-center justify-between mb-1">
                <label class="block text-sm font-medium">System Prompt*</label>
                <button @click="handleEnhancePrompt" type="button" class="btn btn-secondary btn-xs flex items-center gap-1" :disabled="isEnhancingPrompt || isLoading">
                    <IconAnimateSpin v-if="isEnhancingPrompt" class="w-4 h-4 animate-spin" />
                    <IconSparkles v-else class="w-4 h-4" />
                    <span>Enhance</span>
                </button>
            </div>
          <textarea v-model="form.prompt_text" rows="8" required class="input-field mt-1 font-mono text-sm" placeholder="Enter the core instructions, role, and context for the AI..."></textarea>
        </div>
        <div class="mb-4">
            <label class="flex items-center">
                <input type="checkbox" v-model="showCustomEnhancePrompt" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                <span class="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300">Add custom enhancement instructions</span>
            </label>
            <textarea v-if="showCustomEnhancePrompt" v-model="customEnhancePrompt" rows="2" class="input-field mt-2" placeholder="e.g., Make it more concise and formal."></textarea>
        </div>
        <div>
          <label class="block text-sm font-medium">Script Code (Optional)</label>
          <textarea v-model="form.script_code" rows="6" class="input-field mt-1 font-mono text-sm" placeholder="Enter Python script for advanced logic..."></textarea>
        </div>
         <div>
            <label class="flex items-center">
                <input type="checkbox" v-model="form.is_public" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                <span class="ml-2 text-sm">Make this personality public for all users</span>
            </label>
        </div>
      </form>
    </template>
    <template #footer>
      <button @click="uiStore.closeModal('personalityEditor')" class="btn btn-secondary" :disabled="isEnhancingPrompt">Cancel</button>
      <button @click="handleSave" class="btn btn-primary" :disabled="isLoading || isEnhancingPrompt">
        {{ isLoading ? 'Saving...' : 'Save Personality' }}
      </button>
    </template>
  </GenericModal>
</template>