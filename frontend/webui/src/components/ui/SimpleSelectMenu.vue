<script setup>
import { ref, computed, watch, nextTick } from 'vue';

const props = defineProps({
  items: {
    type: Array, // Expects [{ value, label }]
    default: () => []
  },
  modelValue: { // v-model
    type: [String, Number, null],
    default: null
  },
  placeholder: {
    type: String,
    default: 'Select an option'
  }
});

const emit = defineEmits(['update:modelValue']);

const isOpen = ref(false);
const triggerRef = ref(null);
const menuStyle = ref({});

const selectedItemLabel = computed(() => {
    const selected = props.items.find(item => item.value === props.modelValue);
    return selected ? selected.label : props.placeholder;
});

watch(isOpen, async (isNowOpen) => {
    if (isNowOpen) {
        await nextTick();
        if (triggerRef.value) {
            const rect = triggerRef.value.getBoundingClientRect();
            const menuWidth = 256; // w-64
            let left = rect.left;
            if (rect.left + menuWidth > window.innerWidth) {
                left = rect.right - menuWidth;
            }
            
            menuStyle.value = {
                position: 'absolute',
                top: `${rect.bottom + 4}px`,
                left: `${left}px`,
                minWidth: `${rect.width}px`
            };
        }
    }
});

function selectOption(value) {
    emit('update:modelValue', value);
    isOpen.value = false;
}

// v-on-click-outside directive to close the dropdown
const vOnClickOutside = {
  mounted: (el, binding) => {
    el.__vueClickOutside__ = event => {
      const menuPortal = document.getElementById(`menu-${el.id}`);
      if (
        !el.contains(event.target) &&
        (!menuPortal || !menuPortal.contains(event.target))
      ) {
        binding.value(event);
      }
    };
    document.body.addEventListener('click', el.__vueClickOutside__);
  },
  unmounted: (el) => {
    document.body.removeEventListener('click', el.__vueClickOutside__);
  }
};
const uniqueId = `menu-trigger-${Math.random().toString(36).substr(2, 9)}`;

</script>

<template>
  <div :id="uniqueId" ref="triggerRef" class="relative w-full" v-on-click-outside="() => isOpen = false">
    <!-- Slot for custom button -->
    <slot name="button" :toggle="() => isOpen = !isOpen" :selected-label="selectedItemLabel" />
    
    <!-- Dropdown Panel -->
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
            :id="`menu-${uniqueId}`"
            :style="menuStyle"
            class="w-64 z-[9999] rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5"
        >
          <ul class="max-h-60 overflow-y-auto p-1">
            <li 
              v-for="item in items" 
              :key="item.value" 
              @click="selectOption(item.value)" 
              class="text-gray-900 dark:text-gray-100 cursor-pointer select-none relative py-2 px-3 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              <span class="block truncate" :class="{'font-semibold': item.value === modelValue}">{{ item.label }}</span>
            </li>
            <li v-if="items.length === 0" class="px-3 py-2 text-sm text-gray-500 italic">
              No options available.
            </li>
          </ul>
          <div v-if="$slots.footer" class="border-t border-gray-200 dark:border-gray-700">
              <slot name="footer"></slot>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>