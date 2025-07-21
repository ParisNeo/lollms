<script setup>
import { ref, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';

const uiStore = useUiStore();
const props = computed(() => uiStore.modalData('passwordResetLink'));
const linkCopied = ref(false);

const title = computed(() => props.value?.title || 'Generated Link');
const message = computed(() => props.value?.message || 'Please copy this link and send it securely.');
const entityName = computed(() => props.value?.username || '');
const link = computed(() => props.value?.link || '');
const copyButtonText = computed(() => props.value?.copyButtonText || 'Copy Link');

const copyLink = async () => {
  if (link.value) {
    const success = await uiStore.copyToClipboard(link.value);
    if (success) {
      linkCopied.value = true;
      setTimeout(() => {
        linkCopied.value = false;
      }, 2000);
    }
  }
};
</script>

<template>
  <GenericModal
    modalName="passwordResetLink"
    :title="title"
    maxWidthClass="max-w-lg"
  >
    <template #body>
      <div v-if="props" class="space-y-4">
        <p class="text-sm text-gray-600 dark:text-gray-300">
          {{ message }}
          <strong v-if="entityName" class="font-medium text-gray-900 dark:text-gray-100">{{ entityName }}</strong>.
        </p>
        <div class="relative mt-2">
          <input
            type="text"
            :value="link"
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
            {{ linkCopied ? 'Copied!' : copyButtonText }}
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