<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import { useTasksStore } from '../../stores/tasks';
import apiClient from '../../services/api';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';


const authStore = useAuthStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();

const user = computed(() => authStore.user);

const profileForm = ref({
    first_name: '',
    family_name: '',
    email: '',
    birth_date: '',
    receive_notification_emails: true,
    is_searchable: true,
});
const isProfileLoading = ref(false);
const isProfileDirty = ref(false);
let pristineProfileState = '{}';

const passwordForm = ref({
    current_password: '',
    new_password: ''
});
const confirmNewPassword = ref('');
const isPasswordLoading = ref(false);
const showCurrentPassword = ref(false);
const showNewPassword = ref(false);

const isUploadingIcon = ref(false);
const fileInput = ref(null);

// ── Token usage & quota ────────────────────────────────────────────────────
// Pulled from GET /api/auth/me/token-quota. When quotas are disabled (or the
// user is exempt) we MUST tell the user explicitly that they have no limits,
// rather than showing empty/zeroed progress bars.
const quota = computed(() => authStore.myTokenQuota);
const isLoadingQuota = computed(() => authStore.isLoadingMyTokenQuota);

const quotaIsUnlimited = computed(() => {
    const q = quota.value;
    if (!q) return true;
    // Not enforced at all, or exempt => no hard limits apply.
    if (!q.enforced || q.exempt) return true;
    // Enforced but both directions unlimited (max <= 0) => effectively no limit.
    return (Number(q.input_max) <= 0) && (Number(q.output_max) <= 0);
});

const quotaStatusLabel = computed(() => {
    const q = quota.value;
    if (!q) return null;
    if (q.exempt) return 'Exempt — no limits apply to your account';
    if (!q.enforced) return 'Quotas are disabled by the administrator — you have no limits';
    if (quotaIsUnlimited.value) return 'No token limits configured';
    if (q.exhausted) return 'Quota exhausted — generation is paused until reset';
    return 'Quota active';
});

const quotaStatusTone = computed(() => {
    const q = quota.value;
    if (!q) return 'neutral';
    if (q.exempt || !q.enforced || quotaIsUnlimited.value) return 'ok';
    if (q.exhausted) return 'danger';
    return 'active';
});

function quotaPct(used, max) {
    if (!max || Number(max) <= 0) return 0;
    return Math.min(100, Math.round((Number(used || 0) / Number(max)) * 100));
}
const inputPct = computed(() => quotaPct(quota.value?.input_used, quota.value?.input_max));
const outputPct = computed(() => quotaPct(quota.value?.output_used, quota.value?.output_max));

const quotaResetLabel = computed(() => {
    const r = quota.value?.reset_at;
    if (!r) return null;
    try {
        return new Date(r).toLocaleString();
    } catch {
        return String(r);
    }
});

function formatInt(n) {
    return (Number(n) || 0).toLocaleString();
}

const isAdmin = computed(() => authStore.isAdmin);
const isTtsConfigured = computed(() => !!user.value?.tts_binding_model_name);
const isSttConfigured = computed(() => !!user.value?.stt_binding_model_name);
const isTtiConfigured = computed(() => !!user.value?.tti_binding_model_name);

function populateProfileForm() {
    if (user.value) {
        profileForm.value.first_name = user.value.first_name || '';
        profileForm.value.family_name = user.value.family_name || '';
        profileForm.value.email = user.value.email || '';
        profileForm.value.birth_date = user.value.birth_date || '';
        profileForm.value.receive_notification_emails = user.value.receive_notification_emails;
        profileForm.value.is_searchable = user.value.is_searchable;
        pristineProfileState = JSON.stringify(profileForm.value);
    }
}

onMounted(() => {
    populateProfileForm();
    authStore.fetchMyTokenQuota();
});

watch(user, populateProfileForm, { deep: true });
watch(profileForm, (newVal) => {
    isProfileDirty.value = JSON.stringify(newVal) !== pristineProfileState;
}, { deep: true });

async function handleSaveProfile() {
    isProfileLoading.value = true;
    try {
        const pristine = JSON.parse(pristineProfileState);
        const dirtyFields = {};
        let hasChanges = false;
        for (const key in profileForm.value) {
            if (profileForm.value[key] !== pristine[key]) {
                dirtyFields[key] = profileForm.value[key];
                hasChanges = true;
            }
        }

        if (hasChanges) {
            const payload = { ...dirtyFields };
            
            if (payload.email === '') {
                payload.email = null;
            }
            if (payload.birth_date === '') {
                payload.birth_date = null;
            }

            await authStore.updateUserProfile(payload);
        } else {
            uiStore.addNotification("No changes to save.", "info");
        }
    } catch (error) {
        // Error is handled by the global interceptor
    } finally {
        isProfileLoading.value = false;
    }
}

