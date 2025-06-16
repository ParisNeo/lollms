<script>
import { useUiStore } from '../../stores/ui';
import { computed } from 'vue';

export default {
  name: 'GenericModal',
  props: {
    modalName: {
      type: String,
      required: true,
    },
    title: {
      type: String,
      default: 'Modal',
    },
    showCloseButton: {
      type: Boolean,
      default: true,
    },
    allowOverlayClose: {
      type: Boolean,
      default: true,
    },
    maxWidthClass: {
      type: String,
      default: 'max-w-xl' // e.g., max-w-sm, max-w-md, max-w-xl, max-w-4xl
    }
  },
  setup(props) {
    const uiStore = useUiStore();
    // This is necessary for v-if in the template to work with <transition>
    const isVisible = computed(() => uiStore.isModalOpen(props.modalName));
    return { uiStore, isVisible };
  },
  methods: {
    close() {
      this.uiStore.closeModal(this.modalName);
    },
    handleOverlayClick() {
      if (this.allowOverlayClose) {
        this.close();
      }
    }
  }
};
</script>

<template>
  <Transition name="modal">
    <div
      v-if="isVisible"
      class="modal-overlay"
      @click.self="handleOverlayClick"
    >
      <div
        class="modal-content p-6"
        :class="[maxWidthClass]"
      >
        <!-- Modal Header -->
        <div class="flex items-start justify-between pb-4 mb-4 border-b dark:border-gray-700">
          <h3 class="text-lg font-semibold text-gray-800 dark:text-gray-100">{{ title }}</h3>
          <button
            v-if="showCloseButton"
            @click="close"
            class="p-1 rounded-full text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 -mt-1 -mr-1"
            aria-label="Close modal"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Modal Body (slotted content) -->
        <div class="flex-grow overflow-y-auto">
          <slot name="body"></slot>
        </div>

        <!-- Modal Footer (slotted content) -->
        <div v-if="$slots.footer" class="flex justify-end space-x-3 pt-4 mt-4 border-t dark:border-gray-700">
          <slot name="footer"></slot>
        </div>
      </div>
    </div>
  </Transition>
</template>