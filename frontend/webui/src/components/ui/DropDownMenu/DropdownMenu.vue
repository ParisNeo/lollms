<script setup>
import { ref, provide, onMounted, onUnmounted } from 'vue';
import { useFloating, offset, flip, shift, autoUpdate } from '@floating-ui/vue';
import ToolbarButton from '../ToolbarButton.vue';
import useEventBus from '../../../services/eventBus';

const props = defineProps({
  title: { type: String, required: true },
  icon: { type: String, required: true },
  collection: { type: String, default: 'ui' },
  buttonClass: { type: [String, Object, Array], default: '' }
});

const { emit, on, off } = useEventBus();
const isOpen = ref(false);
const reference = ref(null);
const floating = ref(null);

// NEW: State to track submenu activity
const isSubmenuActive = ref(false);
let closeTimer = null;

const { floatingStyles } = useFloating(reference, floating, {
  placement: 'bottom-start',
  middleware: [offset(5), flip(), shift({ padding: 5 })],
  whileElementsMounted: autoUpdate,
});

function openMenu() {
    clearTimeout(closeTimer);
    isOpen.value = true;
}

function closeMenu() {
    // UPDATED: Delay closing and check if a submenu has become active
    closeTimer = setTimeout(() => {
        if (!isSubmenuActive.value) {
            isOpen.value = false;
        }
    }, 200);
}

function forceClose() {
    isSubmenuActive.value = false;
    isOpen.value = false;
}

function handleItemClick() {
    emit('close-all-dropdowns');
}

// NEW: Function for submenus to report their status
function setSubmenuActive(status) {
    isSubmenuActive.value = status;
}

// NEW: Function for submenus to cancel the parent's close timer
function cancelClose() {
    clearTimeout(closeTimer);
}

onMounted(() => {
    on('close-all-dropdowns', forceClose);
});

onUnmounted(() => {
    off('close-all-dropdowns', forceClose);
});

provide('dropdown-context', {
  setSubmenuActive,
  cancelClose
});
</script>

<template>
  <div class="relative" @mouseenter="openMenu" @mouseleave="closeMenu">
    <ToolbarButton
      ref="reference"
      :title="title"
      :icon="icon"
      :collection="collection"
      :button-class="buttonClass"
    />
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
          ref="floating"
          @click="handleItemClick"
          @mouseenter="cancelClose"
          @mouseleave="closeMenu"
          :style="floatingStyles"
          class="z-50 w-56 origin-top-left rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 dark:ring-gray-700 focus:outline-none py-1"
        >
          <slot></slot>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>