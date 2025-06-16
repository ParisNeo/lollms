<script setup>
import { ref, computed, watch } from 'vue';

const props = defineProps({
  items: {
    type: Array,
    default: () => [] // Expects [{id: '..', name: '...'}, {isGroup: true, label: '..', items: [...]}]
  },
  placeholder: {
    type: String,
    default: 'Select items...'
  },
  modelValue: { // Use v-model for two-way data binding
    type: Array,
    default: () => []
  },
  buttonClass: {
    type: String,
    default: ''
  },
  activeClass: {
    type: String,
    default: 'btn-primary'
  },
  inactiveClass: {
    type: String,
    default: 'btn-secondary'
  }
});

const emit = defineEmits(['update:modelValue']);

const isOpen = ref(false);
const selected = ref([...props.modelValue]);

watch(() => props.modelValue, (newValue) => {
    selected.value = [...newValue];
});

const selectionText = computed(() => {
  if (selected.value.length === 0) {
    return props.placeholder;
  }
  return `${props.placeholder} (${selected.value.length})`;
});

const isSelected = (itemId) => {
  return selected.value.includes(itemId);
};

const toggleItem = (itemId) => {
  const index = selected.value.indexOf(itemId);
  if (index > -1) {
    selected.value.splice(index, 1);
  } else {
    selected.value.push(itemId);
  }
  emit('update:modelValue', selected.value);
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
  <div class="relative w-full" v-on-click-outside="() => isOpen = false">
    <button 
      @click="isOpen = !isOpen" 
      class="w-full btn !justify-start !text-left !font-normal"
      :class="[buttonClass, selected.length > 0 ? activeClass : inactiveClass]"
    >
      <span class="truncate">{{ selectionText }}</span>
      <svg class="absolute right-2 top-1/2 -mt-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
    </button>
    <div v-if="isOpen" class="absolute bottom-full mb-2 w-full bg-white dark:bg-gray-800 shadow-lg rounded-md border border-gray-300 dark:border-gray-600 max-h-60 overflow-y-auto z-10">
      <ul v-if="items.length > 0">
        <template v-for="(item, index) in items" :key="index">
            <!-- Render as a group header -->
            <li v-if="item.isGroup" class="px-3 py-1.5 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400 sticky top-0 bg-gray-50 dark:bg-gray-700">
                {{ item.label }}
            </li>
            <!-- Render a normal item -->
            <li v-else @click="toggleItem(item.id)" class="px-3 py-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center">
              <input type="checkbox" :checked="isSelected(item.id)" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 mr-3 pointer-events-none">
              <span class="text-sm text-gray-900 dark:text-gray-100">{{ item.name }}</span>
            </li>
            <!-- Render items inside a group -->
            <li v-if="item.isGroup" v-for="subItem in item.items" :key="subItem.id" @click="toggleItem(subItem.id)" class="px-3 py-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center pl-6">
                <input type="checkbox" :checked="isSelected(subItem.id)" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 mr-3 pointer-events-none">
                <span class="text-sm text-gray-900 dark:text-gray-100">{{ subItem.name }}</span>
            </li>
        </template>
      </ul>
      <div v-else class="px-3 py-2 text-sm text-gray-500 italic">
        No items available.
      </div>
    </div>
  </div>
</template>