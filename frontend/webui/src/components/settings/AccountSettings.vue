<script setup>
import { ref, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';

const authStore = useAuthStore();
const uiStore = useUiStore();

// --- Profile Form State ---
const profileForm = ref({
    first_name: '',
    family_name: '',
    email: '',
    birth_date: ''
});
const isProfileLoading = ref(false);

// --- Password Form State ---
const passwordForm = ref({
    current_password: '',
    new_password: ''
});
const confirmNewPassword = ref('');
const isPasswordLoading = ref(false);

// Populate form when component mounts
onMounted(() => {
    if (authStore.user) {
        profileForm.value.first_name = authStore.user.first_name || '';
        profileForm.value.family_name = authStore.user.family_name || '';
        profileForm.value.email = authStore.user.email || '';
        profileForm.value.birth_date = authStore.user.birth_date || '';
    }
});

// --- Actions ---

async function handleSaveProfile() {
    isProfileLoading.value = true;
    try {
        await authStore.updateUserProfile(profileForm.value);
    } catch (error) {
        // Error is handled by API interceptor
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
        // Clear fields on success
        passwordForm.value.current_password = '';
        passwordForm.value.new_password = '';
        confirmNewPassword.value = '';
    } catch (error) {
        // Error handled by interceptor
    } finally {
        isPasswordLoading.value = false;
    }
}
</script>

<template>
    <div class="space-y-8">
        <!-- User Profile Section -->
        <section>
            <h4 class="text-lg font-semibold mb-4 border-b dark:border-gray-600 pb-2">User Profile</h4>
            <form @submit.prevent="handleSaveProfile" class="space-y-4 max-w-md">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                        <label for="firstName" class="block text-sm font-medium">First Name</label>
                        <input type="text" id="firstName" v-model="profileForm.first_name" class="input-field mt-1" placeholder="Optional">
                    </div>
                    <div>
                        <label for="familyName" class="block text-sm font-medium">Family Name</label>
                        <input type="text" id="familyName" v-model="profileForm.family_name" class="input-field mt-1" placeholder="Optional">
                    </div>
                </div>
                <div>
                    <label for="email" class="block text-sm font-medium">Email Address</label>
                    <input type="email" id="email" v-model="profileForm.email" class="input-field mt-1" placeholder="Optional">
                </div>
                <div>
                    <label for="birthDate" class="block text-sm font-medium">Birth Date</label>
                    <input type="date" id="birthDate" v-model="profileForm.birth_date" class="input-field mt-1">
                </div>
                <div class="text-right">
                    <button type="submit" class="btn btn-primary" :disabled="isProfileLoading">
                        {{ isProfileLoading ? 'Saving...' : 'Save Profile' }}
                    </button>
                </div>
            </form>
        </section>

        <!-- Change Password Section -->
        <section>
            <h4 class="text-lg font-semibold mb-4 border-b dark:border-gray-600 pb-2">Change Password</h4>
            <form @submit.prevent="handleChangePassword" class="space-y-4 max-w-md">
                <div>
                    <label for="currentPassword" class="block text-sm font-medium">Current Password</label>
                    <input type="password" id="currentPassword" v-model="passwordForm.current_password" required class="input-field mt-1" autocomplete="current-password">
                </div>
                <div>
                    <label for="newPassword" class="block text-sm font-medium">New Password</label>
                    <input type="password" id="newPassword" v-model="passwordForm.new_password" required minlength="8" class="input-field mt-1" autocomplete="new-password">
                </div>
                <div>
                    <label for="confirmPassword" class="block text-sm font-medium">Confirm New Password</label>
                    <input type="password" id="confirmPassword" v-model="confirmNewPassword" required class="input-field mt-1" autocomplete="new-password">
                </div>
                <div class="text-right">
                    <button type="submit" class="btn btn-primary" :disabled="isPasswordLoading">
                        {{ isPasswordLoading ? 'Changing...' : 'Change Password' }}
                    </button>
                </div>
            </form>
        </section>
    </div>
</template>