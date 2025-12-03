<script setup>
import { computed, onMounted, onUnmounted, defineEmits } from 'vue';
import { useUiStore } from '../../stores/ui';
import IconClose from '../../assets/icons/IconClose.vue';

const props = defineProps({
  modalName: { type: String, default: '' }, // Made optional for manual control
  visible: { type: Boolean, default: false }, // Manual visibility control
  title: { type: String, default: 'Modal' },
  allowOverlayClose: { type: Boolean, default: true },
  maxWidthClass: { type: String, default: 'max-w-xl' },
  showCloseButton: { type: Boolean, default: true }
});

const emit = defineEmits(['close']);

const uiStore = useUiStore();

const isVisible = computed(() => {
  if (props.modalName) {
    return uiStore.isModalOpen(props.modalName);
  }
  return props.visible;
});

function handleClose() {
  emit('close');
  if (props.modalName) {
    uiStore.closeModal(props.modalName);
  }
}

function handleKeydown(e) {
  if (e.key === 'Escape' && isVisible.value && props.allowOverlayClose && props.showCloseButton) {
    handleClose();
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity ease-out duration-300"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity ease-in duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div v-if="isVisible" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40" @click="allowOverlayClose ? handleClose() : null"></div>
    </Transition>

    <Transition
      enter-active-class="transition ease-out duration-300"
      enter-from-class="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
      enter-to-class="opacity-100 translate-y-0 sm:scale-100"
      leave-active-class="transition ease-in duration-200"
      leave-from-class="opacity-100 translate-y-0 sm:scale-100"
      leave-to-class="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
    >
      <div v-if="isVisible" class="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div class="modal-panel bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full flex flex-col max-h-[90vh] pointer-events-auto" :class="[maxWidthClass]">
          <header class="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
            <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ title }}</h2>
            <button v-if="showCloseButton" @click="handleClose" class="p-1 rounded-full text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">
              <IconClose class="w-6 h-6" />
            </button>
          </header>
          
          <main class="p-6 overflow-y-auto flex-1">
             <slot name="body">
                <slot></slot>
             </slot>
          </main>
          
          <footer v-if="$slots.footer" class="flex items-center justify-end p-4 space-x-3 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700 flex-shrink-0">
            <slot name="footer"></slot>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
