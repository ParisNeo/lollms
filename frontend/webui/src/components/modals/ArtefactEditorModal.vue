<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black bg-opacity-60 backdrop-blur-sm transition-opacity" @click.self="closeModal">
    <div class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden transform transition-all">
      
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
        <div class="flex items-center space-x-3">
          <DocumentIcon v-if="!isAudio" class="w-6 h-6 text-blue-500" />
          <MusicalNoteIcon v-else class="w-6 h-6 text-purple-500" />
          <h2 class="text-xl font-semibold text-gray-900 dark:text-white truncate max-w-md">
            {{ artefact?.title || 'Edit Artefact' }}
          </h2>
          <span class="px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300">
            v{{ artefact?.version }}
          </span>
        </div>
        <div class="flex items-center space-x-2">
          <button @click="closeModal" class="p-2 text-gray-400 hover:text-gray-500 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
            <XMarkIcon class="w-5 h-5" />
          </button>
        </div>
      </div>

      <!-- Main Content Area -->
      <div class="flex-1 overflow-hidden flex flex-col relative bg-white dark:bg-gray-900 min-h-[400px]">
        
        <!-- Loading State -->
        <div v-if="isLoading" class="absolute inset-0 z-10 flex flex-col items-center justify-center bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm">
          <ArrowPathIcon class="w-8 h-8 text-blue-500 animate-spin mb-3" />
          <p class="text-gray-600 dark:text-gray-400 font-medium">Loading artefact content...</p>
        </div>

        <!-- Error State -->
        <div v-else-if="error" class="absolute inset-0 z-10 flex flex-col items-center justify-center p-6 text-center">
          <ExclamationTriangleIcon class="w-12 h-12 text-red-500 mb-4" />
          <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-2">Failed to load content</h3>
          <p class="text-gray-600 dark:text-gray-400 max-w-md">{{ error }}</p>
          <button @click="loadContent" class="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
            Try Again
          </button>
        </div>

        <!-- Audio Workspace (DRY: uses native AudioPlayer component) -->
        <div v-else-if="isAudio" class="flex-1 flex flex-col items-center justify-center p-8 bg-gray-50 dark:bg-gray-900/50">
          <div class="w-full max-w-xl bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-8 flex flex-col items-center">
            <div class="w-20 h-20 mb-6 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
              <MusicalNoteIcon class="w-10 h-10 text-purple-600 dark:text-purple-400" />
            </div>
            
            <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-2 text-center break-all">{{ artefact?.title }}</h3>
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-6 uppercase tracking-wider font-semibold">{{ audioExtension }} Audio</p>
            
            <div class="w-full mb-6">
              <AudioPlayer v-if="audioUrl" :src="audioUrl" class="w-full" />
            </div>
            
            <div class="flex items-center justify-center space-x-4 w-full">
              <button 
                @click="downloadAudio" 
                class="flex items-center space-x-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-lg transition-colors font-medium text-sm w-full justify-center"
              >
                <ArrowDownTrayIcon class="w-5 h-5" />
                <span>Download Original</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Text/Code Workspace -->
        <div v-else class="flex-1 flex flex-col h-full">
          <div class="flex-1 overflow-auto p-4 sm:p-6 h-full">
            <textarea 
              v-model="editedContent" 
              class="w-full h-full min-h-[400px] p-4 font-mono text-sm bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              placeholder="Enter artefact content..."
              spellcheck="false"
            ></textarea>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 flex items-center justify-between">
        <div class="text-sm text-gray-500 dark:text-gray-400">
          <span v-if="isAudio" class="flex items-center">
            <ExclamationTriangleIcon class="w-4 h-4 mr-1 text-amber-500" />
            Audio files cannot be edited directly.
          </span>
          <span v-else>{{ characterCount }} characters</span>
        </div>
        <div class="flex items-center space-x-3">
          <button 
            @click="closeModal" 
            class="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors font-medium"
          >
            Cancel
          </button>
          <button 
            v-if="!isAudio"
            @click="saveContent" 
            :disabled="isSaving"
            class="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ArrowPathIcon v-if="isSaving" class="w-5 h-5 animate-spin" />
            <CheckIcon v-else class="w-5 h-5" />
            <span>{{ isSaving ? 'Saving...' : 'Save Changes' }}</span>
          </button>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue';
