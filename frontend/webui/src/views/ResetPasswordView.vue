<script setup>
import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import apiClient from '../services/api';
import appLogo from '../assets/logo.png';

const route = useRoute();
const router = useRouter();

const token = ref('');
const newPassword = ref('');
const confirmPassword = ref('');
const isLoading = ref(false);
const errorMessage = ref('');
const successMessage = ref('');
const isPasswordVisible = ref(false);

onMounted(() => {
  token.value = route.query.token || '';
  if (!token.value) {
    errorMessage.value = 'No reset token provided. Please use the link sent to you.';
  }
});

const togglePasswordVisibility = () => {
  isPasswordVisible.value = !isPasswordVisible.value;
};

const handleReset = async () => {
  errorMessage.value = '';

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
    successMessage.value = response.data.message;
    setTimeout(() => {
      router.push('/'); // Redirect to home/login after a short delay
    }, 3000);
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || 'An unexpected error occurred.';
  } finally {
    isLoading.value = false;
  }
};
</script>

<template>
  <div class="min-h-screen bg-gray-100 dark:bg-gray-900 flex flex-col justify-center items-center py-12 sm:px-6 lg:px-8">
    <div class="sm:mx-auto sm:w-full sm:max-w-md">
      <img :src="appLogo" alt="Application Logo" class="mx-auto h-20 w-auto" />
      <h2 class="mt-6 text-center text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
        Reset Your Password
      </h2>
    </div>

    <div class="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
      <div class="bg-white dark:bg-gray-800 py-8 px-4 shadow-lg sm:rounded-lg sm:px-10">
        <div v-if="!token">
          <p class="text-center text-red-500">{{ errorMessage }}</p>
        </div>
        <div v-else-if="successMessage">
          <p class="text-center text-green-600 dark:text-green-400">{{ successMessage }}</p>
           <p class="text-center text-sm text-gray-500 mt-2">You will be redirected shortly.</p>
        </div>
        <form v-else @submit.prevent="handleReset" class="space-y-6">
          <div>
            <label for="new-password" class="block text-sm font-medium text-gray-700 dark:text-gray-300">New Password</label>
            <div class="relative">
              <input
                v-model="newPassword"
                :type="isPasswordVisible ? 'text' : 'password'"
                id="new-password"
                required
                minlength="8"
                :disabled="isLoading"
                class="input-field mt-1 w-full pr-10"
                placeholder="Enter new password"
              />
              <button
                type="button"
                @click="togglePasswordVisibility"
                class="absolute inset-y-0 right-0 flex items-center px-3 text-gray-500 hover:text-gray-700"
              >
                <svg v-if="isPasswordVisible" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a9.97 9.97 0 01-1.563 3.029m-2.135-2.135A6.978 6.978 0 0112 17c-1.855 0-3.56-.736-4.807-1.938" /></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
              </button>
            </div>
          </div>
          <div>
            <label for="confirm-password" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Confirm New Password</label>
            <input
              v-model="confirmPassword"
              :type="isPasswordVisible ? 'text' : 'password'"
              id="confirm-password"
              required
              :disabled="isLoading"
              class="input-field mt-1 w-full"
              placeholder="Confirm new password"
            />
          </div>

          <div v-if="errorMessage" class="text-red-600 text-sm p-2 bg-red-100 dark:bg-red-900/50 rounded-md" role="alert">
            {{ errorMessage }}
          </div>

          <div>
            <button type="submit" class="btn btn-primary w-full" :disabled="isLoading">
              {{ isLoading ? 'Resetting...' : 'Set New Password' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>