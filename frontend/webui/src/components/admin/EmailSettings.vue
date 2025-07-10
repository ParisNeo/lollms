<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';

const adminStore = useAdminStore();

const form = ref({});
const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

const emailSettings = computed(() => {
    return adminStore.globalSettings.filter(s => s.category === 'Email Settings' || s.key === 'password_recovery_mode');
});

onMounted(() => {
    if (adminStore.globalSettings.length === 0) {
        adminStore.fetchGlobalSettings();
    } else {
        populateForm();
    }
});

watch(() => adminStore.globalSettings, populateForm, { deep: true });

watch(form, (newValue) => {
    hasChanges.value = JSON.stringify(newValue) !== pristineState;
}, { deep: true });

function populateForm() {
    const newFormState = {};
    if (emailSettings.value.length > 0) {
        emailSettings.value.forEach(setting => {
            newFormState[setting.key] = setting.value;
        });
        form.value = newFormState;
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
    }
}

async function handleSave() {
    isLoading.value = true;
    try {
        const payload = { ...form.value };
        
        // Ensure we don't send an empty password and overwrite the existing one.
        if (payload.smtp_password === null || payload.smtp_password === '') {
            delete payload.smtp_password;
        }

        await adminStore.updateGlobalSettings(payload);
        // After save, the password field should be cleared on the frontend for security
        if (payload.smtp_password) {
            form.value.smtp_password = '';
        }
        // The watcher on globalSettings will repopulate the pristine state
    } catch (error) {
        // Error is handled globally
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="p-6 border-b border-gray-200 dark:border-gray-700">
            <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                Email & Password Recovery
            </h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Configure the method for sending system emails and managing password recovery.
            </p>
        </div>
        <form v-if="Object.keys(form).length" @submit.prevent="handleSave" class="p-6">
            <div class="space-y-8">
                <!-- Main Mode Selector -->
                <div>
                    <label for="password_recovery_mode" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Email Sending Method</label>
                    <select id="password_recovery_mode" v-model="form.password_recovery_mode" class="input-field mt-1">
                        <option value="manual">Manual (Admin Managed)</option>
                        <option value="automatic">SMTP Server</option>
                        <option value="system_mail">System Mail Command</option>
                    </select>
                </div>

                <!-- Conditional Helper Text and Configuration -->
                <div class="mt-4">
                    <!-- Manual Mode Info -->
                    <div v-if="form.password_recovery_mode === 'manual'" class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                        <p class="text-sm text-gray-600 dark:text-gray-300">
                            In <span class="font-semibold">Manual Mode</span>, the system will not send any emails. When a user requests a password reset, a notification will be sent to administrators in the UI. Admins must then manually generate a reset link and send it to the user.
                        </p>
                    </div>

                    <!-- System Mail Mode Info -->
                    <div v-if="form.password_recovery_mode === 'system_mail'" class="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800/50 rounded-lg">
                        <p class="text-sm text-yellow-800 dark:text-yellow-200">
                            <span class="font-semibold">System Mail Mode</span> uses the server's built-in `mail` command (e.g., from `mailutils`). This is a simpler alternative to SMTP but requires the command to be installed and properly configured on the server's operating system.
                        </p>
                    </div>

                    <!-- SMTP Configuration Fields (Conditional) -->
                    <div v-if="form.password_recovery_mode === 'automatic'" class="space-y-6 pt-4">
                         <div class="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800/50 rounded-lg">
                            <p class="text-sm text-blue-800 dark:text-blue-200">
                                <span class="font-semibold">SMTP Mode</span> provides the most reliable way to send emails. Fill in your SMTP provider's details below.
                            </p>
                        </div>
                        <div class="grid grid-cols-1 gap-y-6 sm:grid-cols-2 sm:gap-x-6">
                            <div>
                                <label for="smtp_host" class="block text-sm font-medium text-gray-700 dark:text-gray-300">SMTP Host</label>
                                <input type="text" id="smtp_host" v-model="form.smtp_host" class="input-field mt-1">
                            </div>
                             <div>
                                <label for="smtp_port" class="block text-sm font-medium text-gray-700 dark:text-gray-300">SMTP Port</label>
                                <input type="number" id="smtp_port" v-model="form.smtp_port" class="input-field mt-1">
                            </div>
                             <div class="sm:col-span-2">
                                <label for="smtp_from_email" class="block text-sm font-medium text-gray-700 dark:text-gray-300">From Email Address</label>
                                <input type="email" id="smtp_from_email" v-model="form.smtp_from_email" class="input-field mt-1">
                            </div>
                             <div class="sm:col-span-2">
                                <label for="smtp_user" class="block text-sm font-medium text-gray-700 dark:text-gray-300">SMTP Username</label>
                                <input type="text" id="smtp_user" v-model="form.smtp_user" class="input-field mt-1" autocomplete="off">
                            </div>
                            <div class="sm:col-span-2">
                                <label for="smtp_password" class="block text-sm font-medium text-gray-700 dark:text-gray-300">SMTP Password</label>
                                <input type="password" id="smtp_password" v-model="form.smtp_password" class="input-field mt-1" placeholder="Leave blank to keep existing password" autocomplete="new-password">
                            </div>
                             <div class="relative flex items-start">
                                <div class="flex h-6 items-center">
                                    <input id="smtp_use_tls" v-model="form.smtp_use_tls" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600">
                                </div>
                                <div class="ml-3 text-sm leading-6">
                                    <label for="smtp_use_tls" class="font-medium text-gray-900 dark:text-gray-100">Use TLS</label>
                                    <p class="text-gray-500 dark:text-gray-400">Enable TLS encryption for the connection.</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Save Button -->
            <div class="mt-8 pt-5 border-t border-gray-200 dark:border-gray-700">
                <div class="flex justify-end">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">
                        {{ isLoading ? 'Saving...' : 'Save Settings' }}
                    </button>
                </div>
            </div>
        </form>
         <div v-else class="p-6 text-center">
            <p class="text-gray-500">
                {{ adminStore.isLoadingSettings ? 'Loading settings...' : 'Could not load email settings.' }}
            </p>
        </div>
    </div>
</template>