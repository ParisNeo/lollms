<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import GenericModal from '../ui/GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const { adminAvailableLollmsModels, isLoadingLollmsModels, allUsers, isLoadingUsers } = storeToRefs(adminStore);
const props = computed(() => uiStore.modalData('forceSettings'));
const onSettingsApplied = computed(() => props.value?.onSettingsApplied);

const form = ref({
    lollms_model_name: '',
    safe_store_vectorizer: '',
    llm_ctx_size: null,
});
const selectedUserIds = ref([]);
const userSearchQuery = ref('');
const isLoading = ref(false);

const filteredUsers = computed(() => {
    if (!userSearchQuery.value) {
        return allUsers.value;
    }
    const lowerQuery = userSearchQuery.value.toLowerCase();
    return allUsers.value.filter(u => u.username.toLowerCase().includes(lowerQuery));
});

const areAllUsersSelected = computed({
    get() {
        return filteredUsers.value.length > 0 && selectedUserIds.value.length === filteredUsers.value.length;
    },
    set(value) {
        if (value) {
            selectedUserIds.value = filteredUsers.value.map(u => u.id);
        } else {
            selectedUserIds.value = [];
        }
    }
});

watch(userSearchQuery, () => {
    selectedUserIds.value = [];
});

async function handleSubmit() {
    isLoading.value = true;
    try {
        const payload = { user_ids: selectedUserIds.value };
        if (form.value.lollms_model_name) payload.lollms_model_name = form.value.lollms_model_name;
        if (form.value.safe_store_vectorizer) payload.safe_store_vectorizer = form.value.safe_store_vectorizer;
        if (form.value.llm_ctx_size) payload.llm_ctx_size = Number(form.value.llm_ctx_size);

        if (Object.keys(payload).length <= 1) {
            uiStore.addNotification('Please specify at least one setting to apply.', 'warning');
            return;
        }

        await adminStore.batchUpdateUsers(payload);
        
        if (onSettingsApplied.value && typeof onSettingsApplied.value === 'function') {
            onSettingsApplied.value();
        }
        
        uiStore.addNotification('Settings applied to selected users.', 'success');
        uiStore.closeModal('forceSettings');
    } finally {
        isLoading.value = false;
    }
}

onMounted(() => {
    if (adminAvailableLollmsModels.value.length === 0) {
        adminStore.fetchAdminAvailableLollmsModels();
    }
    if (allUsers.value.length === 0) {
        adminStore.fetchAllUsers();
    } else {
        // If users are already in store, initialize selection
        selectedUserIds.value = allUsers.value.map(u => u.id);
    }
});

watch(allUsers, (newUsers) => {
    // When user list is fetched, select all by default
    selectedUserIds.value = newUsers.map(u => u.id);
});
</script>

<template>
    <GenericModal modal-name="forceSettings" title="Force Settings on Users" max-width-class="max-w-2xl">
        <template #body>
            <form @submit.prevent="handleSubmit" class="space-y-6">
                <p class="text-sm text-gray-500 dark:text-gray-400">
                    Apply these settings to the selected users below. Fields left blank will not be changed.
                </p>
                <div class="space-y-4">
                    <div>
                        <label for="force-model" class="block text-sm font-medium text-gray-700 dark:text-gray-300">LLM Model/Binding</label>
                        <select id="force-model" v-model="form.lollms_model_name" class="input-field mt-1" :disabled="isLoadingLollmsModels">
                            <option v-if="isLoadingLollmsModels" disabled value="">Loading models...</option>
                            <option v-else value="">-- Do Not Change --</option>
                            <option v-for="model in adminAvailableLollmsModels" :key="model.id" :value="model.id">{{ model.name }}</option>
                        </select>
                    </div>
                    <div>
                        <label for="force-vectorizer" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Vectorizer</label>
                        <input type="text" id="force-vectorizer" v-model="form.safe_store_vectorizer" class="input-field mt-1" placeholder="e.g., st:all-MiniLM-L6-v2">
                    </div>
                    <div>
                        <label for="force-ctx" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Context Size</label>
                        <input type="number" id="force-ctx" v-model.number="form.llm_ctx_size" class="input-field mt-1" placeholder="e.g., 4096">
                    </div>
                </div>

                <div class="space-y-3 pt-4 border-t dark:border-gray-600">
                    <h4 class="text-base font-medium text-gray-800 dark:text-gray-200">Target Users ({{ selectedUserIds.length }} selected)</h4>
                    <input type="text" v-model="userSearchQuery" placeholder="Search users..." class="input-field w-full">
                    <div class="relative flex items-start">
                        <div class="flex h-6 items-center">
                            <input id="select-all-users" type="checkbox" v-model="areAllUsersSelected" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600">
                        </div>
                        <div class="ml-3 text-sm leading-6">
                            <label for="select-all-users" class="font-medium text-gray-900 dark:text-gray-100">Select All Visible</label>
                        </div>
                    </div>
                    <div class="max-h-60 overflow-y-auto border dark:border-gray-600 rounded-md p-2 space-y-1">
                        <div v-if="isLoadingUsers" class="text-center text-sm text-gray-500">Loading users...</div>
                        <div v-else-if="filteredUsers.length === 0" class="text-center text-sm text-gray-500">No users match search.</div>
                        <div v-for="user in filteredUsers" :key="user.id" class="relative flex items-start">
                             <div class="flex h-6 items-center">
                                <input :id="`user-${user.id}`" :value="user.id" v-model="selectedUserIds" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600">
                            </div>
                            <div class="ml-3 text-sm leading-6">
                                <label :for="`user-${user.id}`" class="font-medium text-gray-900 dark:text-gray-100">{{ user.username }}</label>
                            </div>
                        </div>
                    </div>
                </div>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-end space-x-3">
                <button type="button" class="btn btn-secondary" @click="uiStore.closeModal('forceSettings')">Cancel</button>
                <button type="submit" class="btn btn-primary" :disabled="isLoading || selectedUserIds.length === 0" @click="handleSubmit">
                    {{ isLoading ? 'Applying...' : `Apply to ${selectedUserIds.length} Users` }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>