<script setup>
import { ref, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';

const uiStore = useUiStore();
const props = computed(() => uiStore.modalData('passwordResetLink'));
const linkCopied = ref(false);

const copyLink = () => {
  if (props.value?.link) {
    navigator.clipboard.writeText(props.value.link).then(() => {
      linkCopied.value = true;
      setTimeout(() => {
        linkCopied.value = false;
      }, 2000);
    });
  }
};
</script>

<template>
  <GenericModal
    modalName="passwordResetLink"
    title="Generated Password Reset Link"
    maxWidthClass="max-w-lg"
  >
    <template #body>
      <div v-if="props" class="space-y-4">
        <p class="text-sm text-gray-600 dark:text-gray-300">
          A single-use password reset link has been generated for the user
          <strong class="font-medium text-gray-900 dark:text-gray-100">{{ props.username }}</strong>.
          Please copy this link and send it to them securely. This link will expire in one hour.
        </p>
        <div class="relative mt-2">
          <input
            type="text"
            :value="props.link"
            readonly
            class="input-field w-full pr-24"
          />
          <button
            @click="copyLink"
            class="absolute inset-y-0 right-0 flex items-center px-4 text-sm font-medium rounded-r-md transition-colors"
            :class="[
              linkCopied
                ? 'bg-green-600 text-white hover:bg-green-700'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            ]"
          >
            {{ linkCopied ? 'Copied!' : 'Copy Link' }}
          </button>
        </div>
      </div>
    </template>
    
    <template #footer>
      <div class="w-full flex justify-end">
        <button
          type="button"
          class="btn btn-primary"
          @click="uiStore.closeModal('passwordResetLink')"
        >
          Done
        </button>
      </div>
    </template>
  </GenericModal>
</template>