<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';
import GenericModal from './GenericModal.vue';

const uiStore = useUiStore();

const props = computed(() => uiStore.modalData('resetPassword'));
const user = computed(() => props.value?.user);
const onPasswordReset = computed(() => props.value?.onPasswordReset);

const newPassword = ref('');
const confirmPassword = ref('');
const isPasswordVisible = ref(false);
const isLoading = ref(false);
const errorMessage = ref('');

watch(user, (newUser) => {
  if (newUser) {
    newPassword.value = '';
    confirmPassword.value = '';
    errorMessage.value = '';
  }
});

const handleReset = async () => {
    if (newPassword.value.length < 8) {
        errorMessage.value = 'New password must be at least 8 characters long.';
        return;
    }
    if (newPassword.value !== confirmPassword.value) {
        errorMessage.value = 'Passwords do not match.';
        return;
    }

    isLoading.value = true;
    errorMessage.value = '';
    
    try {
        await apiClient.post(`/api/admin/users/${user.value.id}/reset-password`, {
            new_password: newPassword.value
        });
        uiStore.addNotification(`Password for ${user.value.username} has been reset.`, 'success');

        if (onPasswordReset.value && typeof onPasswordReset.value === 'function') {
          onPasswordReset.value();
        }

        uiStore.closeModal('resetPassword');
    } catch (error) {
        errorMessage.value = error.response?.data?.detail || 'An unexpected error occurred.';
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
  <GenericModal
    modalName="resetPassword"
    :title="user ? `Reset Password for ${user.username}` : 'Reset Password'"
    maxWidthClass="max-w-md"
    @close="uiStore.closeModal('resetPassword')"
  >
    <template #body>
      <form v-if="user" @submit.prevent="handleReset" class="space-y-4">
        <div>
          <label for="admin-new-password" class="block text-sm font-medium">New Password</label>
          <div class="relative mt-1">
            <input
              v-model="newPassword"
              :type="isPasswordVisible ? 'text' : 'password'"
              id="admin-new-password"
              required
              minlength="8"
              :disabled="isLoading"
              class="input-field w-full pr-10"
              placeholder="Enter new password"
            />
            <button
              type="button"
              @click="isPasswordVisible = !isPasswordVisible"
              class="absolute inset-y-0 right-0 flex items-center px-3 text-gray-500 hover:text-gray-700"
            >
              <svg v-if="isPasswordVisible" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a9.97 9.97 0 01-1.563 3.029m-2.135-2.135A6.978 6.978 0 0112 17c-1.855 0-3.56-.736-4.807-1.938" /></svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
            </button>
          </div>
        </div>
        <div>
          <label for="admin-confirm-password" class="block text-sm font-medium">Confirm New Password</label>
          <input
            v-model="confirmPassword"
            :type="isPasswordVisible ? 'text' : 'password'"
            id="admin-confirm-password"
            required
            :disabled="isLoading"
            class="input-field mt-1 w-full"
            placeholder="Confirm new password"
          />
        </div>
        <div v-if="errorMessage" class="text-red-600 text-sm text-center p-2 bg-red-100 dark:bg-red-900/50 rounded-md" role="alert">
          {{ errorMessage }}
        </div>
      </form>
    </template>
    <template #footer>
      <div class="flex justify-end space-x-3">
        <button type="button" class="btn btn-secondary" @click="uiStore.closeModal('resetPassword')">Cancel</button>
        <button type="button" class="btn btn-danger" @click="handleReset" :disabled="isLoading">
            {{ isLoading ? 'Resetting...' : 'Reset Password' }}
        </button>
      </div>
    </template>
  </GenericModal>
</template>