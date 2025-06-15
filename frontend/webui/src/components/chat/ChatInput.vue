<script setup>
import { ref, computed, watch } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';
import MultiSelectMenu from '../ui/MultiSelectMenu.vue';

const discussionsStore = useDiscussionsStore();
const dataStore = useDataStore();
const uiStore = useUiStore();

const messageText = ref('');
const uploadedImages = ref([]);
const isUploading = ref(false);
const textarea = ref(null);
const imageInput = ref(null);

const generationInProgress = computed(() => discussionsStore.generationInProgress);
const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const availableRagStores = computed(() => dataStore.availableRagStores);

const isSendDisabled = computed(() => {
  return generationInProgress.value || (messageText.value.trim() === '' && uploadedImages.value.length === 0);
});

// FIX: This computed property now correctly interfaces between the singular state and the multi-select component
const ragStoreSelection = computed({
    get() {
        const currentId = activeDiscussion.value?.rag_datastore_id;
        return currentId ? [currentId] : [];
    },
    set(newIds) {
        if (activeDiscussion.value) {
            // Per instructions, use only the first selected item, or null if empty
            const singleIdToSet = newIds.length > 0 ? newIds[0] : null;
            
            if (activeDiscussion.value.rag_datastore_id !== singleIdToSet) {
                discussionsStore.updateDiscussionRagStore({
                    discussionId: activeDiscussion.value.id,
                    ragDatastoreId: singleIdToSet
                });
            }
        }
    }
});

watch(activeDiscussion, (newDiscussion) => {
    if (newDiscussion) {
        // Sync the selection when the discussion changes
        const currentId = newDiscussion.rag_datastore_id;
        ragStoreSelection.value = currentId ? [currentId] : [];
    } else {
        ragStoreSelection.value = [];
    }
}, { immediate: true });

async function handleSendMessage() {
  if (isSendDisabled.value) return;

  const payload = {
    prompt: messageText.value,
    image_server_paths: uploadedImages.value.map(img => img.server_path),
    localImageUrls: uploadedImages.value.map(img => img.local_url),
  };

  try {
    await discussionsStore.sendMessage(payload);
    messageText.value = '';
    uploadedImages.value.forEach(img => URL.revokeObjectURL(img.local_url));
    uploadedImages.value = [];
    if (textarea.value) {
      textarea.value.style.height = 'auto';
    }
  } catch (error) {
    uiStore.addNotification('There was an error sending your message.', 'error');
  }
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSendMessage();
  }
}

function autoGrowTextarea() {
  const el = textarea.value;
  if (el) {
    el.style.height = 'auto';
    const maxHeight = 200;
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? 'auto' : 'hidden';
  }
}

function triggerImageUpload() {
  imageInput.value.click();
}

async function handleImageSelection(event) {
    const files = Array.from(event.target.files);
    if (files.length === 0) return;
    if (uploadedImages.value.length + files.length > 5) {
        uiStore.addNotification('You can upload a maximum of 5 images.', 'warning');
        return;
    }

    isUploading.value = true;
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    try {
        const response = await apiClient.post('/api/upload/chat_image', formData);
        const newImages = response.data;
        newImages.forEach(imgInfo => {
            const originalFile = files.find(f => f.name === imgInfo.filename);
            if(originalFile) {
                uploadedImages.value.push({
                    server_path: imgInfo.server_path,
                    local_url: URL.createObjectURL(originalFile),
                    file: originalFile
                });
            }
        });
        uiStore.addNotification('Images uploaded and ready to send.', 'success');
    } catch (error) {
        console.error("Image upload failed:", error);
    } finally {
        isUploading.value = false;
        event.target.value = ''; 
    }
}

function removeImage(index) {
    const imageToRemove = uploadedImages.value[index];
    URL.revokeObjectURL(imageToRemove.local_url);
    uploadedImages.value.splice(index, 1);
}
</script>

<template>
  <footer class="border-t dark:border-gray-700 p-3 shadow-inner bg-white dark:bg-gray-800">
    <div v-if="uploadedImages.length > 0 || isUploading" class="mb-2 p-2 border-dashed border-gray-300 dark:border-gray-600 rounded-md">
      <div class="flex flex-wrap gap-2">
        <div v-for="(image, index) in uploadedImages" :key="image.server_path" class="relative w-16 h-16">
            <img :src="image.local_url" class="w-full h-full object-cover rounded-md" alt="Image preview" />
            <button @click="removeImage(index)" class="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold leading-none">×</button>
        </div>
         <div v-if="isUploading" class="w-16 h-16 bg-gray-200 dark:bg-gray-700 rounded-md flex items-center justify-center">
            <svg class="animate-spin h-6 w-6 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
        </div>
      </div>
    </div>

    <div class="flex items-end space-x-2">
      <button @click="triggerImageUpload" :disabled="isUploading" class="btn btn-secondary !p-2.5 self-end disabled:opacity-50" title="Upload Images">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
          <path stroke-linecap="round" stroke-linejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v12a1.5 1.5 0 0 0 1.5 1.5Zm10.5-11.25h.008v.008h-.008V8.25Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
        </svg>
      </button>
      <input type="file" ref="imageInput" @change="handleImageSelection" multiple accept="image/*" class="hidden">
      
      <div class="self-end w-40">
        <MultiSelectMenu
            v-model="ragStoreSelection"
            :items="availableRagStores"
            placeholder="RAG Stores"
            buttonClass="!py-2.5"
            activeClass="!bg-green-600 !text-white"
            inactiveClass="btn-secondary"
        />
      </div>

      <textarea
        ref="textarea"
        v-model="messageText"
        @keydown="handleKeydown"
        @input="autoGrowTextarea"
        rows="1"
        class="input-field flex-1 !p-2.5"
        placeholder="Type your message... (Shift+Enter for new line)"
        style="resize: none; overflow-y: hidden;"
      ></textarea>

      <button v-if="!generationInProgress" @click="handleSendMessage" :disabled="isSendDisabled" class="btn btn-primary self-end !p-2.5" title="Send Message">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
        </svg>
      </button>
      <button v-else @click="discussionsStore.stopGeneration" class="btn btn-danger self-end !p-2.5" title="Stop Generation">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
          <path stroke-linecap="round" stroke-linejoin="round" d="M5.25 7.5A2.25 2.25 0 0 1 7.5 5.25h9a2.25 2.25 0 0 1 2.25 2.25v9a2.25 2.25 0 0 1-2.25 2.25h-9a2.25 2.25 0 0 1-2.25-2.25v-9Z" />
        </svg>
      </button>
    </div>
  </footer>
</template>