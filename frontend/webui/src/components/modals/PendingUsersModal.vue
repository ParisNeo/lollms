<script setup>
import { computed, ref } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import GenericModal from './GenericModal.vue';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const allUsers = computed(() => adminStore.allUsers);
const pendingUsers = computed(() => allUsers.value.filter(u => !u.is_active));

const isActivating = ref(false);

async function activate(user) {
    try {
        await adminStore.activateUser(user.id);
    } catch (e) {
        uiStore.addNotification('Failed to activate user', 'error');
    }
}

async function activateAll() {
    isActivating.value = true;
    try {
        for (const user of pendingUsers.value) {
            await adminStore.activateUser(user.id);
        }
        uiStore.closeModal('pendingUsers');
    } finally {
        isActivating.value = false;
    }
}
</script>

<template>
    <GenericModal modal-name="pendingUsers" title="Pending User Approvals">
        <template #body>
            <div v-if="pendingUsers.length === 0" class="text-center p-6 text-gray-500">
                No pending users found.
            </div>
            <div v-else class="space-y-4">
                <div class="flex justify-between items-center bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg">
                    <span class="text-sm font-medium text-blue-800 dark:text-blue-200">{{ pendingUsers.length }} users waiting.</span>
                    <button @click="activateAll" class="btn btn-primary btn-sm" :disabled="isActivating">
                        {{ isActivating ? 'Activating...' : 'Activate All' }}
                    </button>
                </div>
                <ul class="divide-y divide-gray-200 dark:divide-gray-700 max-h-96 overflow-y-auto">
                    <li v-for="user in pendingUsers" :key="user.id" class="py-3 flex items-center justify-between">
                        <div class="flex items-center">
                            <UserAvatar :icon="user.icon" :username="user.username" size-class="h-10 w-10" />
                            <div class="ml-3">
                                <p class="text-sm font-medium text-gray-900 dark:text-white">{{ user.username }}</p>
                                <p class="text-xs text-gray-500">{{ user.email || 'No email' }}</p>
                                <p class="text-xs text-gray-400">Registered: {{ new Date(user.created_at).toLocaleDateString() }}</p>
                            </div>
                        </div>
                        <button @click="activate(user)" class="btn-icon text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20" title="Approve">
                            <IconCheckCircle class="w-6 h-6" />
                        </button>
                    </li>
                </ul>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('pendingUsers')" class="btn btn-secondary">Close</button>
        </template>
    </GenericModal>
</template>
