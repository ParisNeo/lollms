<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';

const uiStore = useUiStore();

const isOpen = computed(() => uiStore.isModalOpen('interactiveOutput'));
const data = computed(() => uiStore.modalData('interactiveOutput'));

function closeModal() {
    uiStore.closeModal('interactiveOutput');
}
</script>

<template>
  <div v-if="isOpen" class="modal-overlay" @click.self="closeModal">
    <div class="modal-panel interactive-output-modal">
      <div class="modal-header">
        <h3>Interactive Output</h3>
        <button @click="closeModal" class="modal-close-btn">×</button>
      </div>
      <div class="modal-body">
        <!-- This modal is now ONLY for the Pygame canvas -->
        <div v-if="data?.canvasId" class="canvas-container">
          <canvas :id="data.canvasId" class="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-black"></canvas>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.interactive-output-modal {
    max-width: 80vw;
    width: 900px;
}
.modal-body {
    padding: 1.5rem;
    max-height: 85vh;
    overflow-y: auto;
}
.canvas-container {
    display: flex;
    justify-content: center;
    align-items: center;
}
</style>