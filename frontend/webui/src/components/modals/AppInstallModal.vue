<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import GenericModal from './GenericModal.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const props = computed(() => uiStore.modalData('appInstall'));
const app = computed(() => props.value?.app);
const installType = computed(() => props.value?.type);

const port = ref(null);
const autostart = ref(false);
const authentication_type = ref('none');
const sso_redirect_uri = ref('');

const isLoading = ref(false);
const isVerifyingPort = ref(false);
const portStatus = ref('unchecked');

watch(app, async (newApp) => {
    if (newApp) {
        port.value = null;
        portStatus.value = 'unchecked';
        autostart.value = newApp.autostart ?? false;
        authentication_type.value = newApp.authentication_type || 'none';
        sso_redirect_uri.value = newApp.sso_redirect_uri || '';
        isLoading.value = false;
        isVerifyingPort.value = true;
        try {
            const nextPort = await adminStore.fetchNextAvailablePort();
            port.value = nextPort;
            portStatus.value = 'available';
        } catch (error) {
            port.value = 9601;
        } finally {
            isVerifyingPort.value = false;
        }
    }
}, { immediate: true });

watch(port, () => {
    portStatus.value = 'unchecked';
});

async function verifyPort() {
    if (!port.value) {
        uiStore.addNotification('Please enter a port number.', 'warning');
        return;
    }
    isVerifyingPort.value = true;
    try {
        const availablePort = await adminStore.fetchNextAvailablePort(port.value);
        if (availablePort === port.value) {
            portStatus.value = 'available';
        } else {
            portStatus.value = 'unavailable';
        }
    } catch (error) {
        portStatus.value = 'unavailable';
    } finally {
        isVerifyingPort.value = false;
    }
}

async function handleInstall() {
    if (!app.value) return;
    if (portStatus.value !== 'available') {
        uiStore.addNotification('Please verify an available port before installing.', 'warning');
        return;
    }

    isLoading.value = true;
    const payload = {
        repository: app.value.repository,
        folder_name: app.value.folder_name,
        port: port.value,
        autostart: autostart.value,
        authentication_type: authentication_type.value,
        sso_redirect_uri: authentication_type.value === 'lollms_sso' ? sso_redirect_uri.value : null,
    };

    try {
        if (installType.value === 'mcps') {
            await adminStore.installZooMcp(payload);
        } else {
            await adminStore.installZooApp(payload);
        }

        if (authentication_type.value === 'lollms_sso') {
            uiStore.addNotification('SSO enabled. A server reboot is recommended after configuring SSO endpoints.', 'warning', 12000);
        }

        uiStore.closeModal('appInstall');
    } catch (error) {
        // Error handled globally
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modal-name="appInstall"
        :title="app ? `Install ${installType === 'mcps' ? 'MCP Service' : 'App'}: ${app.name}` : 'Install Item'"
        max-width-class="max-w-lg"
    >
        <template #body>
            <form v-if="app" @submit.prevent="handleInstall" class="space-y-5">
                <p class="text-xs text-gray-600 dark:text-gray-400">
                    Configure port allocation, autostart behavior, and security access for <span class="font-bold text-gray-900 dark:text-white">{{ app.name }}</span>.
                </p>

                <!-- Port Configuration -->
                <div class="space-y-1.5">
                    <label for="app-port" class="block text-xs font-bold text-gray-700 dark:text-gray-300">
                        Network Port Number
                    </label>
                    <div class="flex gap-2">
                        <input
                            id="app-port"
                            v-model.number="port"
                            type="number"
                            min="1025"
                            max="65535"
                            required
                            class="input-field grow font-mono text-sm py-2 rounded-xl"
                            placeholder="e.g., 9601"
                        />
                        <button 
                            @click="verifyPort" 
                            type="button" 
                            class="btn btn-secondary btn-sm px-4 rounded-xl shrink-0" 
                            :disabled="isVerifyingPort"
                        >
                            <IconAnimateSpin v-if="isVerifyingPort" class="w-4 h-4 animate-spin" />
                            <span v-else>Check Port</span>
                        </button>
                    </div>

                    <!-- Port Verification Banner -->
                    <div 
                        v-if="portStatus !== 'unchecked'" 
                        class="text-xs flex items-center gap-1.5 mt-1 font-medium"
                        :class="portStatus === 'available' ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'"
                    >
                        <IconCheckCircle v-if="portStatus === 'available'" class="w-4 h-4" />
                        <IconXMark v-else class="w-4 h-4" />
                        <span>Port {{ port }} is {{ portStatus === 'available' ? 'free and available' : 'already in use' }}.</span>
                    </div>
                </div>
                
                <!-- Autostart Toggle -->
                <div class="flex items-center justify-between p-3.5 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border border-gray-200/80 dark:border-gray-700/60">
                    <span class="grow flex flex-col pr-3">
                        <span class="text-xs font-bold text-gray-900 dark:text-gray-100">Launch on System Startup</span>
                        <span class="text-[11px] text-gray-500 dark:text-gray-400">Automatically boot this service when the LoLLMs server starts.</span>
                    </span>
                    <button 
                        @click="autostart = !autostart" 
                        type="button" 
                        :class="[autostart ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-700', 'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-hidden']"
                    >
                        <span :class="[autostart ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                    </button>
                </div>

                <!-- Authentication Section -->
                <div class="pt-4 border-t border-gray-100 dark:border-gray-750 space-y-3">
                    <h4 class="font-bold text-xs uppercase tracking-wider text-gray-700 dark:text-gray-300">Access & Authentication</h4>
                    <div>
                        <label for="install-auth-type" class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Auth Standard</label>
                        <select id="install-auth-type" v-model="authentication_type" class="input-field text-xs py-2 rounded-xl">
                            <option value="none">None (Open Local Access)</option>
                            <option value="bearer">Bearer Token Protection</option>
                            <option value="lollms_sso">LoLLMs SSO (Single Sign-On)</option>
                        </select>
                    </div>

                    <div v-if="authentication_type === 'lollms_sso'" class="space-y-1">
                        <label for="install-sso-redirect-uri" class="block text-xs font-medium text-gray-700 dark:text-gray-300">SSO Callback URI</label>
                        <input id="install-sso-redirect-uri" v-model="sso_redirect_uri" type="url" class="input-field text-xs py-2 rounded-xl" placeholder="e.g. http://localhost:9601/auth/callback">
                        <p class="text-[10px] text-gray-400 mt-1">Authorized redirect endpoint registered with the application.</p>
                    </div>
                </div>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-end gap-2">
                <button @click="uiStore.closeModal('appInstall')" type="button" class="btn btn-secondary btn-sm">Cancel</button>
                <button @click="handleInstall" type="button" class="btn btn-primary btn-sm font-semibold" :disabled="isLoading || portStatus !== 'available'">
                    <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-1.5 animate-spin" />
                    {{ isLoading ? 'Installing...' : 'Confirm & Install' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>