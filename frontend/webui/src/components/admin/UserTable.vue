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
            <div>
                <h3 class="text-base font-semibold leading-6 text-gray-900 dark:text-white">All Users</h3>
                <p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">A sortable and searchable list of all registered users.</p>
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
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                <button @click="handleSort('username')" class="flex items-center gap-1">
                                    User
                                    <span v-if="sortKey === 'username'">{{ sortOrder === 'asc' ? '▲' : '▼' }}</span>
                                </button>
                            </th>
                             <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                <button @click="handleSort('last_activity_at')" class="flex items-center gap-1">
                                    Last Seen
                                    <span v-if="sortKey === 'last_activity_at'">{{ sortOrder === 'asc' ? '▲' : '▼' }}</span>
                                </button>
                            </th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                <button @click="handleSort('is_active')" class="flex items-center gap-1">
                                    Status
                                    <span v-if="sortKey === 'is_active'">{{ sortOrder === 'asc' ? '▲' : '▼' }}</span>
                                </button>
                            </th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                                <button @click="handleSort('is_admin')" class="flex items-center gap-1">
                                    Role
                                    <span v-if="sortKey === 'is_admin'">{{ sortOrder === 'asc' ? '▲' : '▼' }}</span>
                                </button>
                            </th>
                            <th scope="col" class="relative px-6 py-3">
                                <span class="sr-only">Actions</span>
                            </th>
                        </tr>
                    </thead>
                    <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                        <tr v-for="user in filteredAndSortedUsers" :key="user.id">
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="flex items-center">
                                    <div class="ml-4">
                                        <div class="text-sm font-medium text-gray-900 dark:text-white">{{ user.username }}</div>
                                        <div class="text-sm text-gray-500 dark:text-gray-400">{{ user.email || 'No email' }}</div>
                                    </div>
                                </div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                {{ formatLastSeen(user.last_activity_at) }}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="flex flex-col gap-1 items-start">
                                    <span :class="user.is_active ? 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300' : 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300'" class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full">
                                        {{ user.is_active ? 'Active' : 'Inactive' }}
                                    </span>
                                     <span v-if="hasPasswordResetRequest(user)" class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300" title="This user has requested a password reset.">
                                        Reset Pending
                                    </span>
                                </div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                {{ user.is_admin ? 'Admin' : 'User' }}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                                <button @click="openEditModal(user)" class="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300">Edit</button>
                                <button @click="toggleUserStatus(user)" class="text-yellow-600 hover:text-yellow-900 dark:text-yellow-400 dark:hover:text-yellow-300">
                                    {{ user.is_active ? 'Deactivate' : 'Activate' }}
                                </button>
                                <button @click="deleteUser(user)" class="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300">Delete</button>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</template>