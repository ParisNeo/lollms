<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from '../ui/GenericModal.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const props = computed(() => uiStore.modalData('contextToArtefact'));
const discussionId = computed(() => props.value?.discussionId);
const artefacts = computed(() => props.value?.artefacts || []);

const mode = ref('new'); // 'new' or 'update'
const newTitle = ref('');
const selectedTitleToUpdate = ref(null);
const isLoading = ref(false);

watch(props, (newProps) => {
    if (newProps && uiStore.isModalOpen('contextToArtefact')) {
        mode.value = 'new';
        newTitle.value = '';
        selectedTitleToUpdate.value = null;
    }
}, { immediate: true });

const titleToSubmit = computed(() => {
    return mode.value === 'new' ? newTitle.value.trim() : selectedTitleToUpdate.value;
});

async function handleSubmit() {
    if (!titleToSubmit.value) {
        uiStore.addNotification('Please provide a name for the new artefact or select one to update.', 'warning');
        return;
    }
    isLoading.value = true;
    try {
        await discussionsStore.exportContextAsArtefact({
            discussionId: discussionId.value,
            title: titleToSubmit.value,
        });
        uiStore.closeModal('contextToArtefact');
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modal-name="contextToArtefact"
        title="Save Context as Artefact"
        max-width-class="max-w-lg"
    >
        <template #body>
            <form @submit.prevent="handleSubmit" class="space-y-6">
                <p class="text-sm text-gray-600 dark:text-gray-300">
                    This will save the current content of the "Discussion Data Zone" as a new artefact. You can create a new artefact or update an existing one, which will create a new version.
                </p>

                <div class="space-y-2">
                    <div class="flex items-center gap-4">
                        <label class="flex items-center">
                            <input type="radio" v-model="mode" value="new" class="radio-input">
                            <span class="ml-2">Create New Artefact</span>
                        </label>
                        <label class="flex items-center">
                            <input type="radio" v-model="mode" value="update" class="radio-input" :disabled="artefacts.length === 0">
                            <span class="ml-2" :class="{'opacity-50': artefacts.length === 0}">Update Existing</span>
                        </label>
                    </div>
                </div>

                <div v-if="mode === 'new'">
                    <label for="new-artefact-title" class="label">New Artefact Name</label>
                    <input id="new-artefact-title" v-model="newTitle" type="text" class="input-field mt-1" required>
                </div>

                <div v-if="mode === 'update'">
                     <label for="update-artefact-title" class="label">Select Artefact to Update</label>
                    <select id="update-artefact-title" v-model="selectedTitleToUpdate" class="input-field mt-1" required>
                        <option :value="null" disabled>Select an artefact...</option>
                        <option v-for="artefact in artefacts" :key="artefact.title" :value="artefact.title">
                            {{ artefact.title }}
                        </option>
                    </select>
                </div>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('contextToArtefact')" type="button" class="btn btn-secondary">Cancel</button>
                <button @click="handleSubmit" type="button" class="btn btn-primary" :disabled="isLoading || !titleToSubmit">
                    {{ isLoading ? 'Saving...' : 'Save Artefact' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>