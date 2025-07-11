<script setup>
import { computed, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const { allUsers, isLoadingUsers } = storeToRefs(adminStore);

const searchQuery = ref('');
const sortKey = ref('username');
const sortOrder = ref('asc');

const filteredAndSortedUsers = computed(() => {
    let users = [...allUsers.value];

    if (searchQuery.value) {
        const lowerCaseQuery = searchQuery.value.toLowerCase();
        users = users.filter(user =>
            user.username.toLowerCase().includes(lowerCaseQuery) ||
            (user.email && user.email.toLowerCase().includes(lowerCaseQuery))
        );
    }

    if (sortKey.value) {
        users.sort((a, b) => {
            let valA = a[sortKey.value];
            let valB = b[sortKey.value];

            if (sortKey.value === 'last_activity_at') {
                valA = valA ? new Date(valA).getTime() : 0;
                valB = valB ? new Date(valB).getTime() : 0;
            } else if (typeof valA === 'string') {
                valA = valA.toLowerCase();
                valB = valB ? valB.toLowerCase() : '';
            }

            if (valA < valB) return sortOrder.value === 'asc' ? -1 : 1;
            if (valA > valB) return sortOrder.value === 'asc' ? 1 : -1;
            return 0;
        });
    }

    return users;
});

function handleSort(key) {
    if (sortKey.value === key) {
        sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc';
    } else {
        sortKey.value = key;
        sortOrder.value = 'asc';
    }
}

function formatLastSeen(dateString) {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    const now = new Date();
    const diffSeconds = Math.round((now - date) / 1000);
    
    if (diffSeconds < 60) return `${diffSeconds}s ago`;
    const diffMinutes = Math.round(diffSeconds / 60);
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    const diffHours = Math.round(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.round(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    
    return date.toLocaleDateString();
}

function hasPasswordResetRequest(user) {
    return user.password_reset_token && new Date(user.reset_token_expiry) > new Date();
}

function openEditModal(user) {
    uiStore.openModal('adminUserEdit', { 
        user,
        onUserUpdated: () => adminStore.fetchAllUsers()
    });
}

function openForceSettingsModal() {
    uiStore.openModal('forceSettings', {
        onSettingsApplied: () => adminStore.fetchAllUsers()
    });
}

function openEmailModal(user) {
    uiStore.openModal('adminUserEmail', {
        user,
        onSend: async ({ subject, body }) => {
            await adminStore.sendEmailToUsers(subject, body, [user.id]);
        }
    });
}

async function toggleUserStatus(user) {
    const action = user.is_active ? 'deactivate' : 'activate';
    const confirmation = await uiStore.showConfirmation({
        title: `${action.charAt(0).toUpperCase() + action.slice(1)} User?`,
        message: `Are you sure you want to ${action} the user "${user.username}"?`,
        confirmText: `Yes, ${action}`
    });

    if (confirmation) {
        try {
            await apiClient.post(`/api/admin/users/${user.id}/${action}`);
            uiStore.addNotification(`User ${user.username} has been ${action}d.`, 'success');
            adminStore.fetchAllUsers();
        } catch (error) {
            // Error is handled by global interceptor
        }
    }
}

async function deleteUser(user) {
     const confirmation = await uiStore.showConfirmation({
        title: `Delete User?`,
        message: `This will permanently delete the user "${user.username}" and all associated data. This action cannot be undone.`,
        confirmText: `Yes, Delete User`
    });
    if (confirmation) {
        try {
            await apiClient.delete(`/api/admin/users/${user.id}`);
            uiStore.addNotification(`User ${user.username} has been deleted.`, 'success');
            adminStore.fetchAllUsers();
        } catch (error) {
            // Error handled by interceptor
        }
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-sm rounded-lg overflow-hidden">
        <div class="px-4 py-5 sm:p-6 space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h3 class="text-base font-semibold leading-6 text-gray-900 dark:text-white">All Users</h3>
                    <p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">A sortable and searchable list of all registered users.</p>
                </div>
                <button @click="openForceSettingsModal" class="btn btn-secondary">
                    Force Settings
                </button>
            </div>
            <input 
                type="text" 
                v-model="searchQuery" 
                placeholder="Search by username or email..."
                class="input-field max-w-sm"
            />
        </div>
        <div class="border-t border-gray-200 dark:border-gray-700">
            <div v-if="isLoadingUsers" class="p-6 text-center text-gray-500">
                Loading users...
            </div>
            <div v-else-if="filteredAndSortedUsers.length === 0" class="p-6 text-center text-gray-500">
                No users found.
            </div>
            <div v-else class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                    <thead class="bg-gray-50 dark:bg-gray-700/50">
                        <tr>
                            <th scope="col" class="table-header">
                                <button @click="handleSort('username')" class="flex items-center gap-1">
                                    User
                                    <span v-if="sortKey === 'username'">{{ sortOrder === 'asc' ? '▲' : '▼' }}</span>
                                </button>
                            </th>
                             <th scope="col" class="table-header">
                                Model/Binding
                            </th>
                             <th scope="col" class="table-header">
                                Vectorizer
                            </th>
                             <th scope="col" class="table-header">
                                Context Size
                            </th>
                             <th scope="col" class="table-header">
                                <button @click="handleSort('last_activity_at')" class="flex items-center gap-1">
                                    Last Seen
                                    <span v-if="sortKey === 'last_activity_at'">{{ sortOrder === 'asc' ? '▲' : '▼' }}</span>
                                </button>
                            </th>
                            <th scope="col" class="table-header">
                                Status
                            </th>
                            <th scope="col" class="table-header">
                                Role
                            </th>
                            <th scope="col" class="relative px-6 py-3">
                                <span class="sr-only">Actions</span>
                            </th>
                        </tr>
                    </thead>
                    <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                        <tr v-for="user in filteredAndSortedUsers" :key="user.id" class="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                            <td class="table-cell">
                                <div class="flex items-center">
                                    <div class="ml-4">
                                        <div class="text-sm font-medium text-gray-900 dark:text-white">{{ user.username }}</div>
                                        <div class="text-sm text-gray-500 dark:text-gray-400">{{ user.email || 'No email' }}</div>
                                    </div>
                                </div>
                            </td>
                             <td class="table-cell text-sm text-gray-500 dark:text-gray-400">
                                {{ user.lollms_model_name || 'Not Set' }}
                            </td>
                            <td class="table-cell text-sm text-gray-500 dark:text-gray-400">
                                {{ user.safe_store_vectorizer || 'Not Set' }}
                            </td>
                            <td class="table-cell text-sm text-gray-500 dark:text-gray-400">
                                {{ user.llm_ctx_size || 'Default' }}
                            </td>
                            <td class="table-cell text-sm text-gray-500 dark:text-gray-400">
                                {{ formatLastSeen(user.last_activity_at) }}
                            </td>
                            <td class="table-cell">
                                <div class="flex flex-col gap-1 items-start">
                                    <span :class="user.is_active ? 'status-badge-green' : 'status-badge-red'" class="status-badge">
                                        {{ user.is_active ? 'Active' : 'Inactive' }}
                                    </span>
                                     <span v-if="hasPasswordResetRequest(user)" class="status-badge status-badge-yellow" title="This user has requested a password reset.">
                                        Reset Pending
                                    </span>
                                </div>
                            </td>
                            <td class="table-cell text-sm text-gray-500 dark:text-gray-400">
                                {{ user.is_admin ? 'Admin' : 'User' }}
                            </td>
                            <td class="table-cell text-right text-sm font-medium">
                                <div class="flex items-center justify-end space-x-3">
                                    <button @click="openEditModal(user)" title="Edit User" class="action-icon">
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>
                                    </button>
                                     <button @click="openEmailModal(user)" title="Email User" class="action-icon">
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75" /></svg>
                                    </button>
                                    <button @click="toggleUserStatus(user)" :title="user.is_active ? 'Deactivate User' : 'Activate User'" :class="user.is_active ? 'action-icon-toggle-active' : 'action-icon-toggle-inactive'">
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M5.636 5.636a9 9 0 1 0 12.728 0M12 3v9" /></svg>
                                    </button>
                                    <button @click="deleteUser(user)" title="Delete User" class="action-icon-delete">
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" /></svg>
                                    </button>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</template>
<style scoped>
.table-header { @apply px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider; }
.table-cell { @apply px-6 py-4 whitespace-nowrap; }
.status-badge { @apply px-2 inline-flex text-xs leading-5 font-semibold rounded-full; }
.status-badge-green { @apply bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300; }
.status-badge-red { @apply bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300; }
.status-badge-yellow { @apply bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300; }
.action-icon { @apply text-gray-400 hover:text-blue-600 dark:hover:text-blue-400; }
.action-icon-toggle-active { @apply text-green-500 hover:text-yellow-600 dark:text-green-400 dark:hover:text-yellow-400; }
.action-icon-toggle-inactive { @apply text-red-500 hover:text-green-600 dark:text-red-400 dark:hover:text-green-400; }
.action-icon-delete { @apply text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300; }
</style>