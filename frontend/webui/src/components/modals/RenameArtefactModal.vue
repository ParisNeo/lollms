<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from './GenericModal.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const modalData = computed(() => uiStore.modalData('renameArtefact'));
const discussionId = computed(() => modalData.value?.discussionId);
const artefact = computed(() => modalData.value?.artefact);

const newTitle = ref('');
const selectedType = ref('');
const inputRef = ref(null);
const isLoading = ref(false);

const typeOptions = [
    { value: 'document', label: 'Reference Document' },
    { value: 'code', label: 'Code Snippet' },
    { value: 'note', label: 'Research Note' },
    { value: 'skill', label: 'AI Capability' },
];

watch(() => uiStore.isModalOpen('renameArtefact'), (isOpen) => {
    if (isOpen && artefact.value) {
        newTitle.value = artefact.value.title;
        // Default type from the latest version
        selectedType.value = artefact.value.versions[0]?.artefact_type || 'document';
        nextTick(() => inputRef.value?.focus());
    }
});

async function handleRename() {
    if (!newTitle.value.trim() || !discussionId.value) return;
    
    isLoading.value = true;
    try {
        await discussionsStore.renameArtefact({
            discussionId: discussionId.value,
            oldTitle: artefact.value.title,
            newTitle: newTitle.value.trim(),
            newType: selectedType.value
        });
        uiStore.closeModal('renameArtefact');
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
  <GenericModal modalName="renameArtefact" title="Rename Artefact" maxWidthClass="max-w-md">
    <template #body>
      <div class="space-y-4">
        <div>
          <label class="label">New Title</label>
          <div class="relative mt-1">
            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <IconFileText class="h-4 w-4 text-gray-400" />
            </div>
            <input
              ref="inputRef"
              v-model="newTitle"
              type="text"
              class="input-field pl-10"
              placeholder="e.g. documentation.md"
              required
              @keyup.enter="handleRename"
            />
          </div>
          <p class="text-[10px] text-gray-500 mt-1 uppercase font-bold">Extension change will auto-update type unless manually selected below.</p>
        </div>

        <div>
          <label class="label">Document Category</label>
          <select v-model="selectedType" class="input-field mt-1">
            <option v-for="opt in typeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </div>
      </div>
    </template>
    <template #footer>
      <button @click="uiStore.closeModal('renameArtefact')" class="btn btn-secondary">Cancel</button>
      <button @click="handleRename" class="btn btn-primary" :disabled="isLoading || !newTitle.trim()">
        {{ isLoading ? 'Processing...' : 'Apply Changes' }}
      </button>
    </template>
  </GenericModal>
</template>