<template>
  <div class="relative" ref="triggerRef" @mouseenter="openSubmenu" @mouseleave="closeSubmenu">
    <div class="flex items-center justify-between px-3 py-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 rounded cursor-pointer text-sm text-gray-700 dark:text-gray-200 w-full">
      <EditorIcon v-if="props.icon" :name="props.icon" :collection="props.collection" class="h-6 w-6 mr-2" />
      <span class="flex-grow">{{ props.title }}</span>
      <EditorIcon name="chevron-right" collection="ui" class="h-4 w-4 ml-2 opacity-70" />
    </div>

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
          ref="menuRef"
          :style="floatingStyles"
          @mouseenter="cancelClose" 
          @mouseleave="closeSubmenu"
          @click="handleItemClick"
          class="fixed z-50 p-1 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-lg min-w-max max-h-[80vh] overflow-y-auto is-submenu-panel"
        >
          <slot></slot>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, inject, provide, onMounted, onUnmounted } from 'vue';
import { useFloating, offset, flip, shift, autoUpdate } from '@floating-ui/vue';
import EditorIcon from './EditorIcon.vue';
import useEventBus from '../../../services/eventBus';

const props = defineProps({
    title: String,
    icon: String,
    collection: { type: String, default: 'ui' }
});

const { emit, on, off } = useEventBus();
const isOpen = ref(false);
let closeTimer = null;
const triggerRef = ref(null);
const menuRef = ref(null);

// UPDATED: Inject parent context
const parentContext = inject('dropdown-context', { 
  setSubmenuActive: () => {}, 
  cancelClose: () => {} 
});

const { floatingStyles } = useFloating(triggerRef, menuRef, {
  placement: 'right-start',
  middleware: [offset({ mainAxis: -4, crossAxis: -5 }), flip(), shift({ padding: 5 })],
  whileElementsMounted: autoUpdate,
});

const openSubmenu = () => {
    parentContext.cancelClose(); // Prevent parent from closing
    parentContext.setSubmenuActive(true); // Tell parent we are active
    if (closeTimer) clearTimeout(closeTimer);
    isOpen.value = true;
};

const closeSubmenu = () => {
    closeTimer = setTimeout(() => {
        isOpen.value = false;
        parentContext.setSubmenuActive(false); // Tell parent we are no longer active
    }, 200);
};

const cancelClose = () => {
    parentContext.cancelClose();
    if (closeTimer) clearTimeout(closeTimer);
};

function handleItemClick() {
  emit('close-all-dropdowns');
}

onMounted(() => {
  on('close-all-dropdowns', () => isOpen.value = false);
});

onUnmounted(() => {
  off('close-all-dropdowns', () => isOpen.value = false);
});

provide('dropdown-context', {
  setSubmenuActive: parentContext.setSubmenuActive, // Pass down parent's functions
  cancelClose: cancelClose
});
</script>