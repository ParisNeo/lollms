<script setup>
import { ref, watch, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import placeholderParser from '../../services/placeholderParser';
import GenericModal from './GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';

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
                initialValues[p.name] = p.default === 'true' || p.default === true;
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
    const originalTemplate = modalData.value.promptTemplate;
    let filledTemplate = placeholderParser.clean(originalTemplate);

    placeholders.value.forEach(p => {
        const value = formValues.value[p.name] !== undefined ? formValues.value[p.name] : (p.default || '');
        const escapedName = p.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

        // Replace @<name>@
        const atRegex = new RegExp(`@<${escapedName}>@`, 'g');
        filledTemplate = filledTemplate.replace(atRegex, String(value));

        // Replace {{name}} and {{ name }}
        const curlyRegex = new RegExp(`\\{\\{\\s*${escapedName}\\s*\\}\\}`, 'g');
        filledTemplate = filledTemplate.replace(curlyRegex, String(value));
    });

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
    title="Fill Prompt Placeholders"
    maxWidthClass="max-w-2xl"
    @close="handleClose"
  >
    <template #body>
      <div v-if="placeholders.length > 0" class="space-y-5 p-1">
        <div class="flex items-center gap-2 p-3 bg-blue-50 dark:bg-blue-950/30 rounded-xl border border-blue-200 dark:border-blue-800/60 text-xs text-blue-900 dark:text-blue-200">
          <IconSparkles class="w-4 h-4 text-blue-500 shrink-0" />
          <span>Complete the parameters below to configure your prompt values.</span>
        </div>

        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div v-for="placeholder in placeholders" :key="placeholder.name" class="space-y-1.5 p-3.5 bg-gray-50 dark:bg-gray-900/50 rounded-xl border border-gray-150 dark:border-gray-800">
            <div class="flex justify-between items-baseline">
              <label :for="`placeholder-${placeholder.name}`" class="block text-xs font-black uppercase tracking-wide text-gray-700 dark:text-gray-300">
                {{ placeholder.title }}
              </label>
              <span class="font-mono text-[10px] text-gray-400">@&lt;{{ placeholder.name }}&gt;@</span>
            </div>
            
            <p v-if="placeholder.help" class="text-[11px] text-gray-500 dark:text-gray-400 italic mb-1">{{ placeholder.help }}</p>

            <!-- Dropdown Select -->
            <select
              v-if="placeholder.options && placeholder.options.length > 0"
              :id="`placeholder-${placeholder.name}`"
              v-model="formValues[placeholder.name]"
              class="input-field text-xs w-full"
            >
              <option v-for="option in placeholder.options" :key="option" :value="option">
                {{ option }}
              </option>
            </select>

            <!-- Checkbox for Boolean -->
            <div v-else-if="placeholder.type === 'bool'" class="mt-2 flex items-center gap-2">
              <input
                :id="`placeholder-${placeholder.name}`"
                type="checkbox"
                v-model="formValues[placeholder.name]"
                class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <label :for="`placeholder-${placeholder.name}`" class="text-xs font-semibold text-gray-800 dark:text-gray-200 cursor-pointer">
                Enable option
              </label>
            </div>

            <!-- CodeMirror Editor for 'text' type -->
            <div v-else-if="placeholder.type === 'text'" class="border dark:border-gray-700 rounded-xl overflow-hidden h-40">
              <CodeMirrorEditor
                :id="`placeholder-${placeholder.name}`"
                v-model="formValues[placeholder.name]"
                class="h-full"
                placeholder="Enter multiline text or paste content..."
              />
            </div>

            <!-- Input for other types (str, int, float) -->
            <input
              v-else
              :type="placeholder.type === 'int' || placeholder.type === 'float' ? 'number' : 'text'"
              :step="placeholder.type === 'float' ? 'any' : (placeholder.type === 'int' ? '1' : undefined)"
              :id="`placeholder-${placeholder.name}`"
              v-model="formValues[placeholder.name]"
              class="input-field text-xs w-full"
              :placeholder="`Enter ${placeholder.title.toLowerCase()}...`"
            />
          </div>
        </form>
      </div>

      <div v-else class="text-center text-xs text-gray-500 py-6">
        No placeholders were found in this prompt.
      </div>
    </template>

    <template #footer>
      <div class="flex justify-end gap-2 w-full">
        <button @click="handleClose" type="button" class="btn btn-secondary text-xs">
          Cancel
        </button>
        <button @click="handleSubmit" type="button" class="btn btn-primary text-xs px-5 shadow-sm">
          Confirm & Apply
        </button>
      </div>
    </template>
  </GenericModal>
</template>

<style scoped>
@reference "tailwindcss";
</style>