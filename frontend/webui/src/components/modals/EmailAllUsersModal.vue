<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import GenericModal from '../ui/GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import { storeToRefs } from 'pinia';
import WysiwygEditor from '../ui/WysiwygEditor.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const { allUsers, isEnhancingEmail } = storeToRefs(adminStore);

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

async function handleEnhance() {
    if (!subject.value && !body.value) {
        uiStore.addNotification('Please provide a subject or body to enhance.', 'warning');
        return;
    }
    try {
        const enhanced = await adminStore.enhanceEmail(subject.value, body.value);
        if (enhanced) {
            subject.value = enhanced.subject;
            body.value = enhanced.body;
        }
    } catch (error) {
        // Error already handled by store/interceptor
    }
}

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
        await adminStore.sendEmailToUsers(subject.value, body.value, selectedUserIds.value);
        uiStore.closeModal('emailAllUsers');
    } catch (error) {
        // The admin store now uses the global handler
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
        maxWidthClass="max-w-4xl"
    >
        <template #body>
            <form @submit.prevent="handleSubmit" class="p-6 space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <!-- Left side: Form -->
                    <div class="space-y-6 md:col-span-2">
                        <div>
                            <label for="email-subject" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Subject</label>
                            <input id="email-subject" v-model="subject" type="text" class="input-field mt-1" required />
                        </div>
                        <div>
                            <label for="email-body" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Body</label>
                            <WysiwygEditor v-model="body" />
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
                            <div class="max-h-96 overflow-y-auto border border-gray-200 dark:border-gray-600 rounded-b-md">
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
            <div class="flex justify-between items-center w-full">
                <button type="button" @click="handleEnhance" class="btn btn-secondary flex items-center gap-2" :disabled="isEnhancingEmail">
                     <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" :class="{'animate-spin': isEnhancingEmail}" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.898 20.572L16.5 21.75l-.398-1.178a3.375 3.375 0 00-2.3-2.3L12.75 18l1.178-.398a3.375 3.375 0 002.3-2.3L16.5 14.25l.398 1.178a3.375 3.375 0 002.3 2.3l1.178.398-1.178.398a3.375 3.375 0 00-2.3 2.3z" />
                    </svg>
                    <span>{{ isEnhancingEmail ? 'Enhancing...' : 'Enhance with AI' }}</span>
                </button>
                <div class="flex justify-end space-x-3">
                    <button type="button" class="btn btn-secondary" @click="uiStore.closeModal('emailAllUsers')">Cancel</button>
                    <button type="button" @click="handleSubmit" class="btn btn-primary" :disabled="isLoading">
                        {{ isLoading ? 'Sending...' : 'Send Email' }}
                    </button>
                </div>
            </div>
        </template>
    </GenericModal>
</template>