async function handleChangePassword() {
    if (passwordForm.value.new_password !== confirmNewPassword.value) {
        uiStore.addNotification("New passwords do not match.", 'error');
        return;
    }
    if (passwordForm.value.new_password.length < 8) {
        uiStore.addNotification("New password must be at least 8 characters long.", 'error');
        return;
    }

    isPasswordLoading.value = true;
    try {
        await authStore.changePassword(passwordForm.value);
        passwordForm.value.current_password = '';
        passwordForm.value.new_password = '';
        confirmNewPassword.value = '';
    } catch (error) {
        // Error is handled by the global interceptor
    } finally {
        isPasswordLoading.value = false;
    }
}

const triggerFileInput = () => {
  fileInput.value?.click();
};

const onIconFileChange = async (event) => {
  const file = event.target.files[0];
  if (!file) return;

  isUploadingIcon.value = true;
  uiStore.addNotification('Uploading icon...', 'info');

  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await apiClient.put('/api/auth/me/icon', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    
    if (authStore.user) {
      authStore.user.icon = response.data.icon_url;
    }
    
    uiStore.addNotification('Icon updated successfully!', 'success');
  } catch (error) {
    uiStore.addNotification('Icon upload failed.', 'error');
  } finally {
    isUploadingIcon.value = false;
    if (fileInput.value) {
      fileInput.value.value = '';
    }
  }
};

async function handleGenerateAvatar() {
    const { confirmed, value } = await uiStore.showConfirmation({
        title: 'Generate New Avatar',
        message: 'Enter an optional prompt to guide the AI. If left blank, a prompt will be generated from your profile information.',
        confirmText: 'Generate',
        inputType: 'textarea',
        inputPlaceholder: 'e.g., a professional photo, pixel art style...'
    });

    if (confirmed) {
        try {
            const task = await authStore.generateAvatar(value || null);
            if (task) {
                uiStore.openModal('tasksManager', { initialTaskId: task.id });
            } else {
                uiStore.addNotification('Failed to start avatar generation task. Check server logs for details.', 'error');
            }
        } catch (error) {
            console.error("Error during handleGenerateAvatar:", error);
            uiStore.addNotification('An unexpected error occurred while trying to generate the avatar.', 'error');
        }
    }
}
</script>

