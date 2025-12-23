<script setup>
import { computed, ref, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../modals/GenericModal.vue';

const uiStore = useUiStore();
const options = computed(() => uiStore.confirmationOptions);
const localInputValue = ref('');

watch(() => options.value.inputValue, (newValue) => {
    localInputValue.value = newValue || '';
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
    :title="options.title || 'Are you sure?'"
    :allowOverlayClose="false"
    maxWidthClass="max-w-md"
  >
    <template #body>
      <div class="text-sm text-gray-700 dark:text-gray-300">
        <p>{{ options.message }}</p>
      </div>

      <div v-if="options.inputType" class="mt-4">
          <select v-if="options.inputType === 'select'" v-model="localInputValue" class="input-field w-full">
              <option v-for="option in options.inputOptions" :key="option.value" :value="option.value">
                  {{ option.text }}
              </option>
          </select>

          <input 
            v-else 
            v-model="localInputValue" 
            :type="options.inputType" 
            :placeholder="options.inputPlaceholder"
            class="input-field w-full"
            @keyup.enter="handleConfirm"
          />
      </div>
    </template>
    <template #footer>
      <button @click="uiStore.cancelAction" class="btn btn-secondary">
        {{ options.cancelText || 'Cancel' }}
      </button>
      <button @click="handleConfirm" class="btn btn-primary">
        {{ options.confirmText || 'Confirm' }}
      </button>
    </template>
  </GenericModal>
</template>
