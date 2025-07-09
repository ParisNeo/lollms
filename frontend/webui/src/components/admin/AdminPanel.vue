<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import apiClient from '../../services/api';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import UserTable from './UserTable.vue';

const uiStore = useUiStore();
const dataStore = useDataStore();

const { availableLollmsModels, isLoadingLollmsModels } = storeToRefs(dataStore);

const users = ref([]);
const activeSessions = ref([]);
const isLoadingUsers = ref(false);
const showAddUserForm = ref(false);

const newUser = ref({
  username: '',
  password: '',
  email: '',
  lollms_model_name: '',
  safe_store_vectorizer: '',
  is_admin: false,
});
const settings = ref({});
const originalSettings = ref({});
const isLoadingSettings = ref(false);
const importFile = ref(null);
const isImporting = ref(false);
const activeTab = ref('users');
const fileInputRef = ref(null);

const isSettingsChanged = computed(() => {
  if (isLoadingSettings.value) return false;
  for (const key in settings.value) {
    if (settings.value[key] !== originalSettings.value[key]?.value) {
      return true;
    }
  }
  return false;
});

const categorizedSettings = computed(() => {
  const categories = {};
  if (!originalSettings.value) return {};
  const sortedKeys = Object.keys(originalSettings.value).sort((a,b)=>a.localeCompare(b));
  for (const key of sortedKeys) {
    const setting = originalSettings.value[key];
    if (!setting) continue;
    if (!categories[setting.category]) {
      categories[setting.category] = [];
    }
    categories[setting.category].push(setting);
  }
  return categories;
});

async function setActiveTab(tabName) {
  if (activeTab.value === tabName) return;
  activeTab.value = tabName;
  await fetchDataForActiveTab();
}

async function fetchDataForActiveTab() {
  if (activeTab.value === 'users') {
    await fetchUsers();
    await fetchSettings();
    if (availableLollmsModels.value.length === 0) {
      dataStore.fetchAdminAvailableLollmsModels();
    }
  } else if (activeTab.value === 'settings') {
    await fetchSettings();
  }
}

async function fetchUsers() {
  isLoadingUsers.value = true;
  try {
    const [usersResponse, sessionsResponse] = await Promise.all([
      apiClient.get('/api/admin/users'),
      apiClient.get('/api/admin/active-sessions')
    ]);
    users.value = usersResponse.data;
    activeSessions.value = sessionsResponse.data;
  } catch (error) {
    uiStore.addNotification('Failed to load user data.', 'error');
  } finally {
    isLoadingUsers.value = false;
  }
}

async function fetchSettings() {
  isLoadingSettings.value = true;
  try {
    const response = await apiClient.get('/api/admin/settings');
    const settingsData = response.data;
    const newSettingsValues = {};
    const newOriginalSettings = {};
    settingsData.forEach(setting => {
      newSettingsValues[setting.key] = setting.value;
      newOriginalSettings[setting.key] = { ...setting };
    });
    settings.value = newSettingsValues;
    originalSettings.value = newOriginalSettings;
  } catch (error) {
    uiStore.addNotification('Failed to load global settings.', 'error');
  } finally {
    isLoadingSettings.value = false;
  }
}

function resetSettings() {
  const newSettings = {};
  for (const key in originalSettings.value) {
    newSettings[key] = originalSettings.value[key].value;
  }
  settings.value = newSettings;
  uiStore.addNotification('Changes have been discarded.', 'info');
}

async function saveSettings() {
  if (!isSettingsChanged.value) {
    uiStore.addNotification('No changes to save.', 'info');
    return false; // Return status
  }
  isLoadingSettings.value = true;
  try {
    await apiClient.put('/api/admin/settings', { configs: settings.value });
    uiStore.addNotification('Global settings updated successfully.', 'success');
    await fetchSettings();
    return true; // Return status
  } catch (error) {
    return false; // Return status
  } finally {
    isLoadingSettings.value = false;
  }
}

