<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import GenericModal from '../ui/GenericModal.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue'; // IMPORTED

const uiStore = useUiStore();
const adminStore = useAdminStore();

const props = computed(() => uiStore.modalData('appConfig'));
const app = computed(() => props.value?.app);

const form = ref({
    port: null,
    autostart: false
});

const isLoading = ref(false);
const isVerifyingPort = ref(false);
const portStatus = ref('unchecked'); // unchecked, available, unavailable, same

const isAppRunning = computed(() => app.value?.status === 'running');

watch(app, (newApp) => {
    if (newApp) {
        form.value.port = newApp.port;
        form.value.autostart = newApp.autostart;
        portStatus.value = 'unchecked';
    }
}, { immediate: true });

watch(() => form.value.port, () => {
    portStatus.value = 'unchecked';
});

async function verifyPort() {
    if (!form.value.port) {
        uiStore.addNotification('Please enter a port number.', 'warning');
        return;
    }
    if (form.value.port === app.value.port) {
        portStatus.value = 'same';
        return;
    }
    isVerifyingPort.value = true;
    try {
        const availablePort = await adminStore.fetchNextAvailablePort(form.value.port);
        if (availablePort === form.value.port) {
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

async function handleUpdate() {
    if (!app.value) return;
    if (portStatus.value === 'unavailable') {
        uiStore.addNotification('The selected port is unavailable. Please choose another.', 'warning');
        return;
    }

    isLoading.value = true;
    try {
        await adminStore.updateInstalledApp(app.value.id, {
            port: form.value.port,
            autostart: form.value.autostart
        });
        uiStore.closeModal('appConfig');
    } catch (error) {
        // Error is handled globally
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modal-name="appConfig"
        :title="app ? `Configure App: ${app.name}` : 'Configure App'"
        max-width-class="max-w-lg"
    >
        <template #body>
            <form v-if="app" @submit.prevent="handleUpdate" class="space-y-6">
                <div v-if="isAppRunning" class="p-4 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300 rounded-lg text-sm">
                    This app is currently running. You must stop it before changing its configuration.
                </div>

                <fieldset :disabled="isAppRunning" class="space-y-6">
                    <div>
                        <label for="app-port" class="block text-sm font-medium">Port Number</label>
                        <div class="mt-1 flex gap-2">
                            <input
                                id="app-port"
                                v-model.number="form.port"
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
                            :class="{
                                'text-green-600 dark:text-green-400': portStatus === 'available' || portStatus === 'same',
                                'text-red-600 dark:text-red-400': portStatus === 'unavailable'
                            }">
                            <IconCheckCircle v-if="portStatus === 'available' || portStatus === 'same'" class="w-4 h-4" />
                            <IconXMark v-else class="w-4 h-4" />
                            <span v-if="portStatus === 'same'">This is the current port.</span>
                            <span v-else>Port {{ form.port }} is {{ portStatus }}.</span>
                        </div>
                    </div>
                    
                    <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                        <span class="flex-grow flex flex-col">
                            <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Start on System Startup</span>
                            <span class="text-sm text-gray-500 dark:text-gray-400">Automatically launch this app when the main server starts.</span>
                        </span>
                        <button @click="form.autostart = !form.autostart" type="button" :class="[form.autostart ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800']">
                            <span :class="[form.autostart ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>
                </fieldset>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('appConfig')" type="button" class="btn btn-secondary">Cancel</button>
                <button @click="handleUpdate" type="button" class="btn btn-primary" :disabled="isLoading || isAppRunning || portStatus === 'unavailable' || portStatus === 'unchecked'">
                    {{ isLoading ? 'Saving...' : 'Save Changes' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>
