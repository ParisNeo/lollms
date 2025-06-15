<script>
import { mapState, mapActions } from 'pinia';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';

export default {
  name: 'ConfirmationModal',
  components: {
    GenericModal,
  },
  computed: {
    ...mapState(useUiStore, ['confirmationOptions']),
  },
  methods: {
    ...mapActions(useUiStore, ['confirmAction', 'cancelAction']),
  },
};
</script>

<template>
  <GenericModal
    modalName="confirmation"
    :title="confirmationOptions.title || 'Are you sure?'"
    :allowOverlayClose="false"
    maxWidthClass="max-w-md"
  >
    <template #body>
      <div class="text-sm text-gray-700 dark:text-gray-300">
        <p>{{ confirmationOptions.message || 'This action cannot be undone.' }}</p>
      </div>
    </template>
    <template #footer>
      <button @click="cancelAction" class="btn btn-secondary">
        {{ confirmationOptions.cancelText || 'Cancel' }}
      </button>
      <button @click="confirmAction" class="btn btn-danger">
        {{ confirmationOptions.confirmText || 'Confirm' }}
      </button>
    </template>
  </GenericModal>
</template>