<template>
    <div v-if="user" class="space-y-10">
        <!-- User Profile Section -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
            <div class="p-4 sm:p-6">
                <h2 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">Profile</h2>
                <p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">Manage your public profile and personal information.</p>
            </div>
            <div class="border-t border-gray-200 dark:border-gray-700 p-4 sm:p-6">
                <form @submit.prevent="handleSaveProfile" class="flex flex-col md:flex-row gap-8">
                    <!-- Avatar Section -->
                    <div class="shrink-0 flex flex-col items-center space-y-2 w-full md:w-40">
                        <UserAvatar :icon="user.icon" :username="user.username" size-class="h-28 w-28" />
                        <input
                            type="file"
                            ref="fileInput"
                            @change="onIconFileChange"
                            accept="image/png, image/jpeg, image/webp"
                            class="hidden"
                        />
                        <button
                            type="button"
                            @click="triggerFileInput"
                            :disabled="isUploadingIcon"
                            class="btn btn-secondary w-full"
                        >
                            {{ isUploadingIcon ? 'Uploading...' : 'Change Icon' }}
                        </button>
                        <button
                            v-if="isTtiConfigured"
                            type="button"
                            @click="handleGenerateAvatar"
                            class="btn btn-secondary-outline w-full"
                        >
                            Generate Avatar
                        </button>
                        <p class="text-xs text-center text-gray-500 dark:text-gray-400">Max 5MB (JPG, PNG, WEBP)</p>
                    </div>

                    <!-- Profile Info Form -->
                    <div class="grow space-y-6">
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
                            <div>
                                <label for="firstName" class="block text-sm font-medium text-gray-700 dark:text-gray-300">First Name</label>
                                <input type="text" id="firstName" v-model="profileForm.first_name" class="input-field mt-1" placeholder="Jane">
                            </div>
                            <div>
                                <label for="familyName" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Family Name</label>
                                <input type="text" id="familyName" v-model="profileForm.family_name" class="input-field mt-1" placeholder="Doe">
                            </div>
                        </div>
                        <div>
                            <label for="email" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Email Address</label>
                            <input type="email" id="email" v-model="profileForm.email" class="input-field mt-1" placeholder="you@example.com">
                        </div>
                        <div>
                            <label for="birthDate" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Birth Date</label>
                            <input type="date" id="birthDate" v-model="profileForm.birth_date" class="input-field mt-1">
                        </div>
                        
                         <div class="space-y-4 pt-4 border-t dark:border-gray-600">
                            <div class="relative flex items-start">
                                <div class="flex h-6 items-center">
                                    <input id="is_searchable" v-model="profileForm.is_searchable" type="checkbox" class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-600">
                                </div>
                                <div class="ml-3 text-sm leading-6">
                                    <label for="is_searchable" class="font-medium text-gray-900 dark:text-gray-100">Profile Searchability</label>
                                    <p class="text-gray-500 dark:text-gray-400">Allow other users to find your profile in searches.</p>
                                </div>
                            </div>
                             <div class="relative flex items-start">
                                <div class="flex h-6 items-center">
                                    <input id="receive_notification_emails" v-model="profileForm.receive_notification_emails" type="checkbox" class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-600">
                                </div>
                                <div class="ml-3 text-sm leading-6">
                                    <label for="receive_notification_emails" class="font-medium text-gray-900 dark:text-gray-100">Notification Emails</label>
                                    <p class="text-gray-500 dark:text-gray-400">Receive emails for important events like password resets.</p>
                                </div>
                            </div>
                        </div>

                        <div class="flex justify-end">
                            <button type="submit" class="btn btn-primary" :disabled="isProfileLoading || !isProfileDirty">
                                {{ isProfileLoading ? 'Saving...' : 'Save Profile' }}
                            </button>
                        </div>
                    </div>
                </form>
            </div>
        </div>

        <!-- Token Usage & Quota Section -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
            <div class="p-4 sm:p-6">
                <div class="flex items-start justify-between gap-3 flex-wrap">
                    <div>
                        <h2 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">Token Usage &amp; Quota</h2>
                        <p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">
                            Your input (prompt) and output (completion) token consumption for the current quota period.
                        </p>
                    </div>
                    <button type="button" class="btn btn-secondary btn-sm" @click="authStore.fetchMyTokenQuota()" :disabled="isLoadingQuota">
                        {{ isLoadingQuota ? 'Refreshing...' : 'Refresh' }}
                    </button>
                </div>
            </div>
            <div class="border-t border-gray-200 dark:border-gray-700 p-4 sm:p-6">
                <div v-if="isLoadingQuota && !quota" class="text-sm text-gray-500 dark:text-gray-400">Loading your token usage…</div>
                <div v-else-if="!quota" class="text-sm text-gray-500 dark:text-gray-400">
                    Token usage information is unavailable right now.
                </div>
                <div v-else class="space-y-5">
                    <!-- Status banner: explicit about "no limits" vs "active quota" -->
                    <div
                        class="rounded-lg px-4 py-3 text-sm font-medium border"
                        :class="{
                            'bg-emerald-50 border-emerald-200 text-emerald-800 dark:bg-emerald-900/30 dark:border-emerald-700 dark:text-emerald-200': quotaStatusTone === 'ok',
                            'bg-amber-50 border-amber-200 text-amber-800 dark:bg-amber-900/30 dark:border-amber-700 dark:text-amber-200': quotaStatusTone === 'active',
                            'bg-rose-50 border-rose-200 text-rose-800 dark:bg-rose-900/30 dark:border-rose-700 dark:text-rose-200': quotaStatusTone === 'danger',
                            'bg-gray-50 border-gray-200 text-gray-700 dark:bg-gray-900/30 dark:border-gray-700 dark:text-gray-300': quotaStatusTone === 'neutral'
                        }"
                    >
                        {{ quotaStatusLabel }}
                        <span v-if="quotaStatusTone !== 'ok' && quotaResetLabel" class="block mt-1 text-xs font-normal opacity-80">
                            Next reset: {{ quotaResetLabel }}
                        </span>
                        <span v-if="quotaStatusTone === 'danger' && quota.message" class="block mt-1 text-xs font-normal opacity-90">
                            {{ quota.message }}
                        </span>
                    </div>

                    <!-- Usage meters — only shown when at least one direction
                         actually has a limit. When quotas are disabled/exempt or
                         fully unlimited, the banner above already says so, and
                         empty meters would only add confusion. -->
                    <div v-if="!quotaIsUnlimited" class="grid grid-cols-1 sm:grid-cols-2 gap-5">
                        <div>
                            <div class="flex justify-between text-xs font-semibold mb-1 text-gray-600 dark:text-gray-300">
                                <span>Input (prompt) tokens</span>
                                <span class="font-mono">
                                    {{ formatInt(quota.input_used) }}
                                    <template v-if="Number(quota.input_max) > 0"> / {{ formatInt(quota.input_max) }}</template>
                                    <template v-else> · unlimited</template>
                                </span>
                            </div>
                            <div class="h-2 rounded-full overflow-hidden bg-gray-200 dark:bg-gray-700">
                                <div
                                    class="h-full transition-all"
                                    :class="Number(quota.input_max) > 0 && quota.input_exhausted ? 'bg-rose-500' : 'bg-sky-500'"
                                    :style="{ width: Number(quota.input_max) > 0 ? inputPct + '%' : '0%' }"
                                ></div>
                            </div>
                            <p v-if="Number(quota.input_max) <= 0" class="mt-1 text-[11px] text-gray-400 dark:text-gray-500">No input limit</p>
                        </div>
                        <div>
                            <div class="flex justify-between text-xs font-semibold mb-1 text-gray-600 dark:text-gray-300">
                                <span>Output (completion) tokens</span>
                                <span class="font-mono">
                                    {{ formatInt(quota.output_used) }}
                                    <template v-if="Number(quota.output_max) > 0"> / {{ formatInt(quota.output_max) }}</template>
                                    <template v-else> · unlimited</template>
                                </span>
                            </div>
                            <div class="h-2 rounded-full overflow-hidden bg-gray-200 dark:bg-gray-700">
                                <div
                                    class="h-full transition-all"
                                    :class="Number(quota.output_max) > 0 && quota.output_exhausted ? 'bg-rose-500' : 'bg-rose-400'"
                                    :style="{ width: Number(quota.output_max) > 0 ? outputPct + '%' : '0%' }"
                                ></div>
                            </div>
                            <p v-if="Number(quota.output_max) <= 0" class="mt-1 text-[11px] text-gray-400 dark:text-gray-500">No output limit</p>
                        </div>
                    </div>

                    <p class="text-[11px] text-gray-400 dark:text-gray-500">
                        Period: <span class="font-mono uppercase">{{ quota.period }}</span>
                        <template v-if="quotaResetLabel && !quotaIsUnlimited"> · Resets {{ quotaResetLabel }}</template>
                    </p>
                </div>
            </div>
        </div>

        <!-- Change Password Section -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
             <div class="px-4 py-5 sm:p-6">
                <h2 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">Change Password</h2>
                <p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">Ensure your account is using a long, random password to stay secure.</p>
            </div>
             <div class="border-t border-gray-200 dark:border-gray-700">
                <form @submit.prevent="handleChangePassword" class="p-4 sm:p-6 space-y-6">
                    <div>
                        <label for="currentPassword" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Current Password</label>
                        <div class="mt-1 relative">
                            <input :type="showCurrentPassword ? 'text' : 'password'" id="currentPassword" v-model="passwordForm.current_password" required class="input-field pr-10" autocomplete="current-password">
                            <button type="button" @click="showCurrentPassword = !showCurrentPassword" class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                                <IconEyeOff v-if="showCurrentPassword" class="w-5 h-5" />
                                <IconEye v-else class="w-5 h-5" />
                            </button>
                        </div>
                    </div>
                    <div>
                        <label for="newPassword" class="block text-sm font-medium text-gray-700 dark:text-gray-300">New Password</label>
                         <div class="mt-1 relative">
                            <input :type="showNewPassword ? 'text' : 'password'" id="newPassword" v-model="passwordForm.new_password" required minlength="8" class="input-field pr-10" autocomplete="new-password">
                            <button type="button" @click="showNewPassword = !showNewPassword" class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                                <IconEyeOff v-if="showNewPassword" class="w-5 h-5" />
                                <IconEye v-else class="w-5 h-5" />
                            </button>
                        </div>
                    </div>
                    <div>
                        <label for="confirmPassword" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Confirm New Password</label>
                        <div class="mt-1 relative">
                            <input :type="showNewPassword ? 'text' : 'password'" id="confirmPassword" v-model="confirmNewPassword" required class="input-field pr-10" autocomplete="new-password">
                        </div>
                    </div>
                    <div class="flex justify-end">
                        <button type="submit" class="btn btn-primary" :disabled="isPasswordLoading">
                            {{ isPasswordLoading ? 'Changing...' : 'Change Password' }}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</template>