<template>
  <div class="w-full flex items-center gap-2">
    <div v-if="isLoading" class="flex-grow h-8 bg-gray-200 dark:bg-gray-700 animate-pulse rounded-lg flex items-center px-4">
        <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Loading Audio...</span>
    </div>
    <audio 
        v-else-if="audioUrl && !error" 
        ref="audioRef"
        controls 
        :src="audioUrl" 
        class="w-full h-8"
        @error="handleAudioError"
    ></audio>
    <div v-else class="flex-grow h-8 bg-red-50 dark:bg-red-900/20 rounded-lg flex items-center px-4 border border-red-200 dark:border-red-800">
        <span class="text-[10px] font-bold text-red-500 uppercase tracking-widest">
            {{ error ? 'Audio Access Error' : 'No Audio Data' }}
        </span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue';
import apiClient from '../../services/api';

const props = defineProps({
  src: { type: String, required: true }
});

const audioUrl = ref(null);
const isLoading = ref(true);
const error = ref(false);
const audioRef = ref(null);

let objectUrl = null;

async function fetchAudio() {
  if (!props.src) {
    isLoading.value = false;
    return;
  }

  isLoading.value = true;
  error.value = false;

  // Cleanup old URL to prevent memory leaks
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  }

  try {
    // We use the authenticated apiClient which includes the Authorization header
    const response = await apiClient.get(props.src, { 
        responseType: 'blob',
        timeout: 30000 // Audio files can be large
    });
    
    objectUrl = URL.createObjectURL(response.data);
    audioUrl.value = objectUrl;
  } catch (e) {
    console.error("Failed to fetch authenticated audio:", e);
    error.value = true;
  } finally {
    isLoading.value = false;
  }
}

function handleAudioError(e) {
    console.error("Audio playback error:", e);
    error.value = true;
}

watch(() => props.src, fetchAudio);

onMounted(fetchAudio);

onUnmounted(() => {
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
  }
});
</script>

<style scoped>
/* Ensure the native audio player fits the container style */
audio::-webkit-media-controls-panel {
    background-color: transparent;
}
</style>