async function addUser() {
  if (!newUser.value.username || !newUser.value.password || !newUser.value.email) {
    uiStore.addNotification('Username, email, and password are required.', 'warning');
    return;
  }
  isLoadingUsers.value = true;
  try {
    await apiClient.post('/api/admin/users', newUser.value);
    uiStore.addNotification(`User '${newUser.value.username}' created successfully.`, 'success');
    resetNewUserForm();
    await fetchUsers();
  } catch (error) { /* Handled by interceptor */ } 
  finally {
    isLoadingUsers.value = false;
  }
}

function editUser(userToEdit) {
    uiStore.openModal('adminUserEdit', {
        user: userToEdit,
        onUserUpdated: () => {
            fetchUsers(); 
        }
    });
}

async function deleteUser(userId) {
  const confirmed = await uiStore.showConfirmation({
    title: "Delete User",
    message: 'Are you sure you want to delete this user? This will also remove all their data and cannot be undone.',
    confirmText: "Delete",
    confirmClass: "btn-danger"
  });
  if (confirmed) {
    isLoadingUsers.value = true;
    try {
      await apiClient.delete(`/api/admin/users/${userId}`);
      uiStore.addNotification('User deleted successfully.', 'success');
      await fetchUsers();
    } catch(error) { /* Handled by interceptor */ }
    finally { isLoadingUsers.value = false; }
  }
}

function resetPassword(userId) {
    const userToReset = users.value.find(u => u.id === userId);
    if (userToReset) {
        uiStore.openModal('resetPassword', { user: userToReset });
    } else {
        uiStore.addNotification('Could not find the specified user to reset password.', 'error');
    }
}

async function activateUser(userId) {
  isLoadingUsers.value = true;
  try {
    await apiClient.post(`/api/admin/users/${userId}/activate`);
    uiStore.addNotification("User has been activated successfully.", 'success');
    await fetchUsers();
  } catch (error) { /* Handled by interceptor */ }
  finally { isLoadingUsers.value = false; }
}

async function deactivateUser(userId) {
  isLoadingUsers.value = true;
  try {
    await apiClient.post(`/api/admin/users/${userId}/deactivate`);
    uiStore.addNotification("User has been deactivated successfully.", 'success');
    await fetchUsers();
  } catch (error) { /* Handled by interceptor */ }
  finally { isLoadingUsers.value = false; }
}

function resetNewUserForm() {
  newUser.value = { username: '', password: '', email: '', lollms_model_name: '', safe_store_vectorizer: '', is_admin: false };
  showAddUserForm.value = false;
}

function handleFileSelect(event) {
  importFile.value = event.target.files[0] || null;
}

