<script setup>
import { ref } from 'vue';
import { useUiStore } from '../../stores/ui';
import IconPhoto from '../../assets/icons/IconPhoto.vue';

const props = defineProps({
  modelValue: {
    type: String,
    default: null
  },
  label: {
    type: String,
    default: 'Icon'
  },
  size: {
    type: Number,
    default: 16 // Corresponds to h-16, w-16
  }
});

const emit = defineEmits(['update:modelValue']);
const uiStore = useUiStore();
const fileInput = ref(null);

function triggerFileUpload() {
  fileInput.value?.click();
}

function handleFileChange(event) {
  const file = event.target.files[0];
  if (!file) return;

  if (!file.type.startsWith('image/')) {
    uiStore.addNotification('Please select a valid image file.', 'warning');
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      canvas.width = 128;
      canvas.height = 128;
      ctx.drawImage(img, 0, 0, 128, 128);
      emit('update:modelValue', canvas.toDataURL('image/png'));
    };
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
}

function removeIcon() {
  emit('update:modelValue', null);
}
</script>

<template>
  <div>
    <label class="label">{{ label }}</label>
    <div class="mt-1 flex items-center gap-4">
      <!-- Preview -->
      <div 
        class="flex-shrink-0 bg-gray-100 dark:bg-gray-700 rounded-lg border border-gray-300 dark:border-gray-600 flex items-center justify-center"
        :class="`h-${size} w-${size}`"
      >
        <img v-if="modelValue" :src="modelValue" alt="Icon preview" class="h-full w-full object-cover rounded-lg">
        <IconPhoto v-else class="text-gray-400" :class="`h-${size/2} w-${size/2}`" />
      </div>

      <!-- Buttons -->
      <div class="space-y-2">
        <input type="file" ref="fileInput" @change="handleFileChange" accept="image/*" class="hidden">
        <button type="button" @click="triggerFileUpload" class="btn btn-secondary text-sm">Upload Image</button>
        <button v-if="modelValue" type="button" @click="removeIcon" class="btn btn-danger-outline text-sm">Remove</button>
      </div>
    </div>
  </div>
</template>