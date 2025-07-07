<script setup>
import { ref, computed, watch } from 'vue';

const props = defineProps({
  modelValue: {
    type: [String, null],
    default: null
  },
  items: {
    type: Array,
    required: true
  },
  label: {
    type: String,
    required: true
  },
  iconSvg: {
    type: String,
    required: true
  },
  placeholder: {
    type: String,
    default: 'Select an option'
  }
});

const emit = defineEmits(['update:modelValue']);

const isOpen = ref(false);
const searchTerm = ref('');

const allItemsFlat = computed(() => {
    const flatList = [];
    props.items.forEach(item => {
        if (item.isGroup || item.label) { // Handle grouped items
            (item.options || item.items).forEach(subItem => {
                flatList.push(subItem);
            });
        } else { // Handle flat list of strings or objects
            if (typeof item === 'string') {
                flatList.push({ id: item, name: item });
            } else {
                flatList.push(item);
            }
        }
    });
    return flatList;
});

const selectedItem = computed(() => {
  if (!props.modelValue) return null;
  return allItemsFlat.value.find(i => i.id === props.modelValue || i.name === props.modelValue);
});

const selectedItemName = computed(() => {
    return selectedItem.value ? selectedItem.value.name : props.placeholder;
});

const filteredItems = computed(() => {
    if (!searchTerm.value) {
        return props.items;
    }
    const lowerSearchTerm = searchTerm.value.toLowerCase();

    // If items are grouped
    if (props.items.some(i => i.isGroup || i.label)) {
        return props.items.map(group => {
            const filteredOptions = (group.options || group.items).filter(option =>
                option.name.toLowerCase().includes(lowerSearchTerm)
            );
            return { ...group, options: filteredOptions, items: filteredOptions };
        }).filter(group => (group.options || group.items).length > 0);
    }

    // If items are a flat list
    return allItemsFlat.value.filter(item =>
        item.name.toLowerCase().includes(lowerSearchTerm)
    );
});

function toggleMenu() {
  isOpen.value = !isOpen.value;
  if (!isOpen.value) {
    searchTerm.value = ''; // Reset search on close
  }
}

function selectItem(item) {
    const valueToEmit = item.id || item.name; // Use ID if available, otherwise name
    emit('update:modelValue', valueToEmit);
    isOpen.value = false;
    searchTerm.value = '';
}

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
    <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ label }}</label>
    <button @click="toggleMenu" class="selector-button">
      <span class="selector-icon" v-html="iconSvg"></span>
      <span class="truncate">{{ selectedItemName }}</span>
      <svg class="w-4 h-4 ml-auto text-gray-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
    </button>

    <transition enter-active-class="transition ease-out duration-100" enter-from-class="transform opacity-0 scale-95" enter-to-class="transform opacity-100 scale-100" leave-active-class="transition ease-in duration-75" leave-from-class="transform opacity-100 scale-100" leave-to-class="transform opacity-0 scale-95">
      <div v-if="isOpen" class="absolute z-10 mt-1 w-full bg-white dark:bg-gray-800 shadow-lg rounded-md border border-gray-200 dark:border-gray-700">
        <div class="p-2">
          <input type="text" v-model="searchTerm" placeholder="Search..." class="w-full px-2 py-1.5 text-sm border-gray-300 dark:border-gray-600 dark:bg-gray-900 rounded-md focus:ring-blue-500 focus:border-blue-500">
        </div>
        <ul class="max-h-60 overflow-y-auto py-1">
          <!-- Handle Flat List -->
          <template v-if="!items.some(i => i.isGroup || i.label)">
             <li v-for="item in filteredItems" :key="item.id || item.name" @click="selectItem(item)" class="menu-item" :class="{'is-selected': modelValue === (item.id || item.name)}">
                {{ item.name }}
              </li>
          </template>
          <!-- Handle Grouped List -->
          <template v-else>
            <li @click="selectItem({id: null, name: placeholder})" class="menu-item" :class="{'is-selected': modelValue === null}">
                {{ placeholder }}
            </li>
            <template v-for="group in filteredItems" :key="group.label">
              <li class="px-3 py-1.5 text-xs font-bold uppercase text-gray-500 dark:text-gray-400">{{ group.label }}</li>
              <li v-for="option in (group.options || group.items)" :key="option.id" @click="selectItem(option)" class="menu-item pl-6" :class="{'is-selected': modelValue === option.id}">
                {{ option.name }}
              </li>
            </template>
          </template>
           <li v-if="filteredItems.length === 0" class="px-3 py-2 text-sm text-gray-500">No results found.</li>
        </ul>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.selector-button {
  @apply w-full flex items-center gap-x-2 text-left px-2.5 py-2 text-sm bg-gray-100 dark:bg-gray-900/50 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500;
}
.selector-icon {
  @apply w-4 h-4 flex-shrink-0 text-gray-500 dark:text-gray-400;
}
.menu-item {
  @apply px-3 py-1.5 text-sm text-gray-800 dark:text-gray-200 cursor-pointer hover:bg-blue-500 hover:text-white;
}
.menu-item.is-selected {
  @apply bg-blue-600 text-white font-semibold;
}
</style>