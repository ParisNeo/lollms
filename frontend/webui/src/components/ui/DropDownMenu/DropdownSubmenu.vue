<script setup>
import { ref, computed, inject, provide, onMounted, onUnmounted } from 'vue';
import { useFloating, offset, flip, shift, autoUpdate } from '@floating-ui/vue';
import useEventBus from '../../../services/eventBus';

import IconChevronRight from '../../../assets/icons/IconChevronRight.vue';
import IconCpuChip from '../../../assets/icons/IconCpuChip.vue';
import IconPhoto from '../../../assets/icons/IconPhoto.vue';
import IconSpeakerWave from '../../../assets/icons/IconSpeakerWave.vue';
import IconMicrophone from '../../../assets/icons/IconMicrophone.vue';
import IconVideoCamera from '../../../assets/icons/IconVideoCamera.vue';
import IconUserCircle from '../../../assets/icons/IconUserCircle.vue';
import IconFileText from '../../../assets/icons/IconFileText.vue';
import IconDatabase from '../../../assets/icons/IconDatabase.vue';
import IconTicket from '../../../assets/icons/IconTicket.vue';
import IconPencil from '../../../assets/icons/IconPencil.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconCog from '../../../assets/icons/IconCog.vue';
import IconServer from '../../../assets/icons/IconServer.vue';
import IconEye from '../../../assets/icons/IconEye.vue';

const props = defineProps({
  title: { type: String, required: true },
  icon: { type: String, default: null },
  collection: { type: String, default: 'default' },
  statusColor: { type: String, default: null },
  statusText: { type: String, default: null },
  isSelected: { type: Boolean, default: null },
  customClass: { type: String, default: '' }
});

const { emit, on, off } = useEventBus();

const isSubmenuOpen = ref(false);
const triggerRef = ref(null);
const floatingRef = ref(null);

// Identity my parent uses to know it's me when closing siblings.
const submenuId = Symbol('submenu-item');
// Scope I hand to MY OWN children, so their sibling-close events only
// ever affect each other — never items that live under a different
// parent, at any depth.
const myScopeId = Symbol('submenu-scope');

// How many of MY direct children currently have a submenu open. While
// this is > 0 I must not close myself, no matter how long the cursor
// has been off my own trigger/panel.
const activeChildCount = ref(0);

let closeTimer = null;

const parentContext = inject('dropdown-context', {
  scopeId: null,
  setSubmenuActive: () => {},
  cancelClose: () => {},
  closeSiblingSubmenus: () => {}
});

const { floatingStyles } = useFloating(triggerRef, floatingRef, {
  placement: 'right-start',
  whileElementsMounted: autoUpdate,
  middleware: [offset(4), flip(), shift({ padding: 8 })],
});

function cancelCloseTimer() {
  clearTimeout(closeTimer);
}

function startCloseTimer(delay = 300) {
  cancelCloseTimer();
  closeTimer = setTimeout(() => {
    if (activeChildCount.value <= 0) {
      isSubmenuOpen.value = false;
      parentContext.setSubmenuActive(false);
    }
  }, delay);
}

// Cancels MY close timer and bubbles the cancel up through every
// ancestor, so hovering a deeply nested submenu keeps the whole chain
// of parents alive, not just the immediate one.
function cancelCloseChain() {
  cancelCloseTimer();
  if (typeof parentContext?.cancelClose === 'function') {
    parentContext.cancelClose();
  }
}

// Called by a direct child submenu item to report it opened/closed.
// Keeps me open while any child is open, and bubbles the same signal
// further up so grandparents stay open too.
function setChildSubmenuActive(status) {
  if (status) {
    activeChildCount.value++;
    cancelCloseTimer();
  } else {
    activeChildCount.value = Math.max(0, activeChildCount.value - 1);
    if (activeChildCount.value === 0) {
      startCloseTimer();
    }
  }
  if (typeof parentContext?.setSubmenuActive === 'function') {
    parentContext.setSubmenuActive(status);
  }
}

// Closes my direct children's submenus other than `exceptId`. Scoped
// to myScopeId so only items whose immediate parent is ME respond.
function closeChildSiblings(exceptId) {
  emit('close-sibling-submenus', { scopeId: myScopeId, exceptId });
}

function handleMouseEnter() {
  cancelCloseChain();
  if (typeof parentContext?.closeSiblingSubmenus === 'function') {
    parentContext.closeSiblingSubmenus(submenuId);
  }
  if (typeof parentContext?.setSubmenuActive === 'function') {
    parentContext.setSubmenuActive(true);
  }
  isSubmenuOpen.value = true;
}

function handleMouseLeave() {
  startCloseTimer();
}

function toggleClick(e) {
  e.stopPropagation();
  cancelCloseTimer();
  const next = !isSubmenuOpen.value;
  if (next && typeof parentContext?.closeSiblingSubmenus === 'function') {
    parentContext.closeSiblingSubmenus(submenuId);
  }
  isSubmenuOpen.value = next;
  if (typeof parentContext?.setSubmenuActive === 'function') {
    parentContext.setSubmenuActive(next);
  }
}

