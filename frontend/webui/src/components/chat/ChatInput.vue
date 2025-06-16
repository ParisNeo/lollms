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
const availableMcpTools = computed(() => dataStore.availableMcpToolsForSelector);

const isSendDisabled = computed(() => {
  return generationInProgress.value || (messageText.value.trim() === '' && uploadedImages.value.length === 0);
});

// RAG Store Selection
const ragStoreSelection = computed({
    get() {
        const currentId = activeDiscussion.value?.rag_datastore_id;
        return currentId ? [currentId] : [];
    },
    set(newIds) {
        if (activeDiscussion.value) {
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

// MCP Tool Selection
const mcpToolSelection = computed({
    get() {
        return activeDiscussion.value?.mcp_tool_ids || [];
    },
    set(newIds) {
        if (activeDiscussion.value) {
            discussionsStore.updateDiscussionMcps({
                discussionId: activeDiscussion.value.id,
                mcp_tool_ids: newIds
            });
        }
    }
});


watch(activeDiscussion, (newDiscussion) => {
    if (newDiscussion) {
        // Sync the RAG selection when the discussion changes
        const currentRagId = newDiscussion.rag_datastore_id;
        ragStoreSelection.value = currentRagId ? [currentRagId] : [];
        // Sync the MCP selection
        mcpToolSelection.value = newDiscussion.mcp_tool_ids || [];
    } else {
        ragStoreSelection.value = [];
        mcpToolSelection.value = [];
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
      
      <!-- MCP Tool Selector -->
      <div class="self-end">
        <MultiSelectMenu
            v-model="mcpToolSelection"
            :items="availableMcpTools"
            placeholder="MCP Tools"
            activeClass="!bg-purple-600 !text-white"
            inactiveClass="btn-secondary"
        >
            <template #button="{ toggle, selected, activeClass, inactiveClass }">
                <button @click="toggle" :class="[selected.length > 0 ? activeClass : inactiveClass]" class="relative btn !p-2.5" title="Select MCP Tools">
                    <svg viewBox="0 0 359.211 359.211" class="w-6 h-6" fill="currentColor">
                        <path d="M352.203,286.132l-78.933-78.933c-3.578-3.578-8.35-5.548-13.436-5.548c-2.151,0-4.238,0.373-6.21,1.05l-18.929-18.929 c-2.825-2.826-6.593-4.382-10.607-4.382c-4.014,0-7.781,1.556-10.606,4.381l-4.978,4.978l-8.904-8.904l38.965-39.17 c9.105,3.949,19.001,5.837,29.224,5.837c0.002,0,0.004,0,0.007,0c19.618,0,38.064-7.437,51.939-21.312 c18.59-18.588,25.842-45.811,18.926-71.207c-0.859-3.159-3.825-5.401-7.053-5.401c-1.389,0-3.453,0.435-5.39,2.372 c-0.265,0.262-26.512,26.322-35.186,34.996c-0.955,0.955-2.531,1.104-3.45,1.104c-0.659,0-1.022-0.069-1.022-0.069v0.002 l-0.593-0.068c-10.782-0.99-23.716-2.984-26.98-4.489c-1.556-3.289-3.427-16.533-4.427-27.489v-0.147l-0.234-0.308 c-0.058-0.485-0.31-2.958,1.863-5.131c9.028-9.029,33.847-34.072,34.083-34.311c2.1-2.099,2.9-4.739,2.232-7.245 c-0.801-3.004-3.355-4.686-5.469-5.257C280.772,0.859,274.292,0,267.788,0c-19.62,0-38.068,7.64-51.941,21.512 c-21.901,21.901-27.036,54.296-15.446,81.141l-38.996,38.995L94.682,74.927c-0.041-0.041-0.086-0.075-0.128-0.115 c0.63-2.567,0.907-5.233,0.791-7.947c-0.329-7.73-3.723-15.2-9.558-21.034L62.041,22.083c-0.519-0.519-3.318-3.109-7.465-3.109 c-1.926,0-4.803,0.583-7.58,3.359L20.971,48.359c-3.021,3.021-4.098,6.903-2.954,10.652c0.767,2.512,2.258,4.139,2.697,4.578 l23.658,23.658c6.179,6.179,14.084,9.582,22.259,9.582c0,0,0,0,0.001,0c2.287,0,4.539-0.281,6.721-0.818 c0.041,0.042,0.075,0.087,0.116,0.128l66.722,66.722l-31.692,31.692c-1.428,1.428-2.669,2.991-3.726,4.654 c-9.281-4.133-19.404-6.327-29.869-6.327c-19.623,0-38.071,7.642-51.946,21.517c-18.589,18.589-25.841,45.914-18.926,71.31 c0.859,3.158,3.825,5.451,7.052,5.451c0,0,0,0,0.001,0c1.389,0,3.453-0.41,5.39-2.347c0.265-0.262,26.513-26.309,35.187-34.983 c0.955-0.955,2.639-1.097,3.557-1.097c0.66,0,1.125,0.072,1.132,0.072h-0.001l0.487,0.069c10.779,0.988,23.813,2.982,27.078,4.489 c1.556,3.29,3.575,16.534,4.554,27.49l0.07,0.501c0.006,0.026,0.362,2.771-1.952,5.086c-9.029,9.029-33.888,34.072-34.124,34.311 c-2.1,2.099-2.92,4.74-2.252,7.245c0.802,3.004,3.346,4.685,5.459,5.256c6.264,1.694,12.738,2.553,19.243,2.553 c19.621,0,38.066-7.64,51.938-21.512c13.876-13.875,21.518-32.324,21.517-51.947c0-10.465-2.193-20.586-6.326-29.868 c1.664-1.057,3.227-2.298,4.654-3.726l31.693-31.693l8.904,8.904l-4.979,4.979c-2.826,2.825-4.382,6.592-4.382,10.606 c0,4.015,1.556,7.782,4.382,10.607l18.929,18.929c-0.677,1.972-1.05,4.059-1.05,6.209c0,5.086,1.971,9.857,5.549,13.435 l78.934,78.934c3.577,3.577,8.349,5.548,13.435,5.548c5.086,0,9.857-1.971,13.435-5.548l40.659-40.66 c3.578-3.578,5.549-8.349,5.549-13.435C357.752,294.482,355.782,289.71,352.203,286.132z"/>
                    </svg>
                    <span v-if="selected.length > 0" class="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-purple-800 rounded-full">
                        {{ selected.length }}
                    </span>
                </button>
            </template>
        </MultiSelectMenu>
      </div>

      <!-- RAG Store Selector -->
      <div class="self-end">
        <MultiSelectMenu
            v-model="ragStoreSelection"
            :items="availableRagStores"
            placeholder="RAG Stores"
            activeClass="!bg-green-600 !text-white"
            inactiveClass="btn-secondary"
        >
            <template #button="{ toggle, selected, activeClass, inactiveClass }">
                <button @click="toggle" :class="[selected.length > 0 ? activeClass : inactiveClass]" class="relative btn !p-2.5" title="Select RAG Store">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
                    </svg>
                     <span v-if="selected.length > 0" class="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-green-800 rounded-full">
                        {{ selected.length }}
                    </span>
                </button>
            </template>
        </MultiSelectMenu>
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