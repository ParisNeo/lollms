<script setup>
import { ref, watch, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import apiClient from '../../services/api';

const props = defineProps({
  src: {
    type: String,
    required: true
  },
  alt: {
    type: String,
    default: 'Image'
  }
});

const imageSrc = ref(null);
const isLoading = ref(true);
const hasError = ref(false);

const authStore = useAuthStore();

async function fetchImage() {
  if (!props.src) {
    hasError.value = true;
    isLoading.value = false;
    return;
  }
  
  isLoading.value = true;
  hasError.value = false;
  
  try {
    const response = await apiClient.get(props.src, {
      responseType: 'blob',
    });
    imageSrc.value = URL.createObjectURL(response.data);
  } catch (error) {
    console.error(`Failed to load authenticated image: ${props.src}`, error);
    hasError.value = true;
  } finally {
    isLoading.value = false;
  }
}

// Fetch the image when the component is mounted or the src prop changes.
onMounted(fetchImage);
watch(() => props.src, fetchImage);

</script>

<template>
  <div class="w-full h-full relative bg-gray-200 dark:bg-gray-700/50">
    <!-- Loading Spinner -->
    <div v-if="isLoading" class="absolute inset-0 flex items-center justify-center">
      <svg class="animate-spin h-6 w-6 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
    </div>
    
    <!-- Error State -->
    <div v-else-if="hasError" class="absolute inset-0 flex items-center justify-center text-xs text-red-500">
      Failed to load
    </div>
    
    <!-- Image -->
    <img 
      v-else-if="imageSrc" 
      :src="imageSrc" 
      :alt="alt" 
      class="w-full h-full object-contain transition-opacity duration-300"
      :class="isLoading ? 'opacity-0' : 'opacity-100'"
      @load="() => isLoading = false"
    />
  </div>
</template>