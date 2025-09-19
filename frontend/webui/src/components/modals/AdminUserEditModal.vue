<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import GenericModal from './GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import apiClient from '../../services/api';

const uiStore = useUiStore();
const dataStore = useDataStore();

const { availableLollmsModels, isLoadingLollmsModels } = storeToRefs(dataStore);

const modalProps = computed(() => uiStore.modalData('adminUserEdit'));
const user = computed(() => modalProps.value?.user);
const onUserUpdated = computed(() => modalProps.value?.onUserUpdated);

const form = ref({
    is_admin: false,
    is_moderator: false,
    is_active: false,
    lollms_model_name: '',
    llm_ctx_size: null,
    safe_store_vectorizer: ''
});

const isLoading = ref(false);
const isGeneratingLink = ref(false);

watch(
    user,
    (newUser) => {
        if (newUser) {
            form.value = {
                is_admin: newUser.is_admin,
                is_moderator: newUser.is_moderator,
                is_active: newUser.is_active,
                lollms_model_name: newUser.lollms_model_name || '',
                llm_ctx_size: newUser.llm_ctx_size,
                safe_store_vectorizer: newUser.safe_store_vectorizer || '',
            };
        }
    },
    { immediate: true }
);

watch(() => form.value.is_admin, (isAdmin) => {
    if (isAdmin) {
        form.value.is_moderator = true;
    }
});

async function handleSubmit() {
    if (!user.value || !user.value.id) return;
    isLoading.value = true;
    try {
        const payload = {
            is_admin: form.value.is_admin,
            is_moderator: form.value.is_moderator,
            is_active: form.value.is_active,
            lollms_model_name: form.value.lollms_model_name || null,
            llm_ctx_size: form.value.llm_ctx_size ? Number(form.value.llm_ctx_size) : null,
            safe_store_vectorizer: form.value.safe_store_vectorizer || null
        };
        await apiClient.put(`/api/admin/users/${user.value.id}`, payload);
        
        if (onUserUpdated.value && typeof onUserUpdated.value === 'function') {
            onUserUpdated.value();
        }
        
        uiStore.addNotification('User updated successfully.', 'success');
        uiStore.closeModal('adminUserEdit');
    } catch (error) {
    } finally {
        isLoading.value = false;
    }
}

function openResetPasswordModal() {
    uiStore.openModal('resetPassword', {
        user: user.value,
        onPasswordReset: () => {
            uiStore.closeModal('adminUserEdit');
        }
    });
}

async function generateResetLink() {
    if (!user.value?.id) return;
    isGeneratingLink.value = true;
    try {
        const response = await apiClient.post(`/api/admin/users/${user.value.id}/generate-reset-link`);
        uiStore.openModal('passwordResetLink', {
            username: user.value.username,
            link: response.data.reset_link
        });
    } catch (error) {
        uiStore.addNotification('Failed to generate reset link.', 'error');
    } finally {
        isGeneratingLink.value = false;
    }
}

onMounted(() => {
    if (availableLollmsModels.value.length === 0) {
        dataStore.fetchAdminAvailableLollmsModels();
    }
});
</script>

<template>
    <GenericModal :modal-name="'adminUserEdit'" :title="user ? `Edit User: ${user.username}` : 'Edit User'">
        <template #body>
            <form v-if="user" @submit.prevent="handleSubmit" class="p-6 space-y-6">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    <div class="relative flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                        <span class="flex-grow flex flex-col">
                            <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Administrator</span>
                            <span class="text-sm text-gray-500 dark:text-gray-400">Grants full system access.</span>
                        </span>
                        <button @click="form.is_admin = !form.is_admin" type="button" :class="[form.is_admin ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800']">
                            <span :class="[form.is_admin ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>
                    <div class="relative flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                        <span class="flex-grow flex flex-col">
                            <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Moderator</span>
                            <span class="text-sm text-gray-500 dark:text-gray-400">Can delete user content.</span>
                        </span>
                        <button @click="form.is_moderator = !form.is_moderator" type="button" :disabled="form.is_admin" :class="[form.is_moderator ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800', {'opacity-50 cursor-not-allowed': form.is_admin}]">
                            <span :class="[form.is_moderator ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>
                    <div class="relative flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                        <span class="flex-grow flex flex-col">
                            <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Account Active</span>
                            <span class="text-sm text-gray-500 dark:text-gray-400">Allows the user to log in.</span>
                        </span>
                        <button @click="form.is_active = !form.is_active" type="button" :class="[form.is_active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800']">
                            <span :class="[form.is_active ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>
                </div>

                <div class="space-y-4 pt-4 border-t dark:border-gray-600">
                    <h3 class="text-base font-semibold leading-6 text-gray-900 dark:text-white">Core Assignments</h3>
                    <div>
                        <label for="lollmsModelSelect" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Default LLM Model</label>
                        <select id="lollmsModelSelect" v-model="form.lollms_model_name" class="input-field mt-1" :disabled="isLoadingLollmsModels">
                            <option v-if="isLoadingLollmsModels" disabled value="">Loading models...</option>
                            <option v-else-if="availableLollmsModels.length === 0" disabled value="">No models available</option>
                            <option value="">(Use System Default)</option>
                            <option v-for="model in availableLollmsModels" :key="model.id" :value="model.id">{{ model.name }}</option>
                        </select>
                    </div>
                    <div>
                        <label for="contextSize" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Context Size Override</label>
                        <input type="number" id="contextSize" v-model.number="form.llm_ctx_size" class="input-field mt-1" placeholder="e.g., 4096">
                        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">Leave blank to use the system or user's default setting.</p>
                    </div>
                    <div>
                        <label for="vectorizer" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Default Vectorizer</label>
                        <input type="text" id="vectorizer" v-model="form.safe_store_vectorizer" class="input-field mt-1" placeholder="e.g., st:all-MiniLM-L6-v2">
                        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">The default vectorizer for new data stores created by this user.</p>
                    </div>
                </div>
                 <div class="space-y-4 pt-4 border-t dark:border-gray-600">
                    <h3 class="text-base font-semibold leading-6 text-gray-900 dark:text-white">Password Management</h3>
                    <div class="flex flex-col sm:flex-row gap-4">
                        <button type="button" @click="openResetPasswordModal" class="btn btn-warning flex-1">
                            Reset Password...
                        </button>
                        <button type="button" @click="generateResetLink" class="btn btn-secondary flex-1" :disabled="isGeneratingLink">
                            {{ isGeneratingLink ? 'Generating...' : 'Generate Reset Link...' }}
                        </button>
                    </div>
                </div>
            </form>
            <div v-else class="p-6 text-center text-gray-500">
                Loading user data...
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end space-x-3">
                <button type="button" class="btn btn-secondary" @click="uiStore.closeModal('adminUserEdit')">Cancel</button>
                <button type="button" class="btn btn-primary" :disabled="isLoading || !user" @click="handleSubmit">
                    {{ isLoading ? 'Saving...' : 'Save Changes' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>