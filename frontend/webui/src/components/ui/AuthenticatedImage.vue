<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue';
import { useAuthStore } from '../../stores/auth';

const props = defineProps({
  src: {
    type: String,
    required: true
  },
  alt: String,
  class: String,
});

const authStore = useAuthStore();
const imageSrc = ref(null);
const isLoading = ref(true);
const hasError = ref(false);

let blobUrl = null;

async function fetchImage() {
  if (!props.src) {
    hasError.value = true;
    isLoading.value = false;
    return;
  }
  
  // Directly use non-relative URLs (like http, https, data:, blob:)
  if (!props.src.startsWith('/')) {
    imageSrc.value = props.src;
    isLoading.value = false;
    return;
  }

  isLoading.value = true;
  hasError.value = false;
  
  try {
    const response = await fetch(props.src, {
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch image: ${response.statusText}`);
    }

    const blob = await response.blob();
    
    // Revoke the old blob URL if it exists to prevent memory leaks
    if (blobUrl) {
      URL.revokeObjectURL(blobUrl);
    }
    
    blobUrl = URL.createObjectURL(blob);
    imageSrc.value = blobUrl;

  } catch (error) {
    console.error(`Could not load authenticated image from ${props.src}:`, error);
    hasError.value = true;
  } finally {
    isLoading.value = false;
  }
}

// Fetch the image when the component is mounted or the src prop changes
onMounted(fetchImage);
watch(() => props.src, fetchImage);

// Clean up the blob URL when the component is unmounted
onUnmounted(() => {
    if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
    }
});
</script>

<template>
  <div class="w-full h-full flex items-center justify-center bg-gray-200 dark:bg-gray-700" :class="props.class">
    <div v-if="isLoading" class="animate-pulse w-full h-full bg-gray-300 dark:bg-gray-600 rounded"></div>
    <img v-else-if="!hasError && imageSrc" :src="imageSrc" :alt="alt" :class="props.class" />
    <div v-else class="text-red-500/70 dark:text-red-400/70 p-2 text-center flex flex-col items-center justify-center">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v12a1.5 1.5 0 0 0 1.5 1.5Zm10.5-11.25h.008v.008h-.008V8.25Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
      </svg>
      <span class="text-xs mt-1 block font-semibold">Load Failed</span>
    </div>
  </div>
</template>