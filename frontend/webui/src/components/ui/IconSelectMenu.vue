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
const triggerRef = ref(null);
const menuStyle = ref({});

const allItemsFlat = computed(() => {
    return props.items.flatMap(item => (item.isGroup ? item.items : [item]));
});

const selectedItem = computed(() => {
    if (!props.modelValue) return null;
    return allItemsFlat.value.find(i => i.id === props.modelValue) || null;
});

function getBoundingBox() {
    if (triggerRef.value) {
        const rect = triggerRef.value.getBoundingClientRect();
        const menuWidth = 256; // w-64
        let left = rect.left;
        if (rect.left + menuWidth > window.innerWidth) {
            left = rect.right - menuWidth;
        }
        
        menuStyle.value = {
            position: 'fixed',
            top: `${rect.bottom + 4}px`,
            left: `${left}px`,
            minWidth: `${rect.width}px`
        };
    }
}

watch(isOpen, async (isNowOpen) => {
    if (isNowOpen) {
        await nextTick();
        getBoundingBox();
        window.addEventListener('resize', getBoundingBox, { passive: true });
    } else {
        window.removeEventListener('resize', getBoundingBox);
    }
});

function selectOption(optionId) {
    emit('update:modelValue', optionId);
    isOpen.value = false;
}

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
    <slot name="button" :toggle="() => isOpen = !isOpen" :selected-item="selectedItem" />
    
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
            <li @click="selectOption(null)" class="menu-item" :class="{'is-selected': !modelValue}">
              <div class="flex items-center space-x-2">
                <div class="h-6 w-6 rounded-md bg-gray-200 dark:bg-gray-600 flex-shrink-0 flex items-center justify-center">
                    <slot name="placeholder-icon"></slot>
                </div>
                <span class="block truncate">{{ placeholder }}</span>
              </div>
               <span v-if="!modelValue" class="check-mark">
                <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" /></svg>
              </span>
            </li>

            <template v-for="(item, index) in items" :key="index">
              <div v-if="item.isGroup" class="pt-2">
                  <div class="px-3 py-1 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
                      {{ item.label }}
                  </div>
                  <li v-for="subItem in item.items" :title="subItem.description" :key="subItem.id" @click="selectOption(subItem.id)" class="menu-item" :class="{'is-selected': subItem.id === modelValue}">
                      <div class="flex items-center space-x-2">
                          <img v-if="subItem.icon_base64" :src="subItem.icon_base64" class="h-6 w-6 rounded-md object-cover flex-shrink-0"/>
                          <div v-else class="h-6 w-6 rounded-md bg-gray-200 dark:bg-gray-600 flex-shrink-0 flex items-center justify-center text-gray-400">
                            <slot name="item-icon-default"></slot>
                          </div>
                          <span class="font-normal block truncate">{{ subItem.name }}</span>
                      </div>
                      <span v-if="subItem.id === modelValue" class="check-mark">
                        <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" /></svg>
                      </span>
                  </li>
              </div>
              <li v-else @click="selectOption(item.id)" class="menu-item" :class="{'is-selected': item.id === modelValue}">
                <div class="flex items-center space-x-2">
                  <img v-if="item.icon_base64" :src="item.icon_base64" class="h-6 w-6 rounded-md object-cover flex-shrink-0"/>
                  <div v-else class="h-6 w-6 rounded-md bg-gray-200 dark:bg-gray-600 flex-shrink-0 flex items-center justify-center text-gray-400">
                     <slot name="item-icon-default"></slot>
                  </div>
                  <span class="font-normal block truncate">{{ item.name }}</span>
                </div>
                 <span v-if="item.id === modelValue" class="check-mark">
                    <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" /></svg>
                  </span>
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

<style scoped>
.menu-item {
    @apply flex items-center justify-between text-gray-900 dark:text-gray-100 cursor-pointer select-none relative py-2 pl-3 pr-9 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700;
}
.menu-item.is-selected {
    @apply bg-blue-50 dark:bg-blue-900/50;
}
.menu-item .font-normal.is-selected {
    @apply font-semibold;
}
.check-mark {
    @apply absolute inset-y-0 right-0 flex items-center pr-4 text-blue-600 dark:text-blue-400;
}
</style>