# [UPDATE] frontend/webui/src/components/admin/UserTable.vue
<script setup>
import { computed, ref, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import { useSocialStore } from '../../stores/social';
import { useRouter } from 'vue-router';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import UserStatsModal from './UserStatsModal.vue';

// Icons
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconXCircle from '../../assets/icons/IconXCircle.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const socialStore = useSocialStore();
const router = useRouter();

const { allUsers, isLoadingUsers } = storeToRefs(adminStore);

const searchQuery = ref('');
const filterOnline = ref(null);
const filterHasKeys = ref(null);
const sortKey = ref('username');
const sortOrder = ref('asc');
const selectedUserForStats = ref(null);
const selectedUserIds = ref([]);

const filters = computed(() => ({
    filter_online: filterOnline.value,
    filter_has_keys: filterHasKeys.value,
    sort_by: sortKey.value,
    sort_order: sortOrder.value
}));

const filteredUsers = computed(() => {
    if (!searchQuery.value) return allUsers.value;
    const lowerCaseQuery = searchQuery.value.toLowerCase();
    return allUsers.value.filter(user =>
        user.username.toLowerCase().includes(lowerCaseQuery) ||
        (user.email && user.email.toLowerCase().includes(lowerCaseQuery))
    );
});

const areAllSelected = computed({
    get: () => {
        const filteredUserIds = filteredUsers.value.map(u => u.id);
        if (filteredUserIds.length === 0) return false;
        return selectedUserIds.value.length === filteredUserIds.length && filteredUserIds.every(id => selectedUserIds.value.includes(id));
    },
    set: (value) => {
        const filteredUserIds = filteredUsers.value.map(u => u.id);
        if (value) {
            selectedUserIds.value = [...new Set([...selectedUserIds.value, ...filteredUserIds])];
        } else {
            selectedUserIds.value = selectedUserIds.value.filter(id => !filteredUserIds.includes(id));
        }
    }
});


function openEmailModal() {
    const selectedUsers = allUsers.value.filter(u => selectedUserIds.value.includes(u.id));
    if (selectedUsers.length === 0) {
        uiStore.addNotification('Please select at least one user.', 'warning');
        return;
    }
    uiStore.openModal('emailAllUsers', { users: selectedUsers });
}

function openCopyEmailsModal() {
    const selectedUsers = allUsers.value.filter(u => selectedUserIds.value.includes(u.id));
    if (selectedUsers.length === 0) {
        uiStore.addNotification('Please select at least one user.', 'warning');
        return;
    }
    uiStore.openModal('emailList', { users: selectedUsers });
}

function handleSort(key) {
    if (sortKey.value === key) {
        sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc';
    } else {
        sortKey.value = key;
        sortOrder.value = 'asc';
    }
    adminStore.fetchAllUsers(filters.value);
}

function applyFilters() {
    adminStore.fetchAllUsers(filters.value);
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
    
    return date.toLocaleString();
}

function openEditModal(user) {
    uiStore.openModal('adminUserEdit', { 
        user,
        onUserUpdated: () => adminStore.fetchAllUsers(filters.value)
    });
}

function openStatsModal(user) {
    selectedUserForStats.value = user;
    uiStore.openModal('userStats');
}

async function handleMessageUser(user) {
    await router.push('/');
    socialStore.openConversation({
        id: user.id,
        username: user.username,
        icon: user.icon
    });
}

onMounted(() => {
    adminStore.fetchAllUsers(filters.value);
});
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-sm rounded-lg overflow-hidden">
        <div class="px-4 py-5 sm:p-6 space-y-4">
            <div class="flex flex-wrap items-center justify-between gap-4">
                <h3 class="text-base font-semibold leading-6 text-gray-900 dark:text-white">All Users</h3>
                <div class="flex items-center gap-2">
                    <button @click="openCopyEmailsModal" class="btn btn-secondary btn-sm" :disabled="selectedUserIds.length === 0">Copy Emails</button>
                    <button @click="openEmailModal" class="btn btn-secondary btn-sm" :disabled="selectedUserIds.length === 0">Email Selected</button>
                </div>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <input 
                    type="text" 
                    v-model="searchQuery" 
                    placeholder="Search username/email..."
                    class="input-field md:col-span-2"
                />
                <select v-model="filterOnline" @change="applyFilters" class="input-field">
                    <option :value="null">All Activity</option>
                    <option :value="true">Online</option>
                    <option :value="false">Offline</option>
                </select>
                <select v-model="filterHasKeys" @change="applyFilters" class="input-field">
                    <option :value="null">All API Keys</option>
                    <option :value="true">Has Keys</option>
                    <option :value="false">No Keys</option>
                </select>
            </div>
        </div>
        <div class="border-t border-gray-200 dark:border-gray-700">
            <div v-if="isLoadingUsers" class="p-6 text-center text-gray-500">
                Loading users...
            </div>
            <div v-else-if="filteredUsers.length === 0" class="p-6 text-center text-gray-500">
                No users found.
            </div>
            <div v-else class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                    <thead class="bg-gray-50 dark:bg-gray-700/50">
                        <tr>
                            <th scope="col" class="px-6 py-3">
                                <input type="checkbox" v-model="areAllSelected" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                            </th>
                            <th scope="col" class="table-header">
                                <button @click="handleSort('username')" class="flex items-center gap-1">User <span v-if="sortKey === 'username'">{{ sortOrder === 'asc' ? '▲' : '▼' }}</span></button>
                            </th>
                            <th scope="col" class="table-header">Status</th>
                            <th scope="col" class="table-header">
                                <button @click="handleSort('last_activity_at')" class="flex items-center gap-1">Last Seen <span v-if="sortKey === 'last_activity_at'">{{ sortOrder === 'asc' ? '▲' : '▼' }}</span></button>
                            </th>
                            <th scope="col" class="table-header">
                                <button @click="handleSort('api_key_count')" class="flex items-center gap-1">API Keys <span v-if="sortKey === 'api_key_count'">{{ sortOrder === 'asc' ? '▲' : '▼' }}</span></button>
                            </th>
                            <th scope="col" class="table-header">
                                <button @click="handleSort('task_count')" class="flex items-center gap-1">Tasks <span v-if="sortKey === 'task_count'">{{ sortOrder === 'asc' ? '▲' : '▼' }}</span></button>
                            </th>
                             <th scope="col" class="table-header">
                                <button @click="handleSort('created_at')" class="flex items-center gap-1">Joined <span v-if="sortKey === 'created_at'">{{ sortOrder === 'asc' ? '▲' : '▼' }}</span></button>
                            </th>
                            <th scope="col" class="relative px-6 py-3"><span class="sr-only">Actions</span></th>
                        </tr>
                    </thead>
                    <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                        <tr v-for="user in filteredUsers" :key="user.id" class="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                            <td class="px-6 py-4">
                                <input type="checkbox" :value="user.id" v-model="selectedUserIds" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                            </td>
                            <td class="table-cell">
                                <div class="flex items-center">
                                    <UserAvatar :icon="user.icon" :username="user.username" size-class="h-8 w-8" />
                                    <div class="ml-4">
                                        <div class="text-sm font-medium text-gray-900 dark:text-white">{{ user.username }}</div>
                                        <div class="text-sm text-gray-500 dark:text-gray-400">{{ user.email || 'No email' }}</div>
                                    </div>
                                </div>
                            </td>
                            <td class="table-cell">
                                <div class="flex items-center gap-2">
                                    <span class="w-3 h-3 rounded-full" :class="user.is_online ? 'bg-green-500' : 'bg-gray-400'" :title="user.is_online ? 'Online' : 'Offline'"></span>
                                    <span :class="user.is_active ? 'status-badge-green' : 'status-badge-red'" class="status-badge">{{ user.is_active ? 'Active' : 'Inactive' }}</span>
                                </div>
                            </td>
                            <td class="table-cell text-sm text-gray-500 dark:text-gray-400">{{ formatLastSeen(user.last_activity_at) }}</td>
                            <td class="table-cell text-sm text-center text-gray-500 dark:text-gray-400">{{ user.api_key_count }}</td>
                            <td class="table-cell text-sm text-center text-gray-500 dark:text-gray-400">{{ user.task_count }}</td>
                            <td class="table-cell text-sm text-gray-500 dark:text-gray-400">{{ new Date(user.created_at).toLocaleDateString() }}</td>
                            <td class="table-cell text-right text-sm font-medium">
                                <div class="flex items-center justify-end space-x-2">
                                    <button @click="openStatsModal(user)" title="View Stats" class="action-icon"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg></button>
                                    <button @click="handleMessageUser(user)" title="Send DM" class="action-icon"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg></button>
                                    <button @click="openEditModal(user)" title="Edit User" class="action-icon"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10"></path></svg></button>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
        <UserStatsModal v-if="selectedUserForStats" :userId="selectedUserForStats.id" :username="selectedUserForStats.username" />
    </div>
</template>