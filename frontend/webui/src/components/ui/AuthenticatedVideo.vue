<template>
  <div class="w-full relative bg-black rounded-2xl overflow-hidden shadow-lg border border-gray-800 group/authvideo">
    <!-- Loading State -->
    <div v-if="isLoading" class="aspect-video flex flex-col items-center justify-center bg-gray-900">
        <IconAnimateSpin class="w-12 h-12 text-blue-500 animate-spin mb-4" />
        <span class="text-xs font-black uppercase tracking-widest text-gray-500">Buffering Secure Media...</span>
    </div>

    <!-- Video Element -->
    <video 
        v-show="!isLoading && videoUrl && !error"
        ref="videoRef"
        controls 
        :src="videoUrl" 
        class="w-full h-full max-h-[600px] object-contain"
        @error="handleVideoError"
    ></video>

    <!-- Error State -->
    <div v-if="error" class="aspect-video flex flex-col items-center justify-center bg-red-950/20 text-red-500 p-6 text-center">
        <IconXMark class="w-12 h-12 mb-4 opacity-50" />
        <p class="font-bold uppercase tracking-tighter">Access Denied or File Missing</p>
        <p class="text-[10px] opacity-70 mt-2">The secure video stream could not be established.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue';
import apiClient from '../../services/api';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';

const props = defineProps({
  src: { type: String, required: true }
});

const videoUrl = ref(null);
const isLoading = ref(true);
const error = ref(false);
const videoRef = ref(null);

let objectUrl = null;

async function fetchVideo() {
  if (!props.src) {
    isLoading.value = false;
    return;
  }

  isLoading.value = true;
  error.value = false;

  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  }

  try {
    const response = await apiClient.get(props.src, { 
        responseType: 'blob',
        // Videos are large, increase timeout to 2 minutes
        timeout: 120000 
    });
    
    objectUrl = URL.createObjectURL(response.data);
    videoUrl.value = objectUrl;
  } catch (e) {
    console.error("Failed to fetch authenticated video:", e);
    error.value = true;
  } finally {
    isLoading.value = false;
  }
}

function handleVideoError(e) {
    console.error("Video playback error:", e);
    error.value = true;
}

watch(() => props.src, fetchVideo);
onMounted(fetchVideo);
onUnmounted(() => {
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
  }
});
</script>
