<script>
import { mapState } from 'pinia';
import { useAuthStore } from '../../stores/auth';

export default {
  name: 'UserTable',
  props: {
    users: Array,
    isLoading: Boolean,
  },
  emits: ['delete-user', 'reset-password'],
  computed: {
      ...mapState(useAuthStore, {
          currentUserId: state => state.user.id,
      })
  }
};
</script>

<template>
  <div class="overflow-x-auto">
    <table class="min-w-full divide-y dark:divide-gray-600">
      <thead class="bg-gray-50 dark:bg-gray-700">
        <tr>
          <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">ID</th>
          <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">Username</th>
          <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">Admin</th>
          <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">LLM Model</th>
          <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">Vectorizer</th>
          <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider">Actions</th>
        </tr>
      </thead>
      <tbody class="bg-white dark:bg-gray-800 divide-y dark:divide-gray-700">
        <tr v-if="isLoading">
          <td colspan="6" class="px-4 py-4 text-center text-sm italic">Loading users...</td>
        </tr>
        <tr v-else-if="users.length === 0">
          <td colspan="6" class="px-4 py-4 text-center text-sm italic">No users found.</td>
        </tr>
        <tr v-for="user in users" :key="user.id" class="hover:bg-gray-50 dark:hover:bg-gray-700/50">
          <td class="px-4 py-2 text-xs font-mono">{{ user.id }}</td>
          <td class="px-4 py-2 text-sm font-medium">{{ user.username }}</td>
          <td class="px-4 py-2 text-sm">
            <span v-if="user.is_admin" class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300">Yes</span>
            <span v-else class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800 dark:bg-gray-600 dark:text-gray-200">No</span>
          </td>
          <td class="px-4 py-2 text-xs truncate" :title="user.lollms_model_name">{{ user.lollms_model_name || '-' }}</td>
          <td class="px-4 py-2 text-xs truncate" :title="user.safe_store_vectorizer">{{ user.safe_store_vectorizer || '-' }}</td>
          <td class="px-4 py-2 text-sm space-x-2 whitespace-nowrap">
            <button @click="$emit('reset-password', user.id)" :disabled="user.id === currentUserId" class="btn btn-secondary !py-1 !px-2 text-xs" title="Reset Password">Reset Pass</button>
            <button @click="$emit('delete-user', user.id)" :disabled="user.id === currentUserId" class="btn btn-danger !py-1 !px-2 text-xs" title="Delete User">Delete</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>