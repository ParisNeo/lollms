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
      <div v-if="isVisible" class="modal-overlay" @click="allowOverlayClose ? handleClose() : null"></div>
    </Transition>

    <Transition
      enter-active-class="transition ease-out duration-400"
      enter-from-class="opacity-0 scale-95 translate-y-8"
      enter-to-class="opacity-100 scale-100 translate-y-0"
      leave-active-class="transition ease-in duration-200"
      leave-from-class="opacity-100 scale-100 translate-y-0"
      leave-to-class="opacity-0 scale-95 translate-y-8"
    >
      <div v-if="isVisible" class="fixed inset-0 z-50 flex items-center justify-center p-6 pointer-events-none">
        <div 
          class="modal-panel w-full flex flex-col pointer-events-auto" 
          :class="[maxWidthClass, maxWidthClass.includes('max-w-full') ? 'max-h-full h-full !rounded-none' : 'max-h-[85vh]']"
        >
          <!-- Enhanced Header -->
          <header class="modal-header">
            <button v-if="showCloseButton" @click="handleClose" class="modal-close-btn">
              <IconClose class="w-6 h-6" />
            </button>
          </header>
          
          <main class="modal-body custom-scrollbar">
             <div class="message-prose">
                <slot name="body">
                    <slot></slot>
                </slot>
             </div>
          </main>
          
          <!-- Enhanced Footer -->
          <footer v-if="$slots.footer" class="modal-footer">
            <slot name="footer"></slot>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
