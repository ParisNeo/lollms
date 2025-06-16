<script setup>
import { ref, computed, watch, nextTick } from 'vue';

const props = defineProps({
  items: {
    type: Array, // Expects [{ id, name, icon_base64, isGroup, label, items }]
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
const triggerRef = ref(null); // Ref for the trigger element (slot)
const menuStyle = ref({}); // For dynamic positioning

const selectedItem = computed(() => {
    for (const item of props.items) {
        if (item.isGroup) {
            const found = item.items.find(subItem => subItem.id === props.modelValue);
            if (found) return found;
        } else {
            if (item.id === props.modelValue) return item;
        }
    }
    return null;
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

function selectOption(optionId) {
    emit('update:modelValue', optionId);
    isOpen.value = false;
}

// v-on-click-outside directive to close the dropdown
const vOnClickOutside = {
  mounted: (el, binding) => {
    el.__vueClickOutside__ = event => {
      // Check if the click is outside the trigger AND the teleported menu
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
    <slot name="button" :toggle="() => isOpen = !isOpen" :selected-item="selectedItem" />
    
    <!-- Dropdown Panel Teleported to Body -->
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
            <li @click="selectOption(null)" class="text-gray-900 dark:text-gray-100 cursor-pointer select-none relative py-2 pl-3 pr-9 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700">
              <span class="block truncate" :class="{'font-semibold': !modelValue}">{{ placeholder }}</span>
            </li>

            <template v-for="(item, index) in items" :key="index">
              <div v-if="item.isGroup" class="pt-2">
                  <div class="px-3 py-1 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
                      {{ item.label }}
                  </div>
                  <li v-for="subItem in item.items" :key="subItem.id" @click="selectOption(subItem.id)" class="text-gray-900 dark:text-gray-100 cursor-pointer select-none relative py-2 pl-3 pr-9 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700">
                      <div class="flex items-center space-x-2">
                          <img v-if="subItem.icon_base64" :src="subItem.icon_base64" class="h-6 w-6 rounded-md object-cover flex-shrink-0"/>
                          <div v-else class="h-6 w-6 rounded-md bg-gray-200 dark:bg-gray-600 flex-shrink-0"></div>
                          <span class="font-normal block truncate" :class="{'font-semibold': subItem.id === modelValue}">{{ subItem.name }}</span>
                      </div>
                  </li>
              </div>
              <li v-else @click="selectOption(item.id)" class="text-gray-900 dark:text-gray-100 cursor-pointer select-none relative py-2 pl-3 pr-9 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700">
                <div class="flex items-center space-x-2">
                  <img v-if="item.icon_base64" :src="item.icon_base64" class="h-6 w-6 rounded-md object-cover flex-shrink-0"/>
                  <div v-else class="h-6 w-6 rounded-md bg-gray-200 dark:bg-gray-600 flex-shrink-0"></div>
                  <span class="font-normal block truncate" :class="{'font-semibold': item.id === modelValue}">{{ item.name }}</span>
                </div>
              </li>
            </template>
          </ul>
          <div v-if="$slots.footer" class="border-t border-gray-200 dark:border-gray-700">
              <slot name="footer"></slot>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>