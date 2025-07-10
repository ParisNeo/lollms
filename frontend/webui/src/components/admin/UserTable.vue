<script>
import { mapState } from 'pinia';
import { useAuthStore } from '../../stores/auth';

function formatTimeAgo(date) {
  if (!date) return 'Never';
  
  const now = new Date();
  const past = new Date(date);
  const seconds = Math.floor((now - past) / 1000);

  if (seconds < 2) return 'Just now';
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return past.toLocaleDateString();
}

export default {
  name: 'UserTable',
  props: {
    users: { type: Array, required: true },
    isLoading: { type: Boolean, default: false },
    activeSessions: { type: Array, default: () => [] },
    sortKey: { type: String, required: true },
    sortDir: { type: String, required: true }
  },
  emits: ['delete-user', 'reset-password', 'get-reset-link', 'activate-user', 'deactivate-user', 'edit-user', 'sort-by'],
  computed: {
    ...mapState(useAuthStore, {
      currentUser: state => state.user,
    })
  },
  methods: {
    formatTimeAgo,
    canPerformAction(user) {
        if (!this.currentUser) return false;
        return user.id !== this.currentUser.id;
    },
    getSortIcon(key) {
      if (this.sortKey !== key) return 'opacity-20';
      return this.sortDir === 'asc' ? 'transform rotate-180' : '';
    }
  }
};
</script>

<template>
  <div class="overflow-x-auto">
    <table class="min-w-full divide-y dark:divide-gray-600">
      <thead class="bg-gray-50 dark:bg-gray-700">
        <tr>
          <th scope="col" class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
             <button @click="$emit('sort-by', 'event')" class="flex items-center space-x-1 group">
                <span>Status</span>
                <svg class="w-4 h-4 text-gray-400 group-hover:opacity-100 transition-opacity" :class="getSortIcon('event')" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
             </button>
          </th>
          <th scope="col" class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
            <button @click="$emit('sort-by', 'username')" class="flex items-center space-x-1 group">
                <span>Username</span>
                <svg class="w-4 h-4 text-gray-400 group-hover:opacity-100 transition-opacity" :class="getSortIcon('username')" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
            </button>
          </th>
          <th scope="col" class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">
             <button @click="$emit('sort-by', 'last_activity_at')" class="flex items-center space-x-1 group">
                <span>Last Seen</span>
                <svg class="w-4 h-4 text-gray-400 group-hover:opacity-100 transition-opacity" :class="getSortIcon('last_activity_at')" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
             </button>
          </th>
          <th scope="col" class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">Admin</th>
          <th scope="col" class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">LLM Model</th>
          <th scope="col" class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">Actions</th>
        </tr>
      </thead>
      <tbody class="bg-white dark:bg-gray-800 divide-y dark:divide-gray-700">
        <tr v-if="isLoading">
          <td colspan="6" class="px-4 py-4 text-center text-sm italic text-gray-500">Loading users...</td>
        </tr>
        <tr v-else-if="!users || users.length === 0">
          <td colspan="6" class="px-4 py-4 text-center text-sm italic text-gray-500">No users found.</td>
        </tr>
        <tr v-for="user in users" :key="user.id" class="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors duration-150">
          <td class="px-4 py-2 text-sm">
            <span v-if="user.password_reset_token" class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-orange-100 text-orange-800 dark:bg-orange-900/50 dark:text-orange-300">Reset Requested</span>
            <span v-else-if="!user.is_active" class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300">Needs Approval</span>
            <span v-else class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300">Active</span>
          </td>
          <td class="px-4 py-2 text-sm font-medium text-gray-900 dark:text-gray-100">{{ user.username }}</td>
          <td class="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">
            <div class="flex items-center space-x-2">
              <span v-if="activeSessions.includes(user.username)" class="h-2 w-2 rounded-full bg-green-500 animate-pulse" title="Online now"></span>
              <span :title="user.last_activity_at ? new Date(user.last_activity_at).toLocaleString() : 'Never'">{{ formatTimeAgo(user.last_activity_at) }}</span>
            </div>
          </td>
          <td class="px-4 py-2 text-sm">
            <span v-if="user.is_admin" class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300">Yes</span>
            <span v-else class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800 dark:bg-gray-600 dark:text-gray-200">No</span>
          </td>
          <td class="px-4 py-2 text-xs truncate text-gray-500 dark:text-gray-400" :title="user.lollms_model_name">{{ user.lollms_model_name || '-' }}</td>
          <td class="px-4 py-2 text-sm space-x-2 whitespace-nowrap">
            <button @click="$emit('edit-user', user)" class="btn btn-primary !py-1 !px-2 text-xs" title="Edit User">Edit</button>
            <button v-if="!user.is_active" @click="$emit('activate-user', user.id)" class="btn btn-success !py-1 !px-2 text-xs" title="Activate User">Activate</button>
            <button v-if="user.is_active && canPerformAction(user)" @click="$emit('deactivate-user', user.id)" class="btn btn-warning !py-1 !px-2 text-xs" title="Deactivate User">Deactivate</button>
            <button v-if="canPerformAction(user)" @click="$emit('reset-password', user.id)" class="btn btn-secondary !py-1 !px-2 text-xs" title="Reset Password">Reset Pass</button>
            <button v-if="canPerformAction(user)" @click="$emit('get-reset-link', user.id, user.username)" class="btn btn-secondary !py-1 !px-2 text-xs" title="Get Password Reset Link">Get Link</button>
            <button v-if="canPerformAction(user)" @click="$emit('delete-user', user.id)" class="btn btn-danger !py-1 !px-2 text-xs" title="Delete User">Delete</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>