async function handleImport() {
  if (!importFile.value) {
    uiStore.addNotification('Please select a file to import.', 'warning');
    return;
  }
  if (importFile.value.name !== 'webui.db') {
    uiStore.addNotification("Invalid file name. Please select the 'webui.db' file.", 'error');
    return;
  }
  isImporting.value = true;
  const formData = new FormData();
  formData.append('file', importFile.value);
  try {
    const response = await apiClient.post('/api/admin/import-openwebui', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
    uiStore.addNotification(response.data.message, 'success', 8000);
    importFile.value = null;
    if (fileInputRef.value) fileInputRef.value.value = '';
  } catch (error) { /* Handled by interceptor */ } 
  finally { isImporting.value = false; }
}

function emailAllUsers() {
  const emails = users.value.map(u => u.email).filter(Boolean).join(',');
  if (emails) {
    window.location.href = `mailto:${emails}`;
  } else {
    uiStore.addNotification('No users with email addresses found.', 'warning');
  }
}

async function handleForceSettingsOnce() {
  const modelToForce = settings.value.force_model_name;
  if (!modelToForce) {
    uiStore.addNotification('Please select a model to force first in the settings below.', 'warning');
    return;
  }

  if (isSettingsChanged.value) {
    uiStore.addNotification('You have unsaved changes. Saving settings before applying...', 'info');
    const saved = await saveSettings();
    if (!saved) {
      uiStore.addNotification('Could not save settings. Aborting force apply.', 'error');
      return;
    }
  }

  const confirmed = await uiStore.showConfirmation({
    title: "Force Settings on All Users?",
    message: `This will overwrite the current model and context size for ALL users with the values you've configured (${modelToForce}). This action cannot be undone. Are you sure?`,
    confirmText: "Yes, Force Settings",
    confirmClass: "btn-warning",
  });

  if (confirmed) {
    isLoadingSettings.value = true;
    const payload = {
      model_name: modelToForce,
      context_size: settings.value.force_context_size,
    };
    try {
      await apiClient.post('/api/admin/force-settings-once', payload);
      uiStore.addNotification("Settings have been applied to all users.", "success");
    } catch (e) {
      // Error is handled by the global interceptor
    } finally {
      isLoadingSettings.value = false;
    }
  }
}

onMounted(() => {
  fetchDataForActiveTab();
});
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
      <div v-if="!showAddUserForm" class="flex justify-end mb-6">
        <button @click="showAddUserForm = true" class="btn btn-primary">Add New User</button>
      </div>

      <section v-if="showAddUserForm" class="bg-gray-100 dark:bg-gray-700/50 p-4 rounded-lg shadow-sm mb-6">
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
          </div>
          <div class="flex items-center">
            <input type="checkbox" v-model="newUser.is_admin" id="newUserIsAdmin" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500">
            <label for="newUserIsAdmin" class="ml-2 block text-sm">Grant Administrator Privileges</label>
          </div>
          <div class="text-right space-x-2">
            <button type="button" @click="resetNewUserForm" class="btn btn-secondary">Cancel</button>
            <button type="submit" class="btn btn-primary" :disabled="isLoadingUsers">Add User</button>
          </div>
        </form>
      </section>

      <section class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm mb-6">
        <h2 class="text-md font-semibold mb-3 border-b dark:border-gray-600 pb-2">Global User Overrides</h2>
        <div class="space-y-4">
          <div>
            <label for="forceMode" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Force Model Mode</label>
            <select id="forceMode" v-model="settings.force_model_mode" class="input-field mt-1 max-w-md">
              <option value="disabled">Disabled</option>
              <option value="force_once">Force Once (Set User Preference)</option>
              <option value="force_always">Force Always (Session Override)</option>
            </select>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label for="forceModelName" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Model to Force</label>
              <select id="forceModelName" v-model="settings.force_model_name" class="input-field mt-1" :disabled="isLoadingLollmsModels || (settings.force_model_mode === 'disabled')">
                  <option v-if="isLoadingLollmsModels" disabled value="">Loading models...</option>
                  <option v-else-if="availableLollmsModels.length === 0" disabled value="">No models available</option>
                  <option v-for="model in availableLollmsModels" :key="model.id" :value="model.id">{{ model.name }}</option>
              </select>
            </div>
            <div>
              <label for="forceCtxSize" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Context Size to Force</label>
              <input type="number" id="forceCtxSize" v-model.number="settings.force_context_size" class="input-field mt-1" :disabled="settings.force_model_mode === 'disabled'">
            </div>
          </div>
          <div class="flex justify-end items-center space-x-4">
              <button v-if="settings.force_model_mode === 'force_once'" type="button" @click="handleForceSettingsOnce" class="btn btn-warning" :disabled="isLoadingSettings">
                  Apply to All Users Now
              </button>
              <button @click="saveSettings" class="btn btn-primary" :disabled="!isSettingsChanged || isLoadingSettings">Save Overrides</button>
          </div>
        </div>
      </section>

      <section class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm">
        <div class="flex justify-between items-center mb-3 border-b dark:border-gray-600 pb-2">
          <h2 class="text-md font-semibold">Manage Existing Users</h2>
          <div class="flex items-center space-x-2">
            <button @click="emailAllUsers" class="btn btn-secondary !py-1 !px-2 text-xs">Email All Users</button>
            <button @click="fetchUsers" class="btn btn-secondary !py-1 !px-2 text-xs" :disabled="isLoadingUsers">
                <span v-if="isLoadingUsers">Refreshing...</span>
                <span v-else>Refresh List</span>
            </button>
          </div>
        </div>
        <UserTable 
          :users="users" 
          :active-sessions="activeSessions"
          :isLoading="isLoadingUsers" 
          @edit-user="editUser"
          @delete-user="deleteUser" 
          @reset-password="resetPassword" 
          @activate-user="activateUser"
          @deactivate-user="deactivateUser"
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
             <template v-if="category !== 'Global LLM Overrides'">
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
             </template>
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
                            ref="fileInputRef"
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