<script setup>
import { ref, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';

const uiStore = useUiStore();

const keyData = computed(() => uiStore.modalProps.newApiKey?.keyData);

const hasCopied = ref(false);

function handleCopy() {
    if (keyData.value?.full_key) {
        uiStore.copyToClipboard(keyData.value.full_key, 'API Key copied to clipboard!');
        hasCopied.value = true;
        setTimeout(() => {
            hasCopied.value = false;
        }, 2500);
    }
}

function closeModal() {
    uiStore.closeModal('newApiKey');
}
</script>

<template>
    <GenericModal 
        v-if="keyData" 
        title="API Key Created Successfully" 
        modal-name="newApiKey"
        :allow-overlay-close="false"
    >
        <template #body>
            <div class="space-y-6">
                <div class="bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-400 p-4 rounded-md">
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <IconInfo class="h-5 w-5 text-yellow-400" />
                        </div>
                        <div class="ml-3">
                            <p class="text-sm text-yellow-700 dark:text-yellow-200">
                                Please copy your new API key now. You will not be able to see it again!
                            </p>
                        </div>
                    </div>
                </div>

                <div>
                    <label for="apiKey" class="block text-sm font-medium text-gray-700 dark:text-gray-300">New API Key for "{{ keyData.alias }}"</label>
                    <div class="mt-1 relative rounded-md shadow-sm">
                        <input
                            type="text"
                            id="apiKey"
                            :value="keyData.full_key"
                            readonly
                            class="input-field !pr-12 selection:bg-blue-200 dark:selection:bg-blue-800 font-mono text-sm"
                        />
                        <div class="absolute inset-y-0 right-0 flex items-center pr-3">
                            <button @click="handleCopy" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200" title="Copy to clipboard">
                                <IconCopy class="h-5 w-5" />
                            </button>
                        </div>
                    </div>
                    <p v-if="hasCopied" class="mt-2 text-sm text-green-600 dark:text-green-400 transition-opacity duration-300">
                        Copied!
                    </p>
                </div>
            </div>
        </template>
        
        <template #footer>
            <button @click="closeModal" class="btn btn-primary">
                I have copied my key
            </button>
        </template>
    </GenericModal>
</template>