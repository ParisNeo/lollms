<script setup>
import { computed, ref, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';

const uiStore = useUiStore();
const options = computed(() => uiStore.confirmationOptions);
const localInputValue = ref('');

watch(() => options.value.inputValue, (newValue) => {
    localInputValue.value = newValue;
}, { immediate: true });

function handleConfirm() {
    let valueToReturn = true;
    if (options.value.inputType) {
        valueToReturn = localInputValue.value;
    }
    uiStore.confirmAction(valueToReturn);
}
</script>

<template>
  <GenericModal
    modalName="confirmation"
    :title="options.title"
    maxWidthClass="max-w-md"
  >
    <template #body>
      <p class="text-sm text-gray-600 dark:text-gray-300">{{ options.message }}</p>

      <div v-if="options.inputType" class="mt-4">
          <select v-if="options.inputType === 'select'" v-model="localInputValue" class="input-field w-full">
              <option v-for="option in options.inputOptions" :key="option.value" :value="option.value">
                  {{ option.text }}
              </option>
          </select>

          <input v-else v-model="localInputValue" :type="options.inputType" class="input-field w-full" />
      </div>
    </template>
    <template #footer>
      <button @click="uiStore.cancelAction" type="button" class="btn btn-secondary">
        Cancel
      </button>
      <button @click="handleConfirm" type="button" class="btn btn-primary">
        {{ options.confirmText }}
      </button>
    </template>
  </GenericModal>
</template>