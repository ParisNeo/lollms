<script setup>
import { ref, computed } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconShieldCheck from '../../assets/icons/IconCheckCircle.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';

const authStore = useAuthStore();
const uiStore = useUiStore();

const username = ref('');
const password = ref('');
const isLoading = ref(false);

// 2FA / Email Verification View State
const is2FaStep = ref(false);
const verificationCode = ref('');
const tempAuthToken = ref('');
const emailHint = ref('');
const isVerifying = ref(false);
const isResending = ref(false);

async function handleLogin() {
    if (!username.value.trim() || !password.value) return;
    isLoading.value = true;
    try {
        const result = await authStore.login(username.value.trim(), password.value);
        if (result?.email_verification_required) {
            is2FaStep.value = true;
            tempAuthToken.value = result.temp_token;
            emailHint.value = result.email_hint || 'your registered email';
            verificationCode.value = '';
            uiStore.addNotification(`Verification code dispatched to ${emailHint.value}.`, 'info', 5000);
        }
    } catch (e) {
        // Handled in store
    } finally {
        isLoading.value = false;
    }
}

async function handleVerifyCode() {
    if (!verificationCode.value.trim() || !tempAuthToken.value) return;
    isVerifying.value = true;
    try {
        await authStore.verifyEmailCode(tempAuthToken.value, verificationCode.value.trim());
    } catch (e) {
        // Handled in store
    } finally {
        isVerifying.value = false;
    }
}

async function handleResendCode() {
    if (!tempAuthToken.value || isResending.value) return;
    isResending.value = true;
    try {
        await authStore.resendVerificationCode(tempAuthToken.value);
    } finally {
        isResending.value = false;
    }
}

function backToCredentials() {
    is2FaStep.value = false;
    verificationCode.value = '';
    tempAuthToken.value = '';
}

function openRegister() {
    uiStore.closeModal('login');
    uiStore.openModal('register');
}

function openForgotPassword() {
    uiStore.closeModal('login');
    uiStore.openModal('forgotPassword');
}
</script>

<template>
  <GenericModal modalName="login" :title="is2FaStep ? 'Two-Factor Email Verification' : 'Sign In to LoLLMs'" maxWidthClass="max-w-md">
    <template #body>
      <!-- STEP 1: CREDENTIALS -->
      <form v-if="!is2FaStep" @submit.prevent="handleLogin" class="space-y-4 py-2">
        <div>
          <label class="label">Username or Email</label>
          <input 
            v-model="username" 
            type="text" 
            class="input-field mt-1" 
            placeholder="Username or email address"
            required 
            autofocus 
          />
        </div>

        <div>
          <div class="flex justify-between items-center">
            <label class="label">Password</label>
            <button type="button" @click="openForgotPassword" class="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline">
              Forgot password?
            </button>
          </div>
          <input 
            v-model="password" 
            type="password" 
            class="input-field mt-1" 
            placeholder="••••••••"
            required 
          />
        </div>

        <div class="pt-2">
          <button type="submit" class="btn btn-primary w-full py-2.5 font-bold flex items-center justify-center gap-2 shadow-lg" :disabled="isLoading">
            <IconAnimateSpin v-if="isLoading" class="w-4 h-4 animate-spin" />
            <span>{{ isLoading ? 'Authenticating...' : 'Sign In' }}</span>
          </button>
        </div>

        <div class="text-center pt-2">
          <p class="text-xs text-gray-500 dark:text-gray-400">
            Don't have an account?
            <button type="button" @click="openRegister" class="text-blue-600 dark:text-blue-400 font-bold hover:underline ml-1">
              Register here
            </button>
          </p>
        </div>
      </form>

      <!-- STEP 2: 2FA EMAIL OTP VERIFICATION -->
      <form v-else @submit.prevent="handleVerifyCode" class="space-y-5 py-2 animate-in fade-in">
        <div class="p-4 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800/40 rounded-2xl flex items-start gap-3">
          <IconShieldCheck class="w-6 h-6 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
          <div class="text-xs leading-relaxed text-blue-900 dark:text-blue-200">
            <span class="font-bold block mb-0.5">Security Code Dispatched</span>
            We have sent a 6-digit login authorization code to <strong>{{ emailHint }}</strong>.
          </div>
        </div>

        <div>
          <label class="label text-center block mb-1">Enter 6-Digit Code</label>
          <input 
            v-model="verificationCode" 
            type="text" 
            maxlength="10"
            class="input-field text-center font-mono text-2xl font-bold tracking-widest py-3 uppercase"
            placeholder="000000"
            required 
            autofocus 
          />
        </div>

        <div class="flex items-center justify-between text-xs pt-1">
          <button type="button" @click="backToCredentials" class="text-gray-500 hover:text-gray-800 dark:hover:text-gray-200 flex items-center gap-1 font-semibold">
            <IconArrowLeft class="w-3.5 h-3.5" /> Back
          </button>
          <button type="button" @click="handleResendCode" :disabled="isResending" class="text-blue-600 dark:text-blue-400 hover:underline font-bold">
            {{ isResending ? 'Sending...' : 'Resend Code' }}
          </button>
        </div>

        <div>
          <button type="submit" class="btn btn-primary w-full py-2.5 font-bold flex items-center justify-center gap-2 shadow-lg" :disabled="isVerifying || !verificationCode.trim()">
            <IconAnimateSpin v-if="isVerifying" class="w-4 h-4 animate-spin" />
            <span>{{ isVerifying ? 'Verifying Code...' : 'Authorize Login' }}</span>
          </button>
        </div>
      </form>
    </template>
    <template #footer>
      <div></div>
    </template>
  </GenericModal>
</template>