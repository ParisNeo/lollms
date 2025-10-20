<script setup>
import { computed, ref, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import GenericModal from './GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const props = computed(() => uiStore.modalData('appEnvConfig'));
const app = computed(() => props.value?.app);

const envContent = ref('');
const isLoading = ref(false);
const isSaving = ref(false);

async function fetchEnv() {
    if (!app.value || isLoading.value) return;
    isLoading.value = true;
    try {
        envContent.value = await adminStore.fetchAppEnv(app.value.id);
    } catch (error) {
        envContent.value = `# Failed to load .env file:\n# ${error.message}`;
    } finally {
        isLoading.value = false;
    }
}

watch(
    () => uiStore.isModalOpen('appEnvConfig'),
    (isOpen) => {
        if (isOpen && app.value) {
            fetchEnv();
        } else {
            envContent.value = '';
        }
    },
    { immediate: true }
);

async function handleSave() {
    if (!app.value) return;
    isSaving.value = true;
    try {
        await adminStore.updateAppEnv(app.value.id, envContent.value);
        uiStore.closeModal('appEnvConfig');
    } catch (error) {
        // Error is handled globally by api client
    } finally {
        isSaving.value = false;
    }
}
</script>

<template>
    <GenericModal modalName="appEnvConfig" :title="`.env Configuration: ${app?.name || ''}`" maxWidthClass="max-w-4xl">
        <template #body>
            <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Edit the environment variables for this application. Changes will be applied on the next start of the application.
            </p>
            <div class="relative bg-gray-900 text-white font-mono text-sm p-4 rounded-md h-96">
                <div v-if="isLoading" class="absolute inset-0 bg-gray-900/80 flex items-center justify-center">
                    <IconAnimateSpin class="w-8 h-8" />
                </div>
                <textarea 
                    v-model="envContent"
                    class="w-full h-full bg-transparent border-none focus:ring-0 resize-none p-0 text-sm"
                    placeholder="Loading .env content..."
                    spellcheck="false"
                ></textarea>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('appEnvConfig')" type="button" class="btn btn-secondary">Cancel</button>
                <button @click="handleSave" type="button" class="btn btn-primary" :disabled="isLoading || isSaving">
                    <IconAnimateSpin v-if="isSaving" class="w-5 h-5 mr-2" />
                    {{ isSaving ? 'Saving...' : 'Save Changes' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>