<template>
  <div 
    class="relative inline-block" 
    @mouseenter="handleMouseEnter" 
    @mouseleave="handleMouseLeave"
  >
    <ToolbarButton
      ref="reference"
      :title="title"
      :icon="icon"
      :collection="collection"
      :button-class="buttonClass"
      @click="toggleMenu"
    >
      <template #icon v-if="$slots.icon">
        <slot name="icon"></slot>
      </template>
    </ToolbarButton>

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
          @mouseenter="handleMouseEnter"
          @mouseleave="handleMouseLeave"
          :style="floatingStyles"
          class="is-dropdown-panel z-[100] w-56 origin-top-left rounded-xl bg-white dark:bg-gray-800 shadow-2xl ring-1 ring-black/5 dark:ring-gray-700 focus:outline-none py-1 border border-gray-200 dark:border-gray-700"
        >
          <!-- Invisible bridge spanning gap between button and dropdown -->
          <div class="absolute -top-3 left-0 right-0 h-3 pointer-events-auto"></div>
          <div class="absolute -bottom-3 left-0 right-0 h-3 pointer-events-auto"></div>
          <slot></slot>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, provide, onMounted, onUnmounted } from 'vue';
import { useFloating, offset, flip, shift, autoUpdate } from '@floating-ui/vue';
import ToolbarButton from '../ToolbarButton.vue';
import useEventBus from '../../../services/eventBus';

const props = defineProps({
  title: { type: String, required: true },
  icon: { type: String, default: '' },
  collection: { type: String, default: 'ui' },
  buttonClass: { type: [String, Object, Array], default: '' }
});

const { emit, on, off } = useEventBus();
const isOpen = ref(false);
const reference = ref(null);
const floating = ref(null);

const activeSubmenusCount = ref(0);
let closeTimer = null;

// Unique per DropdownMenu instance, so sibling-close events never leak
// across separate toolbar menus.
const scopeId = Symbol('dropdown-root-scope');

const { floatingStyles } = useFloating(reference, floating, {
  placement: 'bottom-start',
  middleware: [offset(4), flip(), shift({ padding: 6 })],
  whileElementsMounted: autoUpdate,
});

function openMenu() {
  clearTimeout(closeTimer);
  isOpen.value = true;
}

function startCloseTimer(delay = 350) {
  clearTimeout(closeTimer);
  closeTimer = setTimeout(() => {
    if (activeSubmenusCount.value <= 0) {
      isOpen.value = false;
    }
  }, delay);
}

function cancelClose() {
  clearTimeout(closeTimer);
}

function handleMouseEnter() {
  cancelClose();
  openMenu();
}

function handleMouseLeave() {
  startCloseTimer(350);
}

function toggleMenu(event) {
  if (event) event.stopPropagation();
  cancelClose();
  isOpen.value = !isOpen.value;
}

function forceClose() {
  activeSubmenusCount.value = 0;
  clearTimeout(closeTimer);
  isOpen.value = false;
}

function handleItemClick(event) {
  const isControl = event.target.closest('input, select, textarea, .toggle-switch, .slider, .slider-sm');
  const keepOpen = event.target.closest('[data-keep-open="true"]');
  const isSubmenuTrigger = event.target.closest('.group\\/submenu, .is-submenu-trigger');
  
  if (!isControl && !keepOpen && !isSubmenuTrigger) {
    emit('close-all-dropdowns');
  }
}

// Called by a direct-child submenu item to mark itself active/inactive.
// Keeps the top-level menu open for as long as ANY descendant, at any
// depth, is open (each level bubbles this call further up the chain).
function setSubmenuActive(status) {
  if (status) {
    activeSubmenusCount.value++;
    cancelClose();
  } else {
    activeSubmenusCount.value = Math.max(0, activeSubmenusCount.value - 1);
    if (activeSubmenusCount.value === 0) {
      startCloseTimer(350);
    }
  }
}

// Closes this item's direct-child submenus other than `exceptId`.
// Scoped with this menu's own scopeId so it only affects items whose
// immediate parent is THIS menu, never items nested deeper elsewhere.
function closeSiblingSubmenus(exceptId) {
  emit('close-sibling-submenus', { scopeId, exceptId });
}

function handleDocumentClick(event) {
  if (!isOpen.value) return;
  const target = event.target;
  const triggerEl = reference.value?.$el || reference.value;
  const floatingEl = floating.value;
  
  if (
    triggerEl?.contains(target) || 
    floatingEl?.contains(target) || 
    target.closest('.is-submenu-panel') || 
    target.closest('.is-dropdown-panel')
  ) {
    return;
  }
  forceClose();
}

onMounted(() => {
  on('close-all-dropdowns', forceClose);
  document.addEventListener('pointerdown', handleDocumentClick);
});

onUnmounted(() => {
  off('close-all-dropdowns', forceClose);
  document.removeEventListener('pointerdown', handleDocumentClick);
  clearTimeout(closeTimer);
});

provide('dropdown-context', {
  scopeId,
  setSubmenuActive,
  cancelClose,
  closeSiblingSubmenus
});
</script>