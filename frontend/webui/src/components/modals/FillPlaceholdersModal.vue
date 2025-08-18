<script setup>
import { ref, watch, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import placeholderParser from '../../services/placeholderParser';
import GenericModal from '../ui/GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue'; // Import the editor

const uiStore = useUiStore();
const modalData = computed(() => uiStore.modalData('fillPlaceholders'));

const placeholders = ref([]);
const formValues = ref({});

watch(() => modalData.value?.promptTemplate, (newTemplate) => {
    if (newTemplate) {
        const parsed = placeholderParser.parse(newTemplate);
        placeholders.value = parsed;
        
        const initialValues = {};
        parsed.forEach(p => {
            if (p.type === 'bool') {
                initialValues[p.name] = p.default === 'true';
            } else {
                initialValues[p.name] = p.default || '';
            }
        });
        formValues.value = initialValues;
    } else {
        placeholders.value = [];
        formValues.value = {};
    }
}, { immediate: true });

function handleSubmit() {
    // 1. Get the original template from the modal data.
    const originalTemplate = modalData.value.promptTemplate;

    // 2. Use the cleanTemplate function to strip out definition blocks and get the base prompt structure.
    let filledTemplate = placeholderParser.clean(originalTemplate);

    // 3. Iterate through all placeholders and replace their simple form in the cleaned template.
    placeholders.value.forEach(p => {
        const value = formValues.value[p.name];
        // Use a simple regex with a 'g' flag to replace all instances of the placeholder.
        const simpleRegex = new RegExp(`@<${p.name}>@`, 'g');
        filledTemplate = filledTemplate.replace(simpleRegex, String(value));
    });

    // 4. Call the confirmation callback with the correctly constructed prompt.
    if (modalData.value?.onConfirm) {
        modalData.value.onConfirm(filledTemplate);
    }
    handleClose();
}

function handleClose() {
    uiStore.closeModal('fillPlaceholders');
}
</script>

<template>
  <GenericModal
    modalName="fillPlaceholders"
    title="Fill in Prompt Details"
    maxWidthClass="max-w-2xl"
    @close="handleClose"
  >
    <template #body>
      <form v-if="placeholders.length > 0" @submit.prevent="handleSubmit" class="space-y-4">
        <div v-for="placeholder in placeholders" :key="placeholder.name">
          <label :for="`placeholder-${placeholder.name}`" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
            {{ placeholder.title }}
          </label>
          <p v-if="placeholder.help" class="text-xs text-gray-500 mb-1">{{ placeholder.help }}</p>

          <!-- Dropdown Select -->
          <select
            v-if="placeholder.options && placeholder.options.length > 0"
            :id="`placeholder-${placeholder.name}`"
            v-model="formValues[placeholder.name]"
            class="input-field mt-1"
          >
            <option v-for="option in placeholder.options" :key="option" :value="option">
              {{ option }}
            </option>
          </select>

          <!-- Checkbox for Boolean -->
          <div v-else-if="placeholder.type === 'bool'" class="mt-2 flex items-center">
            <input
              :id="`placeholder-${placeholder.name}`"
              type="checkbox"
              v-model="formValues[placeholder.name]"
              class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <label :for="`placeholder-${placeholder.name}`" class="ml-2 block text-sm text-gray-900 dark:text-gray-100">
              Enable
            </label>
          </div>

          <!-- CodeMirror Editor for 'text' type -->
          <CodeMirrorEditor
            v-else-if="placeholder.type === 'text'"
            :id="`placeholder-${placeholder.name}`"
            v-model="formValues[placeholder.name]"
            class="mt-1 h-40"
          />

          <!-- Input for other types (str, int, float) -->
          <input
            v-else
            :type="placeholder.type === 'int' || placeholder.type === 'float' ? 'number' : 'text'"
            :id="`placeholder-${placeholder.name}`"
            v-model="formValues[placeholder.name]"
            class="input-field mt-1"
          />
        </div>
      </form>
      <div v-else class="text-center text-gray-500">
        No placeholders were found in this prompt.
      </div>
    </template>
    <template #footer>
      <button @click="handleClose" type="button" class="btn btn-secondary">
        Cancel
      </button>
      <button @click="handleSubmit" type="button" class="btn btn-primary">
        Confirm
      </button>
    </template>
  </GenericModal>
</template>