function forceClose() {
  activeChildCount.value = 0;
  cancelCloseTimer();
  if (isSubmenuOpen.value) {
    isSubmenuOpen.value = false;
    if (typeof parentContext?.setSubmenuActive === 'function') {
      parentContext.setSubmenuActive(false);
    }
  }
}

function handleSiblingClose({ scopeId, exceptId }) {
  if (!parentContext?.scopeId || scopeId !== parentContext.scopeId) return;
  if (exceptId === submenuId) return;
  forceClose();
}

function handleCloseAll() {
  activeChildCount.value = 0;
  cancelCloseTimer();
  isSubmenuOpen.value = false;
}

const resolvedStatusColor = computed(() => {
  if (props.statusColor) return props.statusColor;
  if (props.isSelected === true) return 'green';
  if (props.isSelected === false) return 'red';
  return null;
});

const iconComponent = computed(() => {
  switch (props.icon) {
    case 'cpu-chip': return IconCpuChip;
    case 'photo': return IconPhoto;
    case 'speaker-wave': return IconSpeakerWave;
    case 'microphone': return IconMicrophone;
    case 'video-camera': return IconVideoCamera;
    case 'user-circle': return IconUserCircle;
    case 'file-text': return IconFileText;
    case 'database': return IconDatabase;
    case 'ticket': return IconTicket;
    case 'pencil': return IconPencil;
    case 'sparkles': return IconSparkles;
    case 'cog': return IconCog;
    case 'server': return IconServer;
    case 'eye': return IconEye;
    default: return null;
  }
});

onMounted(() => {
  on('close-sibling-submenus', handleSiblingClose);
  on('close-all-dropdowns', handleCloseAll);
});

onUnmounted(() => {
  off('close-sibling-submenus', handleSiblingClose);
  off('close-all-dropdowns', handleCloseAll);
  cancelCloseTimer();
});

provide('dropdown-context', {
  scopeId: myScopeId,
  setSubmenuActive: setChildSubmenuActive,
  cancelClose: cancelCloseChain,
  closeSiblingSubmenus: closeChildSiblings
});
</script>

<template>
  <div 
    class="relative group/submenu"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
  >
    <button 
      ref="triggerRef"
      type="button"
      @click="toggleClick"
      class="w-full text-left px-3.5 py-2.5 text-xs transition-colors hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer flex items-center justify-between gap-2 select-none"
      :class="[
        isSubmenuOpen ? 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white' : 'text-gray-750 dark:text-gray-200',
        customClass
      ]"
    >
      <!-- Left: Neutral Icon & Category Label (No Color Modifications) -->
      <div class="flex items-center gap-3 min-w-0">
        <component 
          v-if="iconComponent" 
          :is="iconComponent" 
          class="w-4 h-4 shrink-0 text-gray-500 dark:text-gray-400" 
        />

        <span class="font-medium text-gray-800 dark:text-gray-200 truncate">
          {{ title }}
        </span>
      </div>

      <!-- Right: Status Badge & Submenu Arrow -->
      <div class="flex items-center gap-2 shrink-0">
        <span 
          v-if="statusText || resolvedStatusColor" 
          class="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider flex items-center gap-1.5 select-none"
          :class="{
            'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200/80 dark:border-emerald-800/60': resolvedStatusColor === 'green',
            'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-200/80 dark:border-rose-800/60': resolvedStatusColor === 'red',
            'bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200/80 dark:border-amber-800/60': resolvedStatusColor === 'orange'
          }"
        >
          <span class="w-1.5 h-1.5 rounded-full" :class="{
            'bg-emerald-500': resolvedStatusColor === 'green',
            'bg-rose-500': resolvedStatusColor === 'red',
            'bg-amber-500': resolvedStatusColor === 'orange'
          }"></span>
          <span>{{ statusText || (resolvedStatusColor === 'green' ? 'Selected' : 'None') }}</span>
        </span>

        <IconChevronRight class="w-3.5 h-3.5 text-gray-400 transition-transform group-hover/submenu:translate-x-0.5" />
      </div>
    </button>

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
          v-if="isSubmenuOpen"
          ref="floatingRef"
          :style="floatingStyles"
          class="is-submenu-panel z-[70] min-w-[260px] max-w-sm rounded-xl bg-white dark:bg-gray-800 shadow-2xl ring-1 ring-black ring-opacity-5 dark:ring-gray-700 border dark:border-gray-700 py-1 overflow-hidden"
          @mouseenter="handleMouseEnter"
          @mouseleave="handleMouseLeave"
        >
          <div class="absolute -left-3 top-0 bottom-0 w-3 pointer-events-auto"></div>
          <div class="absolute -right-3 top-0 bottom-0 w-3 pointer-events-auto"></div>
          <slot />
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
@reference "tailwindcss";
</style>