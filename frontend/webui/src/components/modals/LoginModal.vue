<script setup>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const authStore = useAuthStore();
const uiStore = useUiStore();

const username = ref('');
const password = ref('');
const isLoading = ref(false);
const errorMessage = ref('');

// 2FA / Email Verification Code state
const isEmailVerificationRequired = ref(false);
const emailVerificationCode = ref('');
const tempToken = ref('');
const emailHint = ref('');
const isVerifyingCode = ref(false);
const isResendingCode = ref(false);

const handleLogin = async () => {
  isLoading.value = true;
  errorMessage.value = '';
  try {
    const result = await authStore.login(username.value, password.value);
    
    if (result && result.email_verification_required) {
        isEmailVerificationRequired.value = true;
        tempToken.value = result.temp_token;
        emailHint.value = result.email_hint || 'your registered email';
        return;
    }
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || 'Login failed. Please check your credentials.';
  } finally {
    isLoading.value = false;
  }
};

const handleVerifyCode = async () => {
    if (!emailVerificationCode.value.trim()) {
        errorMessage.value = 'Please enter the verification code.';
        return;
    }

    isVerifyingCode.value = true;
    errorMessage.value = '';
    try {
        await authStore.verifyEmailCode(tempToken.value, emailVerificationCode.value.trim());
    } catch (error) {
        errorMessage.value = error.response?.data?.detail || 'Invalid or expired verification code.';
    } finally {
        isVerifyingCode.value = false;
    }
};

const handleResendCode = async () => {
    isResendingCode.value = true;
    try {
        await authStore.resendVerificationCode(tempToken.value);
    } catch (error) {
        errorMessage.value = error.response?.data?.detail || 'Failed to resend verification code.';
    } finally {
        isResendingCode.value = false;
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
  <GenericModal modalName="login" title="Sign In" maxWidthClass="max-w-md">
    <template #body>
      <!-- Standard Login Form -->
      <form v-if="!isEmailVerificationRequired" @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label for="username" class="block text-sm font-medium">Username or Email</label>
          <input
            v-model="username"
            type="text"
            id="username"
            name="username"
            required
            class="input-field mt-1 w-full"
            placeholder="Enter username or email"
            autocomplete="username"
          />
        </div>
        <div>
          <label for="password" class="block text-sm font-medium">Password</label>
          <input
            v-model="password"
            type="password"
            id="password"
            name="password"
            required
            class="input-field mt-1 w-full"
            placeholder="••••••••"
            autocomplete="current-password"
          />
          <div class="flex justify-end mt-1.5">
            <button
              type="button"
              @click="openForgotPasswordModal"
              class="text-xs text-blue-600 hover:underline dark:text-blue-400 font-medium"
            >
              Forgot password?
            </button>
          </div>
        </div>
        
        <div v-if="errorMessage" class="text-red-500 text-sm">
          {{ errorMessage }}
        </div>

        <button
          type="submit"
          class="btn btn-primary w-full"
          :disabled="isLoading"
        >
          <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-2" />
          {{ isLoading ? 'Signing In...' : 'Sign In' }}
        </button>
        
        <p class="text-center text-sm text-gray-500 dark:text-gray-400 pt-2">
          Don't have an account?
          <button
            type="button"
            @click="openRegisterModal"
            class="text-blue-600 hover:underline dark:text-blue-400 font-medium"
          >
            Register here
          </button>
        </p>
      </form>

      <!-- 2FA / Email Verification Code Form -->
      <form v-else @submit.prevent="handleVerifyCode" class="space-y-5 animate-in fade-in">
          <div class="text-center space-y-2">
              <div class="w-12 h-12 rounded-full bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 flex items-center justify-center mx-auto text-xl font-bold">
                  ✉️
              </div>
              <h3 class="text-base font-bold text-gray-900 dark:text-white">Security Verification</h3>
              <p class="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                  We sent a 6-digit verification code to <span class="font-mono font-bold text-gray-700 dark:text-gray-300">{{ emailHint }}</span>.
              </p>
          </div>

          <div>
              <label for="verification-code" class="block text-xs font-black uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                  Verification Code
              </label>
              <input
                  v-model="emailVerificationCode"
                  type="text"
                  id="verification-code"
                  required
                  maxlength="8"
                  class="input-field text-center font-mono text-lg tracking-[0.3em] font-bold py-2.5"
                  placeholder="123456"
                  autofocus
                  autocomplete="one-time-code"
              />
          </div>

          <div v-if="errorMessage" class="p-3 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 rounded-xl text-xs">
              {{ errorMessage }}
          </div>

          <div class="space-y-3">
              <button
                  type="submit"
                  class="btn btn-primary w-full py-2.5 text-xs font-black uppercase tracking-wider"
                  :disabled="isVerifyingCode"
              >
                  <IconAnimateSpin v-if="isVerifyingCode" class="w-4 h-4 mr-2" />
                  <span>{{ isVerifyingCode ? 'Verifying...' : 'Verify Code' }}</span>
              </button>

              <div class="flex items-center justify-between text-xs text-gray-500 pt-2 border-t dark:border-gray-800">
                  <button
                      type="button"
                      @click="handleResendCode"
                      :disabled="isResendingCode"
                      class="hover:underline text-blue-600 dark:text-blue-400 font-semibold"
                  >
                      {{ isResendingCode ? 'Sending...' : 'Resend Code' }}
                  </button>
                  <button
                      type="button"
                      @click="isEmailVerificationRequired = false"
                      class="hover:underline"
                  >
                      Back to Sign In
                  </button>
              </div>
          </div>
      </form>
    </template>
  </GenericModal>
</template>

<style scoped>
@reference "tailwindcss";
</style>