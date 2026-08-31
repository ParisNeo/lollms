<!-- frontend/webui/src/views/ResetPasswordView.vue -->
<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import apiClient from '../services/api';
import appLogo from '../assets/logo.png';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconCheckCircle from '../assets/icons/IconCheckCircle.vue';
import IconEye from '../assets/icons/IconEye.vue';
import IconEyeOff from '../assets/icons/IconEyeOff.vue';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const token = ref('');
const newPassword = ref('');
const confirmPassword = ref('');
const isLoading = ref(false);
const errorMessage = ref('');
const successMessage = ref('');
const isNewPasswordVisible = ref(false);
const isConfirmPasswordVisible = ref(false);
const countdown = ref(3);

onMounted(() => {
    // Ensure any stale token from a previous session is removed so it cannot conflict
    localStorage.removeItem('lollms-token');
    authStore.token = null;
    authStore.user = null;
    authStore.disconnectWebSocket();

    // Extract token from query parameters
    token.value = (route.query.token || '').toString().trim();
    if (!token.value) {
        errorMessage.value = 'No reset token provided. Please click the exact link from your email.';
    }
});

const passwordsMatch = computed(() => {
    if (!newPassword.value || !confirmPassword.value) return true;
    return newPassword.value === confirmPassword.value;
});

const isFormValid = computed(() => {
    return token.value && 
           newPassword.value.length >= 8 && 
           newPassword.value === confirmPassword.value && 
           !isLoading.value;
});

const handleReset = async () => {
    errorMessage.value = '';

    if (!token.value) {
        errorMessage.value = 'Reset token is missing.';
        return;
    }

    if (newPassword.value.length < 8) {
        errorMessage.value = 'Password must be at least 8 characters long.';
        return;
    }

    if (newPassword.value !== confirmPassword.value) {
        errorMessage.value = 'Passwords do not match.';
        return;
    }

    isLoading.value = true;
    try {
        const response = await apiClient.post('/api/auth/reset-password', {
            token: token.value,
            new_password: newPassword.value,
        });

        successMessage.value = response.data.message || 'Password successfully updated!';

        // Smooth countdown redirect to clean home page
        const timer = setInterval(() => {
            countdown.value -= 1;
            if (countdown.value <= 0) {
                clearInterval(timer);
                window.location.href = '/';
            }
        }, 1000);

    } catch (error) {
        errorMessage.value = error.response?.data?.detail || 'Invalid or expired password reset link. Please request a new one.';
    } finally {
        isLoading.value = false;
    }
};

