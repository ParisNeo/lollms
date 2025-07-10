<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import GenericModal from '../ui/GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import { storeToRefs } from 'pinia';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const { allUsers } = storeToRefs(adminStore);

const subject = ref('');
const body = ref('');
const isLoading = ref(false);
const selectedUserIds = ref([]);
const selectAll = ref(true);

const eligibleUsers = computed(() => {
    return allUsers.value.filter(u => u.is_active && u.receive_notification_emails && u.email);
});

onMounted(() => {
    if (allUsers.value.length === 0) {
        adminStore.fetchAllUsers();
    }
    // Pre-select all eligible users by default
    selectedUserIds.value = eligibleUsers.value.map(u => u.id);
});

watch(selectAll, (newValue) => {
    if (newValue) {
        selectedUserIds.value = eligibleUsers.value.map(u => u.id);
    } else {
        selectedUserIds.value = [];
    }
});

async function handleSubmit() {
    if (!subject.value || !body.value) {
        uiStore.addNotification('Subject and body are required.', 'error');
        return;
    }
    if (selectedUserIds.value.length === 0) {
        uiStore.addNotification('Please select at least one user to email.', 'error');
        return;
    }

    isLoading.value = true;
    try {
        await adminStore.sendEmailToAllUsers(subject.value, body.value);
        uiStore.closeModal('emailAllUsers');
    } catch (error) {
        // The admin store now uses the global handler, but you could add specific modal feedback here if needed.
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modal-name="emailAllUsers"
        title="Email Users"
        @close="uiStore.closeModal('emailAllUsers')"
        maxWidthClass="max-w-3xl"
    >
        <template #body>
            <form @submit.prevent="handleSubmit" class="p-6 space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <!-- Left side: Form -->
                    <div class="space-y-6">
                        <div>
                            <label for="email-subject" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Subject</label>
                            <input id="email-subject" v-model="subject" type="text" class="input-field mt-1" required />
                        </div>
                        <div>
                            <label for="email-body" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Body</label>
                            <textarea id="email-body" v-model="body" rows="12" class="input-field mt-1" required placeholder="You can use HTML tags for formatting."></textarea>
                        </div>
                    </div>

                    <!-- Right side: User List -->
                    <div class="space-y-4">
                        <h4 class="text-sm font-medium text-gray-700 dark:text-gray-300">Recipients ({{ selectedUserIds.length }} / {{ eligibleUsers.length }})</h4>
                        <div class="relative">
                            <div class="flex items-center p-2 border-b border-gray-200 dark:border-gray-600">
                                <input id="select-all-users" type="checkbox" v-model="selectAll" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600">
                                <label for="select-all-users" class="ml-3 block text-sm font-medium text-gray-700 dark:text-gray-200">Select All</label>
                            </div>
                            <div class="max-h-80 overflow-y-auto border border-gray-200 dark:border-gray-600 rounded-b-md">
                                <div v-if="eligibleUsers.length > 0" class="divide-y divide-gray-200 dark:divide-gray-600">
                                    <div v-for="user in eligibleUsers" :key="user.id" class="p-2 flex items-center">
                                        <input :id="`user-${user.id}`" type="checkbox" :value="user.id" v-model="selectedUserIds" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600">
                                        <label :for="`user-${user.id}`" class="ml-3 text-sm text-gray-600 dark:text-gray-300">
                                            <span class="font-medium">{{ user.username }}</span> ({{ user.email }})
                                        </label>
                                    </div>
                                </div>
                                <div v-else class="p-4 text-center text-sm text-gray-500">
                                    No eligible users found.
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-end space-x-3">
                <button type="button" class="btn btn-secondary" @click="uiStore.closeModal('emailAllUsers')">Cancel</button>
                <button type="button" @click="handleSubmit" class="btn btn-primary" :disabled="isLoading">
                    {{ isLoading ? 'Sending...' : 'Send Email' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>