import IconMusicalNote from '@/assets/icons/IconMusicalNote.vue';
import api from '@/services/api';
import { useUiStore } from '@/stores/ui';
import AudioPlayer from '@/components/chat/AudioPlayer.vue'; // Assume existing component path based on tree

const props = defineProps({
  isOpen: { type: Boolean, default: false },
  artefact: { type: Object, default: null }
});

const emit = defineEmits(['close', 'save']);
const uiStore = useUiStore();

// State
const isLoading = ref(false);
const isSaving = ref(false);
const error = ref(null);
const editedContent = ref('');
const audioUrl = ref(null);
const audioBlob = ref(null);

// Constants
const AUDIO_EXTENSIONS = ['mp3', 'wav', 'ogg', 'oga', 'm4a', 'flac', 'webm', 'aac', 'opus'];

// Computed
const audioExtension = computed(() => {
  if (!props.artefact?.title) return '';
  const parts = props.artefact.title.split('.');
  return parts.length > 1 ? parts.pop().toLowerCase() : '';
});

const isAudio = computed(() => {
  if (!props.artefact) return false;
  if (props.artefact.artefact_type === 'audio') return true;
  return AUDIO_EXTENSIONS.includes(audioExtension.value);
});

// Keep AUDIO_EXTENSIONS and detection aligned with backend AUDIO_EXTENSIONS.

const characterCount = computed(() => {
  return editedContent.value ? editedContent.value.length : 0;
});

// Methods
const loadContent = async () => {
  if (!props.artefact) return;
  
  isLoading.value = true;
  error.value = null;
  
  try {
    if (isAudio.value) {
      // Fetch as blob for audio playback
      const response = await api.get(`/api/discussions/${props.artefact.discussion_id}/artefacts/${props.artefact.title}/content`, {
        responseType: 'blob'
      });
      audioBlob.value = response.data;
      audioUrl.value = URL.createObjectURL(response.data);
    } else {
      // Fetch as text for editing
      const response = await api.get(`/api/discussions/${props.artefact.discussion_id}/artefacts/${props.artefact.title}/content`);
      editedContent.value = response.data.content || '';
    }
  } catch (err) {
    console.error('Failed to load artefact:', err);
    error.value = err.response?.data?.detail || 'Could not load the artefact content. Please try again.';
  } finally {
    isLoading.value = false;
  }
};

const saveContent = async () => {
  if (isAudio.value) return; // Guard: Prevent saving binary as text
  
  isSaving.value = true;
  try {
    await api.put(`/api/discussions/${props.artefact.discussion_id}/artefacts/${props.artefact.title}`, {
      content: editedContent.value
    });
    uiStore.showToast('Artefact saved successfully', 'success');
    emit('save', { ...props.artefact, content: editedContent.value });
    closeModal();
  } catch (err) {
    console.error('Failed to save artefact:', err);
    uiStore.showToast(err.response?.data?.detail || 'Failed to save artefact', 'error');
  } finally {
    isSaving.value = false;
  }
};

const downloadAudio = () => {
  if (!audioBlob.value || !props.artefact) return;
  
  const url = window.URL.createObjectURL(audioBlob.value);
  const a = document.createElement('a');
  a.href = url;
  a.download = props.artefact.title;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
};

const closeModal = () => {
  emit('close');
};

// Watchers
watch(() => props.isOpen, (newVal) => {
  if (newVal && props.artefact) {
    loadContent();
  } else {
    // Cleanup on close
    if (audioUrl.value) {
      URL.revokeObjectURL(audioUrl.value);
      audioUrl.value = null;
      audioBlob.value = null;
    }
    editedContent.value = '';
    error.value = null;
  }
});

// Cleanup
onUnmounted(() => {
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value);
  }
});
</script>