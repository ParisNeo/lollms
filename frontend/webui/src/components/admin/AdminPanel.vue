<script>
import apiClient from '../../services/api';
import { useUiStore } from '../../stores/ui';
import UserTable from './UserTable.vue';

export default {
  name: 'AdminPanel',
  components: {
    UserTable
  },
  data() {
    return {
      users: [],
      isLoading: false,
      newUser: {
        username: '',
        password: '',
        lollms_model_name: '',
        safe_store_vectorizer: '',
        is_admin: false,
      }
    };
  },
  created() {
    this.fetchUsers();
  },
  methods: {
    async fetchUsers() {
      this.isLoading = true;
      try {
        const response = await apiClient.get('/api/admin/users');
        this.users = response.data;
      } catch (error) {
        useUiStore().addNotification('Failed to load users.', 'error');
      } finally {
        this.isLoading = false;
      }
    },
    async addUser() {
      const uiStore = useUiStore();
      if (!this.newUser.username || !this.newUser.password) {
        uiStore.addNotification('Username and password are required.', 'warning');
        return;
      }
      try {
        await apiClient.post('/api/admin/users', this.newUser);
        uiStore.addNotification(`User '${this.newUser.username}' created successfully.`, 'success');
        this.resetNewUserForm();
        await this.fetchUsers();
      } catch (error) {
        // API client handles generic error notifications
      }
    },
    async deleteUser(userId) {
        const uiStore = useUiStore();
        if (confirm('Are you sure you want to delete this user? This cannot be undone.')) {
            try {
                await apiClient.delete(`/api/admin/users/${userId}`);
                uiStore.addNotification('User deleted successfully.', 'success');
                await this.fetchUsers();
            } catch(error) { /* Handled by interceptor */ }
        }
    },
    async resetPassword(userId) {
        const uiStore = useUiStore();
        const newPassword = prompt('Enter a new password for the user (min 8 characters):');
        if (!newPassword || newPassword.length < 8) {
            uiStore.addNotification('Password reset cancelled or password too short.', 'warning');
            return;
        }
        try {
            await apiClient.post(`/api/admin/users/${userId}/reset-password`, { new_password: newPassword });
            uiStore.addNotification("User's password has been reset.", 'success');
        } catch (error) { /* Handled by interceptor */ }
    },
    resetNewUserForm() {
        this.newUser = { username: '', password: '', lollms_model_name: '', safe_store_vectorizer: '', is_admin: false };
    }
  }
};
</script>

<template>
  <div>
    <h4 class="text-lg font-semibold mb-4">Administration</h4>
    
    <!-- Add User Form -->
    <section class="bg-gray-100 dark:bg-gray-700/50 p-4 rounded-lg shadow-sm mb-6">
        <h2 class="text-md font-semibold mb-3 border-b dark:border-gray-600 pb-2">Add New User</h2>
        <form @submit.prevent="addUser" class="space-y-4">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label for="newUsername" class="block text-sm font-medium">Username</label>
                    <input type="text" v-model="newUser.username" id="newUsername" required minlength="3" class="input-field mt-1">
                </div>
                <div>
                    <label for="newPassword" class="block text-sm font-medium">Password (min 8 chars)</label>
                    <input type="password" v-model="newUser.password" id="newPassword" required minlength="8" class="input-field mt-1">
                </div>
                <div>
                    <label for="newLollmsModel" class="block text-sm font-medium">Default LoLLMs Model (Optional)</label>
                    <input type="text" v-model="newUser.lollms_model_name" id="newLollmsModel" class="input-field mt-1" placeholder="e.g., ollama/phi3:latest">
                </div>
                <div>
                    <label for="newSafeStoreVectorizer" class="block text-sm font-medium">Default Vectorizer (Optional)</label>
                    <input type="text" v-model="newUser.safe_store_vectorizer" id="newSafeStoreVectorizer" class="input-field mt-1" placeholder="e.g., st:all-MiniLM-L6-v2">
                </div>
            </div>
             <div class="flex items-center">
                 <input type="checkbox" v-model="newUser.is_admin" id="newUserIsAdmin" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                 <label for="newUserIsAdmin" class="ml-2 block text-sm">Grant Administrator Privileges</label>
             </div>
             <div class="text-right">
                <button type="submit" class="btn btn-primary">Add User</button>
             </div>
        </form>
    </section>

    <!-- Manage Users Table -->
    <section class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm">
        <div class="flex justify-between items-center mb-3 border-b dark:border-gray-600 pb-2">
             <h2 class="text-md font-semibold">Manage Existing Users</h2>
             <button @click="fetchUsers" class="btn btn-secondary !py-1 !px-2 text-xs">Refresh List</button>
        </div>
        <UserTable 
            :users="users" 
            :isLoading="isLoading" 
            @delete-user="deleteUser" 
            @reset-password="resetPassword" 
        />
    </section>
  </div>
</template>