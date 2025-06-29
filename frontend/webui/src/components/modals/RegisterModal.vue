<script setup>
import { ref, computed } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';
import appLogo from '../../assets/logo.png';

const authStore = useAuthStore();
const uiStore = useUiStore();

const username = ref('');
const email = ref('');
const password = ref('');
const confirmPassword = ref('');
const isLoading = ref(false);
const errorMessage = ref('');

const passwordsMatch = computed(() => password.value === confirmPassword.value);
const isPasswordLongEnough = computed(() => password.value.length >= 8);

const openLoginModal = () => {
    uiStore.closeModal('register');
    uiStore.openModal('login');
};

const handleRegister = async () => {
    errorMessage.value = '';

    if (!username.value || !email.value || !password.value || !confirmPassword.value) {
        errorMessage.value = 'All fields are required.';
        return;
    }
    if (!isPasswordLongEnough.value) {
        errorMessage.value = 'Password must be at least 8 characters long.';
        return;
    }
    if (!passwordsMatch.value) {
        errorMessage.value = 'Passwords do not match.';
        return;
    }

    isLoading.value = true;
    try {
        await authStore.register({
            username: username.value,
            email: email.value,
            password: password.value,
        });
        // On success, the auth store will close this modal and show a notification
    } catch (error) {
        errorMessage.value = error.response?.data?.detail || 'An unexpected error occurred during registration.';
    } finally {
        isLoading.value = false;
    }
};
</script>

<template>
  <GenericModal
    modalName="register"
    title="Create an Account"
    maxWidthClass="max-w-md"
  >
    <template #body>
      <div class="flex justify-center mb-6">
        <img :src="appLogo" alt="Application Logo" class="h-16 w-auto" />
      </div>

      <form @submit.prevent="handleRegister" class="space-y-4">
        <div>
          <label for="reg-username" class="block text-sm font-medium">Username</label>
          <input
            v-model="username"
            type="text"
            id="reg-username"
            required
            :disabled="isLoading"
            class="input-field mt-1 w-full"
            placeholder="Choose a username"
            autocomplete="username"
          />
        </div>

        <div>
          <label for="reg-email" class="block text-sm font-medium">Email Address</label>
          <input
            v-model="email"
            type="email"
            id="reg-email"
            required
            :disabled="isLoading"
            class="input-field mt-1 w-full"
            placeholder="your@email.com"
            autocomplete="email"
          />
        </div>

        <div>
          <label for="reg-password" class="block text-sm font-medium">Password</label>
            <input
              v-model="password"
              type="password"
              id="reg-password"
              required
              :disabled="isLoading"
              class="input-field mt-1 w-full"
              placeholder="Create a password (min. 8 characters)"
              autocomplete="new-password"
            />
             <p v-if="password && !isPasswordLongEnough" class="text-xs text-red-500 mt-1">
                Password must be at least 8 characters.
             </p>
        </div>

        <div>
          <label for="reg-confirm-password" class="block text-sm font-medium">Confirm Password</label>
            <input
              v-model="confirmPassword"
              type="password"
              id="reg-confirm-password"
              required
              :disabled="isLoading"
              class="input-field mt-1 w-full"
              placeholder="Confirm your password"
              autocomplete="new-password"
            />
            <p v-if="confirmPassword && !passwordsMatch" class="text-xs text-red-500 mt-1">
                Passwords do not match.
            </p>
        </div>

        <div v-if="errorMessage" class="text-red-600 text-sm text-center p-2 bg-red-100 dark:bg-red-900/50 rounded-md" role="alert">
            {{ errorMessage }}
        </div>

        <div class="pt-2">
            <button type="submit" class="btn btn-primary w-full flex justify-center items-center" :disabled="isLoading">
                <span v-if="isLoading" class="flex items-center">
                    <svg class="animate-spin -ml-1 mr-3 h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span>Creating Account...</span>
                </span>
                <span v-else>Register</span>
            </button>
        </div>
      </form>
    </template>
    
    <template #footer>
        <div class="text-center text-sm">
            <p>
                Already have an account?
                <button @click="openLoginModal" class="font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300">
                    Log in here
                </button>
            </p>
        </div>
    </template>
  </GenericModal>
</template>