<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import GenericModal from '../ui/GenericModal.vue';
import IconUploader from '../ui/IconUploader.vue';

const uiStore = useUiStore();
const dataStore = useDataStore();

const props = computed(() => uiStore.modalData('serviceRegistration'));
const item = computed(() => props.value?.item);
const itemType = computed(() => props.value?.itemType || 'app');
const ownerType = computed(() => props.value?.ownerType || 'user');
const onRegistered = computed(() => props.value?.onRegistered);

const isEditMode = computed(() => !!item.value);
const title = computed(() => `${isEditMode.value ? 'Edit' : 'Register'} ${ownerType.value === 'system' ? 'System' : 'Personal'} ${itemType.value.toUpperCase()}`);

const form = ref({});
const isLoading = ref(false);

const getInitialFormState = () => ({
    name: '', url: '', icon: null, active: true,
    authentication_type: 'none', authentication_key: '',
    sso_redirect_uri: '', sso_user_infos_to_share: [],
    type: ownerType.value,
    autostart: false,
    allow_openai_api_access: false,
});

watch(props, (newProps) => {
    if (newProps) {
        form.value = { ...getInitialFormState(), ...(newProps.item || {}) };
    } else {
        form.value = getInitialFormState();
    }
}, { immediate: true, deep: true });

async function handleSubmit() {
    isLoading.value = true;
    try {
        const payload = { ...form.value };
        if (itemType.value === 'app') {
            if (isEditMode.value) {
                await dataStore.updateApp(item.value.id, payload);
            } else {
                await dataStore.addApp(payload);
            }
        } else { // mcp
            if (isEditMode.value) {
                await dataStore.updateMcp(item.value.id, payload);
            } else {
                await dataStore.addMcp(payload);
            }
        }
        if (onRegistered.value) {
            onRegistered.value();
        }
        uiStore.closeModal('serviceRegistration');
    } catch(e) {
        // Handled globally
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal modal-name="serviceRegistration" :title="title" maxWidthClass="max-w-2xl">
        <template #body>
            <form @submit.prevent="handleSubmit" class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label for="service-name" class="label">Name</label>
                        <input id="service-name" v-model="form.name" type="text" class="input-field" required>
                    </div>
                     <div>
                        <label for="service-url" class="label">URL</label>
                        <input id="service-url" v-model="form.url" type="url" class="input-field" required>
                    </div>
                </div>
                <div>
                    <label class="label">Icon</label>
                    <IconUploader v-model="form.icon" />
                </div>
                 <div>
                    <label for="service-auth-type" class="label">Authentication Type</label>
                    <select id="service-auth-type" v-model="form.authentication_type" class="input-field">
                        <option value="none">None</option>
                        <option value="bearer">Bearer Token</option>
                        <option value="lollms_sso">LoLLMs SSO</option>
                    </select>
                </div>
                <div v-if="form.authentication_type === 'bearer'">
                    <label for="service-auth-key" class="label">Authentication Key</label>
                    <input id="service-auth-key" v-model="form.authentication_key" type="password" class="input-field" placeholder="Enter Bearer token">
                </div>
                <div v-if="form.authentication_type === 'lollms_sso'" class="space-y-4 p-4 border rounded-md dark:border-gray-600">
                    <h4 class="font-semibold">SSO Configuration</h4>
                    <div>
                        <label for="sso-redirect-uri" class="label">Redirect URI</label>
                        <input id="sso-redirect-uri" v-model="form.sso_redirect_uri" type="url" class="input-field" placeholder="e.g., https://myapp.com/callback">
                    </div>
                </div>
                
                <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                    <span class="text-sm font-medium">Start on System Startup</span>
                     <button @click="form.autostart = !form.autostart" type="button" :class="[form.autostart ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                        <span :class="[form.autostart ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                    </button>
                </div>

                <div v-if="itemType === 'app'" class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                    <span class="flex-grow flex flex-col">
                        <span class="text-sm font-medium">Allow Access to LoLLMs OpenAI-compatible API</span>
                        <span class="text-sm text-gray-500 dark:text-gray-400">Exposes your active LLM to this app via a secure API.</span>
                    </span>
                     <button @click="form.allow_openai_api_access = !form.allow_openai_api_access" type="button" :class="[form.allow_openai_api_access ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                        <span :class="[form.allow_openai_api_access ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                    </button>
                </div>

                <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                    <span class="text-sm font-medium">Active</span>
                     <button @click="form.active = !form.active" type="button" :class="[form.active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                        <span :class="[form.active ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                    </button>
                </div>
            </form>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('serviceRegistration')" class="btn btn-secondary">Cancel</button>
            <button @click="handleSubmit" class="btn btn-primary" :disabled="isLoading">{{ isLoading ? 'Saving...' : (isEditMode ? 'Save Changes' : 'Register') }}</button>
        </template>
    </GenericModal>
</template>