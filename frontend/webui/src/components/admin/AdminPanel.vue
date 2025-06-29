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
      activeSessions: [],
      isLoadingUsers: false,
      newUser: {
        username: '',
        password: '',
        email: '',
        lollms_model_name: '',
        safe_store_vectorizer: '',
        is_admin: false,
      },
      settings: {},
      originalSettings: {},
      isLoadingSettings: false,
      importFile: null,
      isImporting: false,
      activeTab: 'users',
    };
  },
  computed: {
    isSettingsChanged() {
      for (const key in this.settings) {
        if (this.settings[key] !== this.originalSettings[key]?.value) {
          return true;
        }
      }
      return false;
    },
    categorizedSettings() {
      const categories = {};
      const sortedKeys = Object.keys(this.originalSettings).sort();
      for (const key of sortedKeys) {
        const setting = this.originalSettings[key];
        if (!categories[setting.category]) {
          categories[setting.category] = [];
        }
        categories[setting.category].push(setting);
      }
      return categories;
    }
  },
  created() {
    this.fetchDataForActiveTab();
  },
  methods: {
    async setActiveTab(tabName) {
      if (this.activeTab === tabName) return;
      this.activeTab = tabName;
      await this.fetchDataForActiveTab();
    },
    async fetchDataForActiveTab() {
      if (this.activeTab === 'users') {
        await this.fetchUsers();
      } else if (this.activeTab === 'settings') {
        await this.fetchSettings();
      }
    },
    async fetchUsers() {
      this.isLoadingUsers = true;
      try {
        const [usersResponse, sessionsResponse] = await Promise.all([
          apiClient.get('/api/admin/users'),
          apiClient.get('/api/admin/active-sessions')
        ]);
        this.users = usersResponse.data;
        this.activeSessions = sessionsResponse.data;
      } catch (error) {
        useUiStore().addNotification('Failed to load user data.', 'error');
      } finally {
        this.isLoadingUsers = false;
      }
    },
    async fetchSettings() {
      this.isLoadingSettings = true;
      try {
        const response = await apiClient.get('/api/admin/settings');
        const settingsData = response.data;
        const newSettingsValues = {};
        const newOriginalSettings = {};
        
        settingsData.forEach(setting => {
          newSettingsValues[setting.key] = setting.value;
          newOriginalSettings[setting.key] = { ...setting };
        });

        this.settings = newSettingsValues;
        this.originalSettings = newOriginalSettings;
      } catch (error) {
        useUiStore().addNotification('Failed to load global settings.', 'error');
      } finally {
        this.isLoadingSettings = false;
      }
    },
    resetSettings() {
      const newSettings = {};
      for (const key in this.originalSettings) {
        newSettings[key] = this.originalSettings[key].value;
      }
      this.settings = newSettings;
      useUiStore().addNotification('Changes have been discarded.', 'info');
    },
    async saveSettings() {
      const uiStore = useUiStore();
      if (!this.isSettingsChanged) {
        uiStore.addNotification('No changes to save.', 'info');
        return;
      }
      this.isLoadingSettings = true;
      try {
        await apiClient.put('/api/admin/settings', { configs: this.settings });
        uiStore.addNotification('Global settings updated successfully.', 'success', 6000);
        await this.fetchSettings();
      } catch (error) {
        // Handled by interceptor
      } finally {
        this.isLoadingSettings = false;
      }
    },
    async addUser() {
      const uiStore = useUiStore();
      if (!this.newUser.username || !this.newUser.password || !this.newUser.email) {
        uiStore.addNotification('Username, email, and password are required.', 'warning');
        return;
      }
      this.isLoadingUsers = true;
      try {
        await apiClient.post('/api/admin/users', this.newUser);
        uiStore.addNotification(`User '${this.newUser.username}' created successfully.`, 'success');
        this.resetNewUserForm();
        await this.fetchUsers();
      } catch (error) {
        // Handled by interceptor
      } finally {
        this.isLoadingUsers = false;
      }
    },
    async deleteUser(userId) {
      const uiStore = useUiStore();
      if (confirm('Are you sure you want to delete this user? This will also remove all their data and cannot be undone.')) {
        this.isLoadingUsers = true;
        try {
          await apiClient.delete(`/api/admin/users/${userId}`);
          uiStore.addNotification('User deleted successfully.', 'success');
          await this.fetchUsers();
        } catch(error) { /* Handled by interceptor */ }
        finally { this.isLoadingUsers = false; }
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
    async activateUser(userId) {
      this.isLoadingUsers = true;
      const uiStore = useUiStore();
      try {
        await apiClient.post(`/api/admin/users/${userId}/activate`);
        uiStore.addNotification("User has been activated successfully.", 'success');
        await this.fetchUsers();
      } catch (error) { /* Handled by interceptor */ }
      finally { this.isLoadingUsers = false; }
    },
    resetNewUserForm() {
      this.newUser = { username: '', password: '', email: '', lollms_model_name: '', safe_store_vectorizer: '', is_admin: false };
    },
    handleFileSelect(event) {
      this.importFile = event.target.files[0] || null;
    },
    async handleImport() {
      const uiStore = useUiStore();
      if (!this.importFile) {
        uiStore.addNotification('Please select a file to import.', 'warning');
        return;
      }

      if (this.importFile.name !== 'webui.db') {
        uiStore.addNotification("Invalid file name. Please select the 'webui.db' file.", 'error');
        return;
      }

      this.isImporting = true;
      const formData = new FormData();
      formData.append('file', this.importFile);

      try {
        const response = await apiClient.post('/api/admin/import-openwebui', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        uiStore.addNotification(response.data.message, 'success', 8000);
        this.importFile = null;
        if (this.$refs.fileInput) this.$refs.fileInput.value = '';
      } catch (error) {
        // Handled by interceptor
      } finally {
        this.isImporting = false;
      }
    }
  }
};
</script>

<template>
  <div>
    <h4 class="text-lg font-semibold mb-4">Administration</h4>
    
    <div class="border-b border-gray-200 dark:border-gray-700 mb-6">
      <nav class="-mb-px flex space-x-6" aria-label="Tabs">
        <button @click="setActiveTab('users')"
                :class="[activeTab === 'users' ? 'border-blue-500 text-blue-600 dark:border-blue-400 dark:text-blue-300' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-500']"
                class="whitespace-nowrap py-3 px-1 border-b-2 font-medium text-sm transition-colors duration-200">
          User Management
        </button>
        <button @click="setActiveTab('settings')"
                :class="[activeTab === 'settings' ? 'border-blue-500 text-blue-600 dark:border-blue-400 dark:text-blue-300' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-500']"
                class="whitespace-nowrap py-3 px-1 border-b-2 font-medium text-sm transition-colors duration-200">
          Global Settings
        </button>
        <button @click="setActiveTab('import')"
                :class="[activeTab === 'import' ? 'border-blue-500 text-blue-600 dark:border-blue-400 dark:text-blue-300' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-500']"
                class="whitespace-nowrap py-3 px-1 border-b-2 font-medium text-sm transition-colors duration-200">
          Data Import
        </button>
      </nav>
    </div>

    <div v-if="activeTab === 'users'">
      <section class="bg-gray-100 dark:bg-gray-700/50 p-4 rounded-lg shadow-sm mb-6">
        <h2 class="text-md font-semibold mb-3 border-b dark:border-gray-600 pb-2">Add New User</h2>
        <form @submit.prevent="addUser" class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label for="newUsername" class="block text-sm font-medium">Username</label>
              <input type="text" v-model="newUser.username" id="newUsername" required minlength="3" class="input-field mt-1">
            </div>
            <div>
              <label for="newEmail" class="block text-sm font-medium">Email</label>
              <input type="email" v-model="newUser.email" id="newEmail" required class="input-field mt-1">
            </div>
            <div>
              <label for="newPassword" class="block text-sm font-medium">Password (min 8 chars)</label>
              <input type="password" v-model="newUser.password" id="newPassword" required minlength="8" class="input-field mt-1">
            </div>
            <div>
              <label for="newLollmsModel" class="block text-sm font-medium">Default LoLLMs Model (Optional)</label>
              <input type="text" v-model="newUser.lollms_model_name" id="newLollmsModel" class="input-field mt-1" placeholder="Uses global default if empty">
            </div>
            <div>
              <label for="newSafeStoreVectorizer" class="block text-sm font-medium">Default Vectorizer (Optional)</label>
              <input type="text" v-model="newUser.safe_store_vectorizer" id="newSafeStoreVectorizer" class="input-field mt-1" placeholder="Uses global default if empty">
            </div>
          </div>
          <div class="flex items-center">
            <input type="checkbox" v-model="newUser.is_admin" id="newUserIsAdmin" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500">
            <label for="newUserIsAdmin" class="ml-2 block text-sm">Grant Administrator Privileges</label>
          </div>
          <div class="text-right">
            <button type="submit" class="btn btn-primary" :disabled="isLoadingUsers">Add User</button>
          </div>
        </form>
      </section>

      <section class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm">
        <div class="flex justify-between items-center mb-3 border-b dark:border-gray-600 pb-2">
          <h2 class="text-md font-semibold">Manage Existing Users</h2>
          <button @click="fetchUsers" class="btn btn-secondary !py-1 !px-2 text-xs" :disabled="isLoadingUsers">
            <span v-if="isLoadingUsers">Refreshing...</span>
            <span v-else>Refresh List</span>
          </button>
        </div>
        <UserTable 
          :users="users" 
          :active-sessions="activeSessions"
          :isLoading="isLoadingUsers" 
          @delete-user="deleteUser" 
          @reset-password="resetPassword" 
          @activate-user="activateUser"
        />
      </section>
    </div>
    
    <div v-if="activeTab === 'settings'">
      <section class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm">
        <div class="flex justify-between items-center mb-4 border-b dark:border-gray-600 pb-3">
          <h2 class="text-md font-semibold">Application Settings</h2>
          <div class="space-x-2">
            <button @click="resetSettings" class="btn btn-secondary" :disabled="!isSettingsChanged || isLoadingSettings">Reset</button>
            <button @click="saveSettings" class="btn btn-primary" :disabled="!isSettingsChanged || isLoadingSettings">
              <span v-if="isLoadingSettings">Saving...</span>
              <span v-else>Save Changes</span>
            </button>
          </div>
        </div>
        <div v-if="isLoadingSettings" class="text-center p-8 text-gray-500">
          Loading settings...
        </div>
        <form v-else @submit.prevent="saveSettings" class="space-y-8">
          <div v-for="(group, category) in categorizedSettings" :key="category">
            <h3 class="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">{{ category }}</h3>
            <div class="space-y-6 bg-gray-50 dark:bg-gray-700/50 p-4 rounded-md">
              <div v-for="setting in group" :key="setting.key">
                <label :for="`setting-${setting.key}`" class="block text-sm font-medium text-gray-700 dark:text-gray-300">{{ setting.description }}</label>
                
                <div class="mt-2">
                  <label v-if="setting.type === 'boolean'" :for="`setting-${setting.key}`" class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" v-model="settings[setting.key]" class="sr-only peer" :id="`setting-${setting.key}`">
                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-600 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-500 peer-checked:bg-blue-600"></div>
                    <span class="ml-3 text-sm font-medium text-gray-900 dark:text-gray-200">{{ settings[setting.key] ? 'Enabled' : 'Disabled' }}</span>
                  </label>

                  <select v-else-if="setting.key === 'registration_mode'" v-model="settings[setting.key]" :id="`setting-${setting.key}`" class="input-field max-w-sm">
                    <option value="direct">Direct (instantly active)</option>
                    <option value="admin_approval">Admin Approval</option>
                  </select>

                  <input v-else
                        :type="setting.type === 'string' ? 'text' : 'number'"
                        :step="setting.type === 'float' ? '0.1' : '1'"
                        v-model.number="settings[setting.key]"
                        :id="`setting-${setting.key}`"
                        class="input-field max-w-sm">
                </div>
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-2">Key: <code class="bg-gray-200 dark:bg-gray-600 px-1 rounded">{{ setting.key }}</code></p>
              </div>
            </div>
          </div>
        </form>
      </section>
    </div>

    <div v-if="activeTab === 'import'">
        <section class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm">
            <h2 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">Import from OpenWebUI</h2>
            <p class="mt-2 max-w-2xl text-sm text-gray-500 dark:text-gray-400">
                Migrate users and their discussion histories from an OpenWebUI instance.
            </p>

            <div class="mt-6 border-t border-gray-200 dark:border-gray-700 pt-6">
                <div class="prose dark:prose-invert text-sm max-w-none">
                    <p><strong>Instructions:</strong></p>
                    <ol>
                        <li>Locate your OpenWebUI data directory (e.g., inside the Docker container at <code>/app/backend/data</code>).</li>
                        <li>Find the main database file named <strong><code>webui.db</code></strong>.</li>
                        <li>Click "Select File" and upload that single <code>webui.db</code> file.</li>
                        <li>Click "Start Import". The process runs in the background and may take several minutes. Check the server logs for detailed progress.</li>
                    </ol>
                    <p class="font-semibold text-yellow-600 dark:text-yellow-400">
                      Important: This tool migrates users based on their email. If a user with the same email already exists, their core data will be skipped, but their discussions will still be imported. Passwords will be migrated seamlessly.
                    </p>
                </div>
                
                <div class="mt-6">
                    <label for="file-upload" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
                        OpenWebUI Database File
                    </label>
                    <div class="mt-2 flex items-center">
                        <input
                            ref="fileInput"
                            @change="handleFileSelect"
                            type="file"
                            accept=".db"
                            class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-blue-900/50 dark:file:text-blue-300 dark:hover:file:bg-blue-900"
                        />
                    </div>
                     <div v-if="importFile" class="mt-2 text-sm text-gray-600 dark:text-gray-400">
                        Selected: <strong>{{ importFile.name }}</strong>
                    </div>
                </div>

                <div class="mt-6 flex justify-end">
                    <button
                        @click="handleImport"
                        :disabled="isImporting || !importFile"
                        class="btn btn-primary"
                    >
                        <span v-if="isImporting">Importing...</span>
                        <span v-else>Start Import</span>
                    </button>
                </div>
            </div>
        </section>
    </div>

  </div>
</template>