<script setup>
import { ref, computed, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';

const uiStore = useUiStore();
const isOpen = ref(false);

onMounted(() => {
    // Fetch languages if they are not already loaded
    if (Object.keys(uiStore.availableLanguages).length === 0) {
        uiStore.fetchLanguages();
    }
});

const currentLanguageLabel = computed(() => {
  // Defensive check to prevent crash if currentLanguage is not yet set
  return (uiStore.currentLanguage || 'EN').toUpperCase();
});

const handleLanguageSelect = (langCode) => {
  uiStore.setLanguage(langCode);
  isOpen.value = false;
};

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
    <button
      @click="isOpen = !isOpen"
      title="Change Language"
      class="flex items-center justify-center h-9 w-9 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors text-sm font-semibold"
    >
      {{ currentLanguageLabel }}
    </button>
    <transition
      enter-active-class="transition ease-out duration-100"
      enter-from-class="transform opacity-0 scale-95"
      enter-to-class="transform opacity-100 scale-100"
      leave-active-class="transition ease-in duration-75"
      leave-from-class="transform opacity-100 scale-100"
      leave-to-class="transform opacity-0 scale-95"
    >
      <div
        v-if="isOpen"
        class="absolute top-full right-0 mt-2 w-40 origin-top-right rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none z-10"
      >
        <div class="py-1">
          <a
            v-for="(name, code) in uiStore.availableLanguages"
            :key="code"
            href="#"
            @click.prevent="handleLanguageSelect(code)"
            class="block px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700"
            :class="{ 'font-bold bg-gray-100 dark:bg-gray-700': code === uiStore.currentLanguage }"
          >
            {{ name }}
          </a>
        </div>
      </div>
    </transition>
  </div>
</template>