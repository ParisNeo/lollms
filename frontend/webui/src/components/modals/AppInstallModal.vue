<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import GenericModal from '../ui/GenericModal.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const props = computed(() => uiStore.modalData('appInstall'));
const app = computed(() => props.value?.app);

const port = ref(null);
const autostart = ref(false);
const isLoading = ref(false);
const isVerifyingPort = ref(false);
const portStatus = ref('unchecked'); // unchecked, available, unavailable

watch(app, async (newApp) => {
    if (newApp) {
        port.value = null;
        portStatus.value = 'unchecked';
        autostart.value = false;
        isLoading.value = false;
        isVerifyingPort.value = true;
        try {
            const nextPort = await adminStore.fetchNextAvailablePort();
            port.value = nextPort;
            portStatus.value = 'available';
        } catch (error) {
            port.value = 9601; // Fallback
        } finally {
            isVerifyingPort.value = false;
        }
    }
});

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
    try {
        await adminStore.installZooApp({
            repository: app.value.repository,
            folder_name: app.value.folder_name,
            port: port.value,
            autostart: autostart.value
        });
        uiStore.closeModal('appInstall');
    } catch (error) {
        // Error is handled globally
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modal-name="appInstall"
        :title="app ? `Install App: ${app.name}` : 'Install App'"
        max-width-class="max-w-lg"
    >
        <template #body>
            <form v-if="app" @submit.prevent="handleInstall" class="space-y-6">
                <p class="text-sm text-gray-600 dark:text-gray-300">
                    Configure the installation settings for <span class="font-semibold text-gray-900 dark:text-white">{{ app.name }}</span>.
                </p>
                <div>
                    <label for="app-port" class="block text-sm font-medium">Port Number</label>
                    <div class="mt-1 flex gap-2">
                        <input
                            id="app-port"
                            v-model.number="port"
                            type="number"
                            min="1025"
                            max="65535"
                            required
                            class="input-field flex-grow"
                            placeholder="e.g., 9601"
                        />
                        <button @click="verifyPort" type="button" class="btn btn-secondary w-28" :disabled="isVerifyingPort">
                            <IconAnimateSpin v-if="isVerifyingPort" class="w-5 h-5" />
                            <span v-else>Verify</span>
                        </button>
                    </div>
                     <div v-if="portStatus !== 'unchecked'" class="mt-2 text-sm flex items-center gap-1.5"
                         :class="portStatus === 'available' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'">
                        <IconCheckCircle v-if="portStatus === 'available'" class="w-4 h-4" />
                        <IconXMark v-else class="w-4 h-4" />
                        <span>Port {{ port }} is {{ portStatus }}.</span>
                    </div>
                </div>
                
                <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                    <span class="flex-grow flex flex-col">
                        <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Start on System Startup</span>
                        <span class="text-sm text-gray-500 dark:text-gray-400">Automatically launch this app when the main server starts.</span>
                    </span>
                    <button @click="autostart = !autostart" type="button" :class="[autostart ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800']">
                        <span :class="[autostart ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                    </button>
                </div>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('appInstall')" type="button" class="btn btn-secondary">Cancel</button>
                <button @click="handleInstall" type="button" class="btn btn-primary" :disabled="isLoading || portStatus !== 'available'">
                    {{ isLoading ? 'Installing...' : 'Confirm & Install' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>