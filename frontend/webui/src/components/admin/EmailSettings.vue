<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';

import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconShieldCheck from '../../assets/icons/IconCheckCircle.vue';
import IconSend from '../../assets/icons/IconSend.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const { globalSettings, isLoadingSettings } = storeToRefs(adminStore);

const isSaving = ref(false);
const isTestingEmail = ref(false);
const testRecipient = ref('');

const emailForm = ref({
    password_recovery_mode: 'manual',
    smtp_host: '',
    smtp_port: 587,
    smtp_user: '',
    smtp_password: '',
    smtp_from_email: '',
    smtp_use_tls: true,
    // Email 2FA / Verification Options
    email_verification_enabled: false,
    email_verification_code_expiry_minutes: 10,
    email_verification_bypass_admins: false
});

const isDirty = ref(false);
let pristineSnapshot = '';

function getSettingVal(key, defaultVal) {
    const s = globalSettings.value.find(item => item.key === key);
    return s ? s.value : defaultVal;
}

function populate() {
    if (!globalSettings.value || globalSettings.value.length === 0) return;

    emailForm.value = {
        password_recovery_mode: getSettingVal('password_recovery_mode', 'manual'),
        smtp_host: getSettingVal('smtp_host', ''),
        smtp_port: getSettingVal('smtp_port', 587),
        smtp_user: getSettingVal('smtp_user', ''),
        smtp_password: getSettingVal('smtp_password', ''),
        smtp_from_email: getSettingVal('smtp_from_email', ''),
        smtp_use_tls: getSettingVal('smtp_use_tls', true),
        email_verification_enabled: getSettingVal('email_verification_enabled', false),
        email_verification_code_expiry_minutes: getSettingVal('email_verification_code_expiry_minutes', 10),
        email_verification_bypass_admins: getSettingVal('email_verification_bypass_admins', false)
    };

    pristineSnapshot = JSON.stringify(emailForm.value);
    isDirty.value = false;
}

onMounted(async () => {
    await adminStore.fetchGlobalSettings();
    populate();
});

watch(globalSettings, populate, { deep: true });

watch(emailForm, (newVal) => {
    isDirty.value = JSON.stringify(newVal) !== pristineSnapshot;
}, { deep: true });

async function handleSave() {
    isSaving.value = true;
    try {
        await adminStore.updateGlobalSettings(emailForm.value);
        pristineSnapshot = JSON.stringify(emailForm.value);
        isDirty.value = false;
    } catch (e) {
        // Store notification handles error
    } finally {
        isSaving.value = false;
    }
}

async function handleTestEmail() {
    if (!testRecipient.value.trim() || !testRecipient.value.includes('@')) {
        uiStore.addNotification('Please enter a valid recipient email address for testing.', 'warning');
        return;
    }

    if (isDirty.value) {
        await handleSave();
    }

    isTestingEmail.value = true;
    try {
        const formData = new FormData();
        formData.append('to_email', testRecipient.value.trim());

        const res = await apiClient.post('/api/admin/test-email-dispatch', formData);
        uiStore.addNotification(res.data.message || 'Test email dispatched successfully!', 'success', 6000);
    } catch (e) {
        const msg = e.response?.data?.detail || 'Test email delivery failed.';
        uiStore.addNotification(msg, 'error', 7000);
    } finally {
        isTestingEmail.value = false;
    }
}
</script>

