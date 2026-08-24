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
        // Error handled globally
    } finally {
        isSaving.value = false;
    }
}
</script>

<template>
    <GenericModal modal-name="appEnvConfig" :title="`.env Configuration: ${app?.name || ''}`" max-width-class="max-w-3xl">
        <template #body>
            <p class="text-xs text-gray-600 dark:text-gray-400 mb-3">
                Configure environment variables directly. Updates will take effect on the next application restart.
            </p>
            <div class="relative bg-gray-950 text-gray-100 font-mono text-xs p-4 rounded-2xl border border-gray-800 h-80 overflow-hidden shadow-inner">
                <div v-if="isLoading" class="absolute inset-0 bg-gray-950/80 backdrop-blur-xs flex items-center justify-center z-10">
                    <IconAnimateSpin class="w-6 h-6 text-primary animate-spin" />
                </div>
                <textarea 
                    v-model="envContent"
                    class="w-full h-full bg-transparent border-none focus:ring-0 focus:outline-hidden resize-none p-0 text-xs font-mono leading-relaxed"
                    placeholder="# Loading environment variables..."
                    spellcheck="false"
                ></textarea>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end gap-2">
                <button @click="uiStore.closeModal('appEnvConfig')" type="button" class="btn btn-secondary btn-sm">Cancel</button>
                <button @click="handleSave" type="button" class="btn btn-primary btn-sm font-semibold" :disabled="isLoading || isSaving">
                    <IconAnimateSpin v-if="isSaving" class="w-4 h-4 mr-1.5 animate-spin" />
                    {{ isSaving ? 'Saving...' : 'Save .env' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>