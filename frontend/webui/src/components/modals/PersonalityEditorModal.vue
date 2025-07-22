<script setup>
import { ref, watch, computed, onUnmounted } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useTasksStore } from '../../stores/tasks';
import { useAuthStore } from '../../stores/auth';
import { storeToRefs } from 'pinia';
import GenericModal from '../ui/GenericModal.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import MultiSelectMenu from '../ui/MultiSelectMenu.vue';
import apiClient from '../../services/api';

const dataStore = useDataStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();
const authStore = useAuthStore();

const modalData = computed(() => uiStore.modalData('personalityEditor'));
const { availableMcpToolsForSelector } = storeToRefs(dataStore);
const { isAdmin } = storeToRefs(authStore);
const { availableRagStores } = storeToRefs(dataStore);

const form = ref({});
const isLoading = ref(false);
const iconPreview = ref(null);
const fileInputRef = ref(null);
const isExtractingText = ref(false);

const modalTitle = computed(() => form.value.id ? 'Edit Personality' : 'Create Personality');

watch(modalData, (newData) => {
    if (newData?.personality) {
        const p = newData.personality;
        form.value = { 
            ...p, 
            active_mcps: p.active_mcps || [],
            owner_type: p.owner_username === 'System' ? 'system' : 'user',
            data_source_type: p.data_source_type || 'none',
            data_source: p.data_source || '',
        };
        
        if (p.id && (p.is_public || p.owner_username === 'System')) {
            const clonedPersonality = { ...form.value };
            clonedPersonality.id = null;
            clonedPersonality.is_public = false;
            clonedPersonality.owner_type = 'user';
            form.value = clonedPersonality;
        }
        iconPreview.value = p.icon_base64 || null;
    }
}, { immediate: true });


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
    const payload = { ...form.value };
    if (payload.data_source_type === 'none') {
        payload.data_source = null;
    }
    await action(payload);
    uiStore.closeModal('personalityEditor');
  } catch (error) {
    // Error is handled by interceptor, don't close modal on failure
  } finally {
    isLoading.value = false;
  }
}

async function handleKnowledgeFileUpload(event) {
    const files = event.target.files;
    if (!files.length) return;

    isExtractingText.value = true;
    const formData = new FormData();
    for (const file of files) {
        formData.append('files', file);
    }

    try {
        const response = await apiClient.post('/api/files/extract-text', formData);
        const extractedText = response.data.text;
        form.value.data_source = form.value.data_source 
            ? `${form.value.data_source}\n\n${extractedText}` 
            : extractedText;
        uiStore.addNotification(`Extracted text from ${files.length} file(s).`, 'success');
    } catch (error) {
        // Error is handled by the global API interceptor
    } finally {
        isExtractingText.value = false;
        if (fileInputRef.value) fileInputRef.value.value = ''; // Reset file input
    }
}

</script>

<template>
  <GenericModal modalName="personalityEditor" :title="modalTitle" maxWidthClass="max-w-4xl">
    <template #body>
      <form @submit.prevent="handleSave" class="space-y-4">
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
        <div v-if="isAdmin && !form.id" class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
                <label class="block text-sm font-medium">Type</label>
                <select v-model="form.owner_type" class="input-field mt-1">
                    <option value="user">Personal (for my account only)</option>
                    <option value="system">System (for all users)</option>
                </select>
            </div>
        </div>
        <div v-if="availableMcpToolsForSelector.length > 0">
            <label class="block text-sm font-medium">Active MCPs (Tools)</label>
            <MultiSelectMenu 
                v-model="form.active_mcps" 
                :items="availableMcpToolsForSelector" 
                placeholder="Select default tools..." 
                class="mt-1"
            />
        </div>
        <div>
          <label class="block text-sm font-medium">Description</label>
          <textarea v-model="form.description" rows="2" class="input-field mt-1" placeholder="Briefly describe this personality's purpose and style..."></textarea>
        </div>
        
        <!-- KNOWLEDGE SECTION -->
        <div class="space-y-2 pt-4 border-t dark:border-gray-600">
            <h3 class="text-base font-medium">Knowledge</h3>
            <div>
                <label class="block text-sm font-medium">Knowledge Type</label>
                <select v-model="form.data_source_type" class="input-field mt-1">
                    <option value="none">None</option>
                    <option value="raw_text">Static (Raw Text & Files)</option>
                    <option value="datastore">Dynamic (Data Store)</option>
                </select>
            </div>
            
            <div v-if="form.data_source_type === 'raw_text'">
                <label class="block text-sm font-medium">Static Knowledge Content</label>
                <textarea v-model="form.data_source" rows="6" class="input-field mt-1 font-mono text-sm" placeholder="Paste text or upload files..."></textarea>
                <div class="mt-2 flex items-center gap-4">
                    <input type="file" ref="fileInputRef" @change="handleKnowledgeFileUpload" multiple class="hidden" accept=".txt,.pdf,.docx">
                    <button type="button" @click="fileInputRef.click()" :disabled="isExtractingText" class="btn btn-secondary text-sm">
                        <IconAnimateSpin v-if="isExtractingText" class="w-4 h-4 mr-2" />
                        {{ isExtractingText ? 'Processing...' : 'Add from Files (.txt, .pdf, .docx)' }}
                    </button>
                </div>
            </div>

            <div v-if="form.data_source_type === 'datastore'">
                <label class="block text-sm font-medium">Select Data Store</label>
                <select v-model="form.data_source" class="input-field mt-1">
                    <option :value="null">Select a Data Store...</option>
                    <option v-for="store in availableRagStores" :key="store.id" :value="store.id">{{ store.name }}</option>
                </select>
            </div>
        </div>
        
        <div>
          <label class="block text-sm font-medium">Disclaimer</label>
          <textarea v-model="form.disclaimer" rows="2" class="input-field mt-1" placeholder="Any warnings or disclaimers for the user..."></textarea>
        </div>
        <div>
            <div class="flex items-center justify-between mb-1">
                <label class="block text-sm font-medium">System Prompt*</label>
            </div>
          <textarea v-model="form.prompt_text" rows="8" required class="input-field mt-1 font-mono text-sm" placeholder="Enter the core instructions, role, and context for the AI..."></textarea>
        </div>
        <div>
          <label class="block text-sm font-medium">Script Code (Optional)</label>
          <textarea v-model="form.script_code" rows="6" class="input-field mt-1 font-mono text-sm" placeholder="Enter Python script for advanced logic..."></textarea>
        </div>
         <div v-if="isAdmin">
            <label class="flex items-center">
                <input type="checkbox" v-model="form.is_public" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                <span class="ml-2 text-sm">Make this personality public for all users</span>
            </label>
        </div>
      </form>
    </template>
    <template #footer>
      <button @click="uiStore.closeModal('personalityEditor')" class="btn btn-secondary">Cancel</button>
      <button @click="handleSave" class="btn btn-primary" :disabled="isLoading">
        {{ isLoading ? 'Saving...' : 'Save Personality' }}
      </button>
    </template>
  </GenericModal>
</template>