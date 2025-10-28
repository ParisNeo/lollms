<template>
  <GenericModal modal-name="enhancePrompt" title="Enhance Prompt" max-width-class="max-w-lg">
    <template #body>
      <div class="space-y-4">
        <div>
          <label for="enhancement-instructions" class="block text-sm font-medium">Instructions</label>
          <textarea id="enhancement-instructions" v-model="instructions" rows="3" class="input-field mt-1" placeholder="Optional: Guide the AI... e.g., 'make it more cinematic' or 'change the car to red'"></textarea>
        </div>
        <div>
          <label for="enhancement-mode" class="block text-sm font-medium">Enhancement Mode</label>
          <select id="enhancement-mode" v-model="mode" class="input-field mt-1">
            <option value="description">Full Description</option>
            <option value="update">Update Instructions</option>
          </select>
          <p class="text-xs text-gray-500 mt-1">
            <b>Full Description:</b> Re-writes the prompt with more detail.<br>
            <b>Update Instructions:</b> Treats your prompt as instructions to change an image.
          </p>
        </div>
      </div>
    </template>
    <template #footer>
      <button @click="uiStore.closeModal('enhancePrompt')" type="button" class="btn btn-secondary">Cancel</button>
      <button @click="handleConfirm" type="button" class="btn btn-primary">Enhance</button>
    </template>
  </GenericModal>
</template>

<script setup>
import { ref, watch, computed } from 'vue';
import GenericModal from './GenericModal.vue';
import { useUiStore } from '../../stores/ui';

const uiStore = useUiStore();
const modalProps = computed(() => uiStore.modalData('enhancePrompt'));

const instructions = ref('');
const mode = ref('description');

watch(modalProps, (props) => {
  if (props) {
    instructions.value = props.instructions || '';
    mode.value = props.mode || 'description';
  }
}, { immediate: true });

function handleConfirm() {
  if (modalProps.value?.onConfirm) {
    modalProps.value.onConfirm({
      instructions: instructions.value,
      mode: mode.value
    });
  }
  uiStore.closeModal('enhancePrompt');
}
</script>