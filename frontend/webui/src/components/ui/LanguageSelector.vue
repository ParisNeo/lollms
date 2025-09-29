<!-- [CREATE] frontend/webui/src/components/ui/LanguageSelector.vue -->
<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useDataStore } from '../../stores/data';
import { useFloating, offset, flip, shift, autoUpdate } from '@floating-ui/vue';

const props = defineProps({
  modelValue: {
    type: String,
    default: 'auto'
  },
  includeAuto: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:modelValue']);

const dataStore = useDataStore();
const languages = computed(() => dataStore.languages);
const isLoading = computed(() => dataStore.isLoadingLanguages);

const isOpen = ref(false);
const triggerRef = ref(null);
const floatingRef = ref(null);
const search = ref('');

const { floatingStyles } = useFloating(triggerRef, floatingRef, {
  placement: 'bottom-start',
  whileElementsMounted: autoUpdate,
  middleware: [offset(5), flip(), shift({ padding: 5 })],
});

const vOnClickOutside = {
  mounted: (el, binding) => {
    el.clickOutsideEvent = event => {
      const triggerEl = triggerRef.value;
      if (!(el === event.target || el.contains(event.target) || triggerEl?.contains(event.target))) {
        binding.value();
      }
    };
    document.addEventListener('mousedown', el.clickOutsideEvent);
  },
  unmounted: el => {
    document.removeEventListener('mousedown', el.clickOutsideEvent);
  },
};

const allOptions = computed(() => {
    const options = [...languages.value];
    if (props.includeAuto) {
        options.unshift({ value: 'auto', label: 'Auto-detect' });
    }
    return options;
});

const selectedLanguage = computed(() => {
  return allOptions.value.find(lang => lang.value === props.modelValue) || null;
});

const filteredLanguages = computed(() => {
  if (!search.value) return allOptions.value;
  const lowerSearch = search.value.toLowerCase();
  return allOptions.value.filter(lang => 
    lang.label.toLowerCase().includes(lowerSearch) || 
    lang.value.toLowerCase().includes(lowerSearch)
  );
});

function selectLanguage(value) {
  emit('update:modelValue', value);
  isOpen.value = false;
  search.value = '';
}

onMounted(() => {
    if (languages.value.length === 0) {
        dataStore.fetchLanguages();
    }
});
</script>

<template>
  <div class="relative w-full">
    <button
      ref="triggerRef"
      @click="isOpen = !isOpen"
      type="button"
      class="input-field flex items-center justify-between"
    >
      <span class="truncate">{{ selectedLanguage ? selectedLanguage.label : 'Select Language' }}</span>
      <svg class="w-4 h-4 text-gray-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
    </button>
    <Teleport to="body">
      <Transition
        enter-active-class="transition ease-out duration-100"
        enter-from-class="transform opacity-0 scale-95"
        enter-to-class="transform opacity-100 scale-100"
        leave-active-class="transition ease-in duration-75"
        leave-from-class="transform opacity-100 scale-100"
        leave-to-class="transform opacity-0 scale-95"
      >
        <div
          v-if="isOpen"
          ref="floatingRef"
          :style="floatingStyles"
          v-on-click-outside="() => isOpen = false"
          class="z-50 w-64 origin-top-left rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 dark:ring-gray-700 focus:outline-none flex flex-col max-h-[50vh]"
        >
          <div class="p-2 border-b dark:border-gray-700">
            <input
              v-model="search"
              type="text"
              placeholder="Search language..."
              class="input-field-sm w-full"
            />
          </div>
          <div class="flex-grow overflow-y-auto">
            <div v-if="isLoading" class="p-4 text-center text-sm text-gray-500">Loading...</div>
            <div v-else-if="filteredLanguages.length === 0" class="p-4 text-center text-sm text-gray-500">No matches found.</div>
            <ul v-else class="py-1">
              <li
                v-for="lang in filteredLanguages"
                :key="lang.value"
                @click="selectLanguage(lang.value)"
                class="px-3 py-2 text-sm cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700"
                :class="{'bg-blue-100 dark:bg-blue-900/50 font-semibold': modelValue === lang.value}"
              >
                {{ lang.label }}
              </li>
            </ul>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>