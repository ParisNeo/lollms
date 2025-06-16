<script setup>
import { ref } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';

const authStore = useAuthStore();
const uiStore = useUiStore();

const username = ref('');
const password = ref('');
const isLoading = ref(false);

const handleLogin = async () => {
    if (!username.value || !password.value) {
        uiStore.addNotification('Username and password are required.', 'warning');
        return;
    }
    isLoading.value = true;
    try {
        await authStore.login(username.value, password.value);
        // On success, the auth store will close the modal and show a success notification.
    } catch (error) {
        // On failure, the auth store shows an error notification. We just need to re-enable the form.
        password.value = ''; // Clear password field on failure
    } finally {
        isLoading.value = false;
    }
};
</script>

<template>
  <GenericModal
    modalName="login"
    title="Login Required"
    :showCloseButton="false"
    :allowOverlayClose="false"
    maxWidthClass="max-w-md"
  >
    <template #body>
      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label for="username" class="block text-sm font-medium">Username</label>
          <input
            v-model="username"
            type="text"
            id="username"
            required
            :disabled="isLoading"
            class="input-field mt-1"
            placeholder="Enter your username"
            autocomplete="username"
          />
        </div>
        <div>
          <label for="password" class="block text-sm font-medium">Password</label>
          <input
            v-model="password"
            type="password"
            id="password"
            required
            :disabled="isLoading"
            class="input-field mt-1"
            placeholder="Enter your password"
            autocomplete="current-password"
          />
        </div>
      </form>
    </template>
    <template #footer>
      <button @click="handleLogin" class="btn btn-primary w-full" :disabled="isLoading">
        <span v-if="isLoading">Logging In...</span>
        <span v-else>Login</span>
      </button>
    </template>
  </GenericModal>
</template>