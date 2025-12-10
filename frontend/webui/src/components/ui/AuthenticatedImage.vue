<template>
  <div class="w-full h-full flex items-center justify-center bg-gray-200 dark:bg-gray-700">
    <div v-if="isLoading" class="w-full h-full animate-pulse bg-gray-300 dark:bg-gray-600"></div>
    <img v-else-if="imageUrl && !error" :src="imageUrl" :alt="alt" @load="$emit('load', $event)" class="w-full h-full object-contain" />
    <div v-else class="text-xs text-gray-500 dark:text-gray-400 p-2 text-center">
      Image Error
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue';
import apiClient from '../../services/api';

const props = defineProps({
  src: { type: String, required: true },
  alt: { type: String, default: 'Authenticated image' }
});
defineEmits(['load']);

const imageUrl = ref(null);
const isLoading = ref(true);
const error = ref(false);

let objectUrl = null;

async function fetchImage() {
  if (!props.src) return;

  if (props.src.startsWith('data:image/')) {
      imageUrl.value = props.src;
      isLoading.value = false;
      error.value = false;
      return;
  }

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
    // console.error(`Failed to load authenticated image from ${props.src}`, e);
    // Suppress console error for 404/401 to keep logs clean, just show UI error
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
