<script setup>
import { ref, nextTick, watch } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';
import appLogo from '../../assets/logo.png';

const authStore = useAuthStore();
const uiStore = useUiStore();

const usernameOrEmail = ref('');
const password = ref('');
const isLoading = ref(false);
const errorMessage = ref('');
const isPasswordVisible = ref(false);

const usernameInput = ref(null);

watch(() => uiStore.activeModal, (newModalName) => {
    if (newModalName === 'login') {
        nextTick(() => {
            usernameInput.value?.focus();
        });
    }
});

const togglePasswordVisibility = () => {
    isPasswordVisible.value = !isPasswordVisible.value;
};

const handleLogin = async () => {
    errorMessage.value = '';

    if (!usernameOrEmail.value || !password.value) {
        errorMessage.value = 'Username/Email and password are required.';
        return;
    }

    isLoading.value = true;
    try {
        await authStore.login(usernameOrEmail.value, password.value);
        usernameOrEmail.value = '';
        password.value = '';
    } catch (error) {
        errorMessage.value = error.message || 'An unknown error occurred.';
        password.value = '';
    } finally {
        isLoading.value = false;
    }
};

const openRegisterModal = () => {
    uiStore.closeModal('login');
    uiStore.openModal('register');
};

const openForgotPasswordModal = () => {
  uiStore.closeModal('login');
  uiStore.openModal('forgotPassword');
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
      <div class="flex justify-center mb-6">
        <img :src="appLogo" alt="Application Logo" class="h-16 w-auto" />
      </div>

      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label for="username" class="block text-sm font-medium">Username or Email</label>
          <input
            ref="usernameInput"
            v-model="usernameOrEmail"
            type="text"
            id="username"
            required
            :disabled="isLoading"
            class="input-field mt-1 w-full"
            placeholder="Enter your username or email"
            autocomplete="username"
          />
        </div>

        <div>
          <div class="flex items-center justify-between">
            <label for="password" class="block text-sm font-medium">Password</label>
            <div class="text-sm">
              <button
                type="button"
                @click="openForgotPasswordModal"
                class="font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300"
              >
                Forgot your password?
              </button>
            </div>
          </div>
          <div class="relative mt-1">
            <input
              v-model="password"
              :type="isPasswordVisible ? 'text' : 'password'"
              id="password"
              required
              :disabled="isLoading"
              class="input-field w-full pr-10"
              placeholder="Enter your password"
              autocomplete="current-password"
            />
            <button
              type="button"
              @click="togglePasswordVisibility"
              class="absolute inset-y-0 right-0 flex items-center px-3 text-gray-500 hover:text-gray-700"
              aria-label="Toggle password visibility"
            >
              <svg v-if="isPasswordVisible" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a9.97 9.97 0 01-1.563 3.029m-2.135-2.135A6.978 6.978 0 0112 17c-1.855 0-3.56-.736-4.807-1.938" /></svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
            </button>
          </div>
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
                    <span>Logging In...</span>
                </span>
                <span v-else>Login</span>
            </button>
        </div>
      </form>
    </template>
    
    <template #footer>
        <div class="text-center text-sm">
            <p>
                Don't have an account?
                <button @click="openRegisterModal" class="font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300">
                    Sign Up
                </button>
            </p>
        </div>
    </template>
  </GenericModal>
</template>