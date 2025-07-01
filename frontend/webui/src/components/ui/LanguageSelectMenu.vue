<script setup>
import { ref } from 'vue';

const props = defineProps({
  languageGroups: {
    type: Array, // Expects [{ label, isGroup, items: [{ id, name, icon }] }]
    required: true
  }
});

const emit = defineEmits(['select-language']);

const isOpen = ref(false);

function selectLanguage(langId) {
  if (langId) {
    emit('select-language', langId);
  }
  isOpen.value = false;
}

// v-on-click-outside directive to close the dropdown
const vOnClickOutside = {
  mounted: (el, binding) => {
    el.__vueClickOutside__ = event => {
      if (!(el === event.target || el.contains(event.target))) {
        binding.value(event);
      }
    };
    document.body.addEventListener('click', el.__vueClickOutside__);
  },
  unmounted: (el) => {
    document.body.removeEventListener('click', el.__vueClickOutside__);
  }
};
</script>

<template>
  <div class="relative" v-on-click-outside="() => isOpen = false">
    <!-- Trigger Button -->
    <button @click="isOpen = !isOpen" title="Insert Code Block" class="toolbar-btn">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l-4 4-4-4M6 16l-4-4 4-4"/></svg>
    </button>

    <!-- Dropdown Panel -->
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
        class="absolute top-full left-0 mt-2 w-48 origin-top-left rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none z-20"
      >
        <div class="p-1">
          <ul class="max-h-72 overflow-y-auto">
            <li @click="selectLanguage('')" class="flex items-center space-x-2 text-gray-900 dark:text-gray-100 cursor-pointer select-none relative p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l-4 4-4-4M6 16l-4-4 4-4"/></svg>
                <span class="font-normal block truncate">Generic Code Block</span>
            </li>
            <template v-for="(group, index) in languageGroups" :key="index">
              <div v-if="group.isGroup" class="pt-2">
                <div class="px-2 py-1 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
                  {{ group.label }}
                </div>
                <li v-for="lang in group.items" :key="lang.id" @click="selectLanguage(lang.id)" class="flex items-center space-x-2 text-gray-900 dark:text-gray-100 cursor-pointer select-none relative p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700">
                    <span class="h-4 w-4 flex-shrink-0" v-html="lang.icon"></span>
                    <span class="font-normal block truncate">{{ lang.name }}</span>
                </li>
              </div>
            </template>
          </ul>
        </div>
      </div>
    </Transition>
  </div>
</template>