<template>
  <div class="bg-white dark:bg-gray-800 shadow-md rounded-2xl border border-gray-100 dark:border-gray-700/60 overflow-hidden">
    <!-- Header -->
    <div class="p-6 border-b border-gray-200 dark:border-gray-700">
      <h3 class="text-xl font-bold text-gray-900 dark:text-white">Email & Security Verification Settings</h3>
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Configure outbound email delivery (System Mail, SMTP, Gmail) and enforce Email 2FA verification for login security.
      </p>
    </div>

    <form @submit.prevent="handleSave" class="p-6 space-y-8">
      
      <!-- ── SECTION 1: EMAIL VERIFICATION (2FA) GATE ── -->
      <div class="space-y-4">
        <div class="flex items-center gap-2">
            <IconShieldCheck class="w-5 h-5 text-blue-500" />
            <h4 class="text-base font-bold text-gray-900 dark:text-white">Email Verification & Two-Factor Authentication (2FA)</h4>
        </div>
        <p class="text-xs text-gray-500 dark:text-gray-400">
            When enabled, users logging in with a password will receive a 6-digit OTP code on their registered email to authorize access.
        </p>

        <div class="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-2xl border dark:border-gray-700 space-y-4">
            <!-- Master Toggle -->
            <div class="flex items-center justify-between">
                <span class="grow flex flex-col pr-4">
                    <span class="text-sm font-bold text-gray-900 dark:text-gray-100">Enforce Email 2FA on Sign-In</span>
                    <span class="text-xs text-gray-500">Require an email OTP code for all user logins (Deactivated by default).</span>
                </span>
                <button 
                    @click="emailForm.email_verification_enabled = !emailForm.email_verification_enabled" 
                    type="button" 
                    :class="[emailForm.email_verification_enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200']"
                >
                    <span :class="[emailForm.email_verification_enabled ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200']"></span>
                </button>
            </div>

            <!-- Additional 2FA Parameters -->
            <div v-if="emailForm.email_verification_enabled" class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t dark:border-gray-700/60 animate-in fade-in">
                <div>
                    <label class="label text-xs font-bold">Code Expiry Time (Minutes)</label>
                    <input 
                        v-model.number="emailForm.email_verification_code_expiry_minutes" 
                        type="number" 
                        min="1" 
                        max="60" 
                        class="input-field mt-1"
                    />
                    <p class="text-[10px] text-gray-400 mt-1">Duration before the 6-digit code becomes invalid (default: 10m).</p>
                </div>

                <div class="flex items-center justify-between p-3 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700">
                    <span class="flex flex-col pr-2">
                        <span class="text-xs font-bold">Bypass for Admins</span>
                        <span class="text-[10px] text-gray-400">Permit admin password login without email code if mail services fail.</span>
                    </span>
                    <button 
                        @click="emailForm.email_verification_bypass_admins = !emailForm.email_verification_bypass_admins" 
                        type="button" 
                        :class="[emailForm.email_verification_bypass_admins ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors']"
                    >
                        <span :class="[emailForm.email_verification_bypass_admins ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition']"></span>
                    </button>
                </div>
            </div>
        </div>
      </div>

      <!-- ── SECTION 2: OUTBOUND TRANSPORT MODE ── -->
      <div class="space-y-4 pt-6 border-t dark:border-gray-700">
        <h4 class="text-base font-bold text-gray-900 dark:text-white">Email Dispatch Method</h4>
        
        <div>
          <label class="label">Mail Transport System</label>
          <select v-model="emailForm.password_recovery_mode" class="input-field mt-1">
            <option value="manual">Manual / Disabled (No outbound email)</option>
            <option value="system_mail">System Mail Command (sendmail / mailx / mail)</option>
            <option value="smtp">Custom SMTP Server</option>
            <option value="gmail">Gmail Service</option>
            <option value="outlook">Outlook (Windows Only)</option>
          </select>
          <p class="text-xs text-gray-500 mt-1">
            <span v-if="emailForm.password_recovery_mode === 'system_mail'" class="text-blue-600 dark:text-blue-400 font-bold">
              ✓ Uses local system binary (sendmail/mailx). No external credentials required.
            </span>
            <span v-else-if="emailForm.password_recovery_mode === 'smtp'">
              Requires valid SMTP credentials and host configuration below.
            </span>
            <span v-else-if="emailForm.password_recovery_mode === 'gmail'">
              Uses Google SMTP servers with your Gmail address and App Password.
            </span>
          </p>
        </div>

        <!-- SMTP & Gmail Parameters -->
        <div v-if="['smtp', 'gmail'].includes(emailForm.password_recovery_mode)" class="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-2xl border dark:border-gray-700 space-y-4 animate-in fade-in">
          <div v-if="emailForm.password_recovery_mode === 'smtp'" class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="label text-xs">SMTP Host</label>
              <input v-model="emailForm.smtp_host" type="text" class="input-field mt-1" placeholder="smtp.example.com" />
            </div>
            <div>
              <label class="label text-xs">SMTP Port</label>
              <input v-model.number="emailForm.smtp_port" type="number" class="input-field mt-1" placeholder="587" />
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="label text-xs">User / Email</label>
              <input v-model="emailForm.smtp_user" type="text" class="input-field mt-1" placeholder="user@example.com" />
            </div>
            <div>
              <label class="label text-xs">Password / App Password</label>
              <input v-model="emailForm.smtp_password" type="password" class="input-field mt-1" placeholder="••••••••" />
            </div>
          </div>

          <div v-if="emailForm.password_recovery_mode === 'smtp'" class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="label text-xs">From Address</label>
              <input v-model="emailForm.smtp_from_email" type="text" class="input-field mt-1" placeholder="noreply@example.com" />
            </div>
            <div class="flex items-center justify-between p-3 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 self-end h-[42px]">
              <span class="text-xs font-bold">Use TLS Encryption</span>
              <button 
                @click="emailForm.smtp_use_tls = !emailForm.smtp_use_tls" 
                type="button" 
                :class="[emailForm.smtp_use_tls ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors']"
              >
                <span :class="[emailForm.smtp_use_tls ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition']"></span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- ── SECTION 3: TEST EMAIL DIAGNOSTICS ── -->
      <div v-if="emailForm.password_recovery_mode !== 'manual'" class="space-y-3 pt-6 border-t dark:border-gray-700 animate-in fade-in">
        <h4 class="text-sm font-bold text-gray-900 dark:text-white flex items-center gap-2">
          <span>🧪</span> Live Delivery Diagnostic
        </h4>
        <div class="flex flex-col sm:flex-row gap-3 items-center">
          <input 
            v-model="testRecipient" 
            type="email" 
            placeholder="test-recipient@example.com" 
            class="input-field grow"
          />
          <button 
            type="button" 
            @click="handleTestEmail" 
            class="btn btn-secondary flex items-center gap-2 shrink-0 w-full sm:w-auto"
            :disabled="isTestingEmail || !testRecipient.trim()"
          >
            <IconAnimateSpin v-if="isTestingEmail" class="w-4 h-4 animate-spin" />
            <IconSend v-else class="w-4 h-4" />
            <span>{{ isTestingEmail ? 'Sending Test...' : 'Send Test Email' }}</span>
          </button>
        </div>
      </div>

      <!-- Save Actions -->
      <div class="flex justify-end gap-3 pt-6 border-t dark:border-gray-700">
        <button type="submit" class="btn btn-primary px-8 flex items-center gap-2" :disabled="isSaving || !isDirty">
          <IconAnimateSpin v-if="isSaving" class="w-4 h-4 animate-spin" />
          <span>{{ isSaving ? 'Saving Settings...' : 'Save Email Settings' }}</span>
        </button>
      </div>
    </form>
  </div>
</template>