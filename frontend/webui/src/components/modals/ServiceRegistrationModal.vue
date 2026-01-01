<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import GenericModal from './GenericModal.vue';
import apiClient from '../../services/api';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();

// Modal props: item (for edit), itemType ('app' or 'mcp'), ownerType ('user' or 'system'), onRegistered (callback)
const props = computed(() => uiStore.modalData('serviceRegistration'));
const itemToEdit = computed(() => props.value?.item);
const itemType = computed(() => props.value?.itemType || 'app');
const ownerType = computed(() => props.value?.ownerType || 'system');

const form = ref({
    name: '',
    url: '',
    authentication_type: 'none',
    authentication_key: '',
    header_name: 'X-API-Key' // Default header name for api_key type
});
const isKeyVisible = ref(false);
const isLoading = ref(false);

const modalTitle = computed(() => {
    const typeLabel = itemType.value.toUpperCase();
    if (itemToEdit.value) return `Edit ${typeLabel} Registration`;
    return `Register External ${typeLabel}`;
});

watch(itemToEdit, (newItem) => {
    // Reset visibility state whenever the item changes
    isKeyVisible.value = false;
    
    if (newItem) {
        form.value.name = newItem.name;
        form.value.url = newItem.url;
        form.value.authentication_type = newItem.authentication_type || 'none';
        
        // Handle potentially JSON-encoded authentication key
        if (newItem.authentication_type === 'api_key' && newItem.authentication_key) {
             try {
                // Try parsing JSON first
                const data = JSON.parse(newItem.authentication_key);
                if (typeof data === 'object' && data !== null) {
                    form.value.authentication_key = data.key || '';
                    form.value.header_name = data.header_name || 'X-API-Key';
                } else {
                    // Fallback if not JSON object
                    form.value.authentication_key = newItem.authentication_key;
                    form.value.header_name = 'X-API-Key';
                }
             } catch (e) {
                // Not JSON, assume raw key
                form.value.authentication_key = newItem.authentication_key;
                form.value.header_name = 'X-API-Key';
             }
        } else {
            form.value.authentication_key = newItem.authentication_key || '';
            form.value.header_name = 'X-API-Key';
        }
    } else {
        // Reset form for new item
        form.value = {
            name: '',
            url: '',
            authentication_type: 'none',
            authentication_key: '',
            header_name: 'X-API-Key'
        };
    }
}, { immediate: true });

function setHeader(name) {
    form.value.header_name = name;
}

async function handleSubmit() {
    if (!form.value.name || !form.value.url) {
        uiStore.addNotification('Name and URL are required.', 'warning');
        return;
    }

    isLoading.value = true;
    try {
        let finalAuthKey = form.value.authentication_key;
        
        // Pack key and header into JSON if type is api_key
        if (form.value.authentication_type === 'api_key') {
            finalAuthKey = JSON.stringify({
                key: form.value.authentication_key,
                header_name: form.value.header_name
            });
        }

        const payload = {
            name: form.value.name,
            url: form.value.url,
            type: ownerType.value,
            authentication_type: form.value.authentication_type,
            authentication_key: finalAuthKey
        };

        if (itemType.value === 'app') {
             uiStore.addNotification('Manual app registration not fully implemented in UI yet.', 'warning');
             return; 

        } else {
            // MCP Registration
            if (itemToEdit.value) {
                // Update existing manually registered MCP
                // We use the direct API endpoint for mcps
                await apiClient.put(`/api/mcps/${itemToEdit.value.id}`, payload);
                uiStore.addNotification('MCP updated successfully.', 'success');

            } else {
                // Create new
                await apiClient.post('/api/mcps', payload);
                uiStore.addNotification('MCP registered successfully.', 'success');
            }
        }

        if (props.value?.onRegistered) {
            props.value.onRegistered();
        }
        uiStore.closeModal('serviceRegistration');
    } catch (error) {
        console.error(error);
        uiStore.addNotification('Failed to save service registration.', 'error');
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modal-name="serviceRegistration"
        :title="modalTitle"
        max-width-class="max-w-lg"
    >
        <template #body>
            <form @submit.prevent="handleSubmit" class="space-y-6">
                <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Name</label>
                    <input v-model="form.name" type="text" required class="input-field mt-1 w-full" placeholder="My Service" />
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">URL</label>
                    <input v-model="form.url" type="url" required class="input-field mt-1 w-full" placeholder="http://localhost:8000" />
                    <p class="text-xs text-gray-500 mt-1">The base URL of the service.</p>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Authentication</label>
                    <select v-model="form.authentication_type" class="input-field mt-1 w-full">
                        <option value="none">None</option>
                        <option value="api_key">API Key (Header)</option>
                        <option value="bearer">Bearer Token</option>
                        <option value="lollms_chat_auth">LoLLMs Chat Auth (Internal)</option>
                    </select>
                </div>

                <div v-if="form.authentication_type !== 'none' && form.authentication_type !== 'lollms_chat_auth'" class="space-y-4 border-l-2 border-gray-200 dark:border-gray-700 pl-4">
                    
                    <!-- API Key Header Configuration -->
                    <div v-if="form.authentication_type === 'api_key'">
                        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Header Name</label>
                        <input v-model="form.header_name" type="text" class="input-field mt-1 w-full" placeholder="X-API-Key" />
                        <div class="flex flex-wrap gap-2 mt-2">
                            <button type="button" @click="setHeader('X-API-Key')" class="px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors border dark:border-gray-600">X-API-Key</button>
                            <button type="button" @click="setHeader('X-AgentsKB-Key')" class="px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors border dark:border-gray-600">X-AgentsKB-Key</button>
                            <button type="button" @click="setHeader('Authorization')" class="px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors border dark:border-gray-600">Authorization</button>
                        </div>
                    </div>

                    <div>
                        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {{ form.authentication_type === 'bearer' ? 'Token' : 'Key' }}
                        </label>
                        <div class="relative mt-1">
                            <input 
                                :type="isKeyVisible ? 'text' : 'password'" 
                                v-model="form.authentication_key" 
                                class="input-field w-full pr-10" 
                                placeholder="Enter secret..." 
                            />
                            <button 
                                type="button" 
                                @click="isKeyVisible = !isKeyVisible" 
                                class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 cursor-pointer z-10 focus:outline-none"
                                title="Toggle Visibility"
                            >
                                <IconEyeOff v-if="isKeyVisible" class="w-5 h-5" />
                                <IconEye v-else class="w-5 h-5" />
                            </button>
                        </div>
                    </div>
                </div>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('serviceRegistration')" class="btn btn-secondary">Cancel</button>
                <button @click="handleSubmit" class="btn btn-primary" :disabled="isLoading">
                    <IconAnimateSpin v-if="isLoading" class="w-5 h-5 mr-2 animate-spin" />
                    {{ itemToEdit ? 'Save Changes' : 'Register' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>
