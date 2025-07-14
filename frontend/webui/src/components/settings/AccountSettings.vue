<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';
import UserAvatar from '../ui/UserAvatar.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';

const authStore = useAuthStore();
const uiStore = useUiStore();

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

onMounted(populateProfileForm);

watch(user, populateProfileForm, { deep: true });
watch(profileForm, (newVal) => {
    isProfileDirty.value = JSON.stringify(newVal) !== pristineProfileState;
}, { deep: true });

async function handleSaveProfile() {
    isProfileLoading.value = true;
    try {
        await authStore.updateUserProfile(profileForm.value);
        // The watcher on `user` will reset the dirty state
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
                    <div class="flex-shrink-0 flex flex-col items-center space-y-2 w-full md:w-40">
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
                        <p class="text-xs text-center text-gray-500 dark:text-gray-400">Max 5MB (JPG, PNG, WEBP)</p>
                    </div>

                    <!-- Profile Info Form -->
                    <div class="flex-grow space-y-6">
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