<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import GenericModal from '../ui/GenericModal.vue';
import IconWrenchScrewdriver from '../../assets/icons/IconWrenchScrewdriver.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';

const uiStore = useUiStore();
const dataStore = useDataStore();

const props = computed(() => uiStore.modalData('serviceRegistration'));
const item = computed(() => props.value?.item);
const itemType = computed(() => props.value?.itemType); // 'mcp' or 'app'
const isInstalled = computed(() => props.value?.isInstalled || false);

const ssoInfoOptions = [
    { id: 'email', label: 'Email Address' },
    { id: 'first_name', label: 'First Name' },
    { id: 'family_name', label: 'Family Name' },
    { id: 'birth_date', label: 'Birth Date' },
];

const getInitialFormState = () => ({
    name: '',
    client_id: '',
    url: '',
    icon: '',
    active: true,
    authentication_type: 'none',
    authentication_key: '',
    sso_redirect_uri: '',
    sso_user_infos_to_share: [],
    port: null,
});

const form = ref(getInitialFormState());
const isLoading = ref(false);
const showKey = ref(false);
const fileInput = ref(null);
const formIconLoadFailed = ref(false);

const isEditMode = computed(() => !!item.value);
const isSsoAuth = computed(() => form.value.authentication_type === 'lollms_sso');
const isEditingInstalledApp = computed(() => isEditMode.value && isInstalled.value);

const modalTitle = computed(() => {
    const action = isEditMode.value ? 'Edit' : 'Add New';
    const type = itemType.value === 'mcp' ? 'MCP Server' : 'Application';
    const context = isEditingInstalledApp.value ? 'Installed' : 'External';
    return `${action} ${isEditMode.value ? context : ''} ${type}`;
});

watch(props, (newVal) => {
    if (newVal) {
        populateForm();
    }
}, { immediate: true, deep: true });

watch(() => form.value.icon, () => {
    formIconLoadFailed.value = false;
});

function populateForm() {
    if (isEditMode.value) {
        form.value.name = item.value.name || '';
        form.value.client_id = item.value.client_id || '';
        form.value.url = item.value.url || '';
        form.value.icon = item.value.icon || '';
        form.value.active = typeof item.value.active === 'boolean' ? item.value.active : true;
        form.value.authentication_type = item.value.authentication_type || 'none';
        form.value.authentication_key = ''; // Never populate existing key
        form.value.sso_redirect_uri = item.value.sso_redirect_uri || '';
        form.value.sso_user_infos_to_share = item.value.sso_user_infos_to_share || [];
        form.value.port = item.value.port || null;
    } else {
        form.value = getInitialFormState();
    }
}

function handleClose() {
    form.value = getInitialFormState();
    showKey.value = false;
    uiStore.closeModal('serviceRegistration');
}

function handleFormIconError() {
    formIconLoadFailed.value = true;
}

async function handleFormSubmit() {
    if (!form.value.name || (!form.value.url && !isEditingInstalledApp.value)) {
        uiStore.addNotification('Name and URL are required.', 'warning');
        return;
    }
    isLoading.value = true;
    try {
        const payload = { ...form.value };
        if (payload.port) payload.port = Number(payload.port);
        
        const isApp = itemType.value === 'app';
        if (isEditMode.value) {
            await (isApp ? dataStore.updateApp(item.value.id, payload) : dataStore.updateMcp(item.value.id, payload));
        } else {
            const ownerType = props.value?.ownerType || 'user';
            payload.type = ownerType;
            await (isApp ? dataStore.addApp(payload) : dataStore.addMcp(payload));
        }
        handleClose();
    } finally {
        isLoading.value = false;
    }
}

async function handleGenerateSecret() {
    const confirmed = await uiStore.showConfirmation({
        title: `Generate New Secret?`,
        message: `This will generate a new SSO secret for '${item.value.name}'. Your existing application using the old secret will no longer be able to authenticate. This action is irreversible.`,
        confirmText: 'Generate Secret'
    });
    if (confirmed) {
        const isApp = itemType.value === 'app';
        const secret = await (isApp ? dataStore.generateAppSsoSecret(item.value.id) : dataStore.generateMcpSsoSecret(item.value.id));
        if (secret) {
            uiStore.openModal('passwordResetLink', {
                title: 'New SSO Secret Generated',
                message: `This is the new SSO secret for '${item.value.name}'. Copy it now, as you will not be able to see it again.`,
                link: secret,
                copyButtonText: 'Copy Secret'
            });
        }
    }
}

function triggerFileInput() {
    fileInput.value.click();
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'];
    if (!allowedTypes.includes(file.type)) {
        uiStore.addNotification('Invalid file type. Please select an image.', 'error');
        return;
    }
    
    if (file.type === 'image/svg+xml') {
        const reader = new FileReader();
        reader.onload = (e) => { form.value.icon = e.target.result; };
        reader.onerror = () => { uiStore.addNotification('Failed to read the SVG file.', 'error'); };
        reader.readAsDataURL(file);
        event.target.value = '';
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
            const MAX_WIDTH = 128;
            const MAX_HEIGHT = 128;
            let width = img.width;
            let height = img.height;

            if (width > height) {
                if (width > MAX_WIDTH) {
                    height = Math.round(height * (MAX_WIDTH / width));
                    width = MAX_WIDTH;
                }
            } else {
                if (height > MAX_HEIGHT) {
                    width = Math.round(width * (MAX_HEIGHT / height));
                    height = MAX_HEIGHT;
                }
            }

            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, width, height);

            form.value.icon = canvas.toDataURL('image/png');
        };
        img.onerror = () => { uiStore.addNotification('Failed to load image for processing.', 'error'); };
        img.src = e.target.result;
    };
    reader.onerror = () => { uiStore.addNotification('Failed to read the file.', 'error'); };
    reader.readAsDataURL(file);
    
    event.target.value = '';
}
</script>

<template>
    <GenericModal modal-name="serviceRegistration" :title="modalTitle" max-width-class="max-w-2xl">
        <template #body>
            <form @submit.prevent="handleFormSubmit" class="space-y-6">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    <div>
                        <label for="formName" class="block text-sm font-medium">Name</label>
                        <input type="text" id="formName" v-model="form.name" class="input-field mt-1" :placeholder="itemType === 'mcp' ? 'My Local Server' : 'My Web App'" required>
                    </div>
                    <div v-if="!isEditingInstalledApp">
                        <label for="formUrl" class="block text-sm font-medium">URL</label>
                        <input type="url" id="formUrl" v-model="form.url" class="input-field mt-1" :placeholder="itemType === 'mcp' ? 'http://127.0.0.1:9602' : 'https://example.com'" required>
                        <p v-if="itemType === 'mcp'" class="mt-1 text-xs text-gray-500 dark:text-gray-400">
                            Enter the base URL. The system will automatically append the <code>/mcp</code> endpoint.
                        </p>
                    </div>
                    <div v-else>
                        <label for="formPort" class="block text-sm font-medium">Port</label>
                        <input type="number" id="formPort" v-model="form.port" class="input-field mt-1" placeholder="e.g., 9601" required>
                    </div>
                </div>

                <div>
                    <label class="block text-sm font-medium">Icon (Optional)</label>
                    <div class="mt-2 flex items-center gap-x-4">
                        <div class="h-16 w-16 rounded-md bg-gray-200 dark:bg-gray-700 flex items-center justify-center overflow-hidden">
                            <img v-if="form.icon && !formIconLoadFailed" :src="form.icon" @error="handleFormIconError" alt="Icon Preview" class="h-full w-full object-cover">
                            <IconWrenchScrewdriver v-else class="w-8 h-8 text-gray-500 dark:text-gray-400" />
                        </div>
                        <div class="flex-grow space-y-2">
                            <input type="text" v-model="form.icon" class="input-field" placeholder="Paste image URL or upload a file">
                            <div class="flex items-center gap-x-3">
                                <button @click="triggerFileInput" type="button" class="btn btn-secondary text-sm">Upload File</button>
                                <button v-if="form.icon" @click="form.icon = ''" type="button" class="text-sm font-medium text-red-600 hover:text-red-500">Remove</button>
                            </div>
                        </div>
                    </div>
                    <input type="file" ref="fileInput" @change="handleFileSelect" class="hidden" accept="image/png, image/jpeg, image/gif, image/webp, image/svg+xml">
                </div>

                <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md" :title="isEditingInstalledApp ? 'Status is controlled from the Apps Management panel' : ''">
                    <span class="flex-grow flex flex-col">
                        <span class="text-sm font-medium" :class="isEditingInstalledApp ? 'text-gray-500 dark:text-gray-400' : 'text-gray-900 dark:text-gray-100'">Active</span>
                        <span class="text-sm text-gray-500 dark:text-gray-400">Inactive items cannot be used.</span>
                    </span>
                    <button @click="form.active = !form.active" type="button" :disabled="isEditingInstalledApp" :class="[form.active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out', {'opacity-50 cursor-not-allowed': isEditingInstalledApp}]">
                        <span :class="[form.active ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                    </button>
                </div>
                
                <fieldset class="space-y-4">
                    <legend class="text-sm font-medium">Authentication</legend>
                    <select id="formAuthType" v-model="form.authentication_type" class="input-field">
                        <option value="none">None</option>
                        <option value="lollms_sso">LoLLMs SSO</option>
                        <option value="lollms_chat_auth">LoLLMs Chat Auth</option>
                        <option value="bearer">Bearer Token</option>
                    </select>
                    <p v-if="form.authentication_type === 'lollms_chat_auth'" class="mt-1 text-xs text-gray-500 dark:text-gray-400">A temporary token will be generated by LoLLMs for each session.</p>
                    <div v-if="form.authentication_type === 'bearer'" class="relative">
                        <label for="formKey" class="sr-only">Authentication Key</label>
                        <input :type="showKey ? 'text' : 'password'" id="formKey" v-model="form.authentication_key" class="input-field pr-10" placeholder="Paste your Bearer token here">
                        <button type="button" @click="showKey = !showKey" class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                            <IconEyeOff v-if="showKey" class="w-5 h-5" />
                            <IconEye v-else class="w-5 h-5" />
                        </button>
                    </div>
                </fieldset>
                
                <div v-if="isSsoAuth" class="p-4 space-y-4 border rounded-md dark:border-gray-600">
                    <h4 class="font-medium text-gray-800 dark:text-gray-200">SSO Configuration</h4>
                    <div>
                        <label for="ssoClientId" class="block text-sm font-medium">Client ID</label>
                        <input type="text" id="ssoClientId" v-model="form.client_id" class="input-field mt-1" :class="{ 'bg-gray-100 dark:bg-gray-700': isEditMode && item.client_id }" :readonly="isEditMode && item.client_id" placeholder="e.g., my_cool_app_v1 (optional)">
                        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">A unique identifier. If blank, one will be generated. <strong class="font-semibold">Cannot be changed after creation.</strong></p>
                    </div>
                    <div>
                        <label for="ssoRedirectUri" class="block text-sm font-medium">Redirect URI</label>
                        <input type="url" id="ssoRedirectUri" v-model="form.sso_redirect_uri" class="input-field mt-1" placeholder="https://yourapp.com/lollms_auth" required>
                        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">The URL where users are sent after authentication.</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium">User Info to Share</label>
                        <div class="mt-2 space-y-2">
                            <div v-for="option in ssoInfoOptions" :key="option.id" class="flex items-center">
                                <input :id="`sso-info-${option.id}`" type="checkbox" :value="option.id" v-model="form.sso_user_infos_to_share" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                                <label :for="`sso-info-${option.id}`" class="ml-2 text-sm text-gray-700 dark:text-gray-300">{{ option.label }}</label>
                            </div>
                        </div>
                    </div>
                    <div v-if="isEditMode">
                        <label class="block text-sm font-medium">SSO Secret</label>
                         <div class="mt-1 flex items-center gap-x-3">
                            <p class="text-sm text-gray-500 dark:text-gray-400 flex-grow">A secret is required for the service to validate tokens.</p>
                            <button type="button" @click="handleGenerateSecret" class="btn btn-secondary text-sm">Generate Secret</button>
                        </div>
                    </div>
                </div>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="handleClose" type="button" class="btn btn-secondary">Cancel</button>
                <button @click="handleFormSubmit" type="button" class="btn btn-primary" :disabled="isLoading">
                    {{ isLoading ? (isEditMode ? 'Saving...' : 'Adding...') : (isEditMode ? 'Save Changes' : `Add ${itemType === 'mcp' ? 'MCP' : 'App'}`) }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>