<template>
  <div class="w-full h-full flex items-center justify-center bg-gray-200 dark:bg-gray-700 overflow-hidden relative">
    <div v-if="isLoading" class="absolute inset-0 flex items-center justify-center bg-gray-300 dark:bg-gray-600 animate-pulse"></div>
    <img v-else-if="imageUrl && !error" :src="imageUrl" :alt="alt" @load="$emit('load', $event)" class="w-full h-full" :class="imgClass" />
    <div v-else class="text-xs text-gray-500 dark:text-gray-400 p-2 text-center absolute inset-0 flex items-center justify-center">
      <span v-if="error">Image Error</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue';
import apiClient from '../../services/api';

const props = defineProps({
  src: { type: String, required: true },
  alt: { type: String, default: 'Authenticated image' },
  imgClass: { type: String, default: 'object-contain' } // Allow overriding object-fit
});
defineEmits(['load']);

const imageUrl = ref(null);
const isLoading = ref(true);
const error = ref(false);

let objectUrl = null;

async function fetchImage() {
  if (!props.src) {
    isLoading.value = false;
    return;
  }

  // 1. Handle Blob URLs directly
  if (props.src.startsWith('blob:')) {
      imageUrl.value = props.src;
      isLoading.value = false;
      error.value = false;
      return;
  }

  // 2. Handle Data URIs and sanitize any duplicate prefix headers
  if (props.src.startsWith('data:image/')) {
      let clean = props.src;
      while (clean.startsWith('data:image/png;base64,data:image/') || clean.startsWith('data:image/jpeg;base64,data:image/')) {
          clean = clean.replace(/^data:image\/[a-zA-Z]+;base64,/, '');
      }
      imageUrl.value = clean;
      isLoading.value = false;
      error.value = false;
      return;
  }

  // 3. Handle Raw Base64 Strings (not starting with URL prefixes)
  if (!props.src.startsWith('http://') && !props.src.startsWith('https://') && !props.src.startsWith('/') && !props.src.startsWith('api/')) {
      let cleanB64 = props.src.trim();
      while (cleanB64.startsWith('data:image/')) {
          const commaIdx = cleanB64.indexOf(',');
          if (commaIdx !== -1) cleanB64 = cleanB64.substring(commaIdx + 1);
          else break;
      }
      imageUrl.value = `data:image/png;base64,${cleanB64}`;
      isLoading.value = false;
      error.value = false;
      return;
  }

  // 4. Handle Server / API URLs via authenticated fetch
  isLoading.value = true;
  error.value = false;

  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  }

  try {
    const response = await apiClient.get(props.src, { responseType: 'blob' });
    objectUrl = URL.createObjectURL(response.data);
    imageUrl.value = objectUrl;
  } catch (e) {
    console.error("Failed to load authenticated image:", e);
    error.value = true;
  } finally {
    isLoading.value = false;
  }
}

watch(() => props.src, fetchImage);
onMounted(fetchImage);
onUnmounted(() => {
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
  }
});
</script>