const goToLogin = () => {
    window.location.href = '/';
};
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-950 flex flex-col justify-center items-center py-12 px-4 sm:px-6 lg:px-8 relative selection:bg-blue-500 selection:text-white">
    <!-- Ambient Background Lighting -->
    <div class="fixed inset-0 z-0 overflow-hidden pointer-events-none">
        <div class="absolute top-[-10%] left-[-10%] w-[80%] h-[60%] rounded-full bg-blue-500/10 dark:bg-blue-600/5 blur-[120px]"></div>
        <div class="absolute bottom-[-10%] right-[-10%] w-[80%] h-[60%] rounded-full bg-purple-500/10 dark:bg-purple-600/5 blur-[120px]"></div>
    </div>

    <div class="sm:mx-auto sm:w-full sm:max-w-md relative z-10 text-center">
      <div class="inline-block p-4 bg-white dark:bg-gray-900 rounded-3xl shadow-xl border border-gray-100 dark:border-gray-800 mb-6">
        <img :src="appLogo" alt="LoLLMs Logo" class="h-16 w-auto object-contain mx-auto" />
      </div>
      <h2 class="text-2xl sm:text-3xl font-black tracking-tight text-gray-900 dark:text-white">
        Reset Your Password
      </h2>
      <p class="mt-2 text-xs font-medium text-gray-500 dark:text-gray-400">
        Enter a strong, secure new password for your account.
      </p>
    </div>

    <div class="mt-8 sm:mx-auto sm:w-full sm:max-w-md relative z-10 w-full">
      <div class="bg-white dark:bg-gray-900 py-8 px-6 sm:px-10 shadow-2xl rounded-3xl border border-gray-150 dark:border-gray-800 backdrop-blur-xl">
        
        <!-- Missing Token Warning -->
        <div v-if="!token && !successMessage" class="text-center space-y-4">
          <div class="p-4 bg-rose-50 dark:bg-rose-950/30 text-rose-700 dark:text-rose-300 rounded-2xl border border-rose-200 dark:border-rose-800/50 text-xs leading-relaxed font-semibold">
            {{ errorMessage }}
          </div>
          <button @click="goToLogin" class="btn btn-secondary w-full py-3 text-xs uppercase tracking-wider font-bold">
            Back to Home
          </button>
        </div>

        <!-- Success State -->
        <div v-else-if="successMessage" class="text-center space-y-5 animate-in fade-in zoom-in-95">
          <div class="w-16 h-16 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-500 rounded-full flex items-center justify-center mx-auto border border-emerald-200 dark:border-emerald-800 shadow-lg shadow-emerald-500/10">
            <IconCheckCircle class="w-10 h-10" />
          </div>
          <div>
            <h3 class="text-lg font-bold text-gray-900 dark:text-white">{{ successMessage }}</h3>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Redirecting to sign in within <span class="font-mono font-bold text-blue-500">{{ countdown }}s</span>...
            </p>
          </div>
          <button @click="goToLogin" class="btn btn-primary w-full py-3 text-xs uppercase tracking-widest font-black shadow-lg shadow-blue-500/20">
            Sign In Now &rarr;
          </button>
        </div>

        <!-- Password Entry Form -->
        <form v-else @submit.prevent="handleReset" class="space-y-5">
          <!-- New Password Input -->
          <div>
            <label for="new-password" class="block text-xs font-black uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
              New Password
            </label>
            <div class="relative">
              <input
                v-model="newPassword"
                :type="isNewPasswordVisible ? 'text' : 'password'"
                id="new-password"
                required
                minlength="8"
                :disabled="isLoading"
                class="input-field w-full pr-10 text-sm py-2.5 rounded-xl"
                placeholder="At least 8 characters"
                autocomplete="new-password"
              />
              <button
                type="button"
                @click="isNewPasswordVisible = !isNewPasswordVisible"
                class="absolute inset-y-0 right-0 flex items-center px-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                tabindex="-1"
              >
                <IconEyeOff v-if="isNewPasswordVisible" class="h-4 w-4" />
                <IconEye v-else class="h-4 w-4" />
              </button>
            </div>
          </div>

          <!-- Confirm Password Input -->
          <div>
            <label for="confirm-password" class="block text-xs font-black uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
              Confirm Password
            </label>
            <div class="relative">
              <input
                v-model="confirmPassword"
                :type="isConfirmPasswordVisible ? 'text' : 'password'"
                id="confirm-password"
                required
                :disabled="isLoading"
                class="input-field w-full pr-10 text-sm py-2.5 rounded-xl"
                :class="{'border-rose-500 focus:border-rose-500': !passwordsMatch}"
                placeholder="Re-enter new password"
                autocomplete="new-password"
              />
              <button
                type="button"
                @click="isConfirmPasswordVisible = !isConfirmPasswordVisible"
                class="absolute inset-y-0 right-0 flex items-center px-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                tabindex="-1"
              >
                <IconEyeOff v-if="isConfirmPasswordVisible" class="h-4 w-4" />
                <IconEye v-else class="h-4 w-4" />
              </button>
            </div>
            <p v-if="!passwordsMatch" class="text-[11px] text-rose-500 font-medium mt-1">
              Passwords do not match.
            </p>
          </div>

          <!-- Error Alert Banner -->
          <div v-if="errorMessage" class="p-3 bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 rounded-xl border border-rose-200 dark:border-rose-800 text-xs font-medium" role="alert">
            {{ errorMessage }}
          </div>

          <!-- Submit Button -->
          <div class="pt-2">
            <button
              type="submit"
              class="btn btn-primary w-full py-3 text-xs uppercase tracking-widest font-black shadow-xl shadow-blue-500/20"
              :disabled="!isFormValid"
            >
              <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
              <span>{{ isLoading ? 'Updating Password...' : 'Save New Password' }}</span>
            </button>
          </div>

          <div class="text-center pt-2">
            <a href="/" class="text-xs font-semibold text-gray-500 hover:text-blue-600 dark:hover:text-blue-400 transition-colors">
              Cancel & Return Home
            </a>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
@reference "tailwindcss";
</style>