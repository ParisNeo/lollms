<script setup>
import { ref, computed, onMounted } from 'vue';
import { useSocialStore } from '../../stores/social';
import { useNotesStore } from '../../stores/notes';
import { useSkillsStore } from '../../stores/skills';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import { storeToRefs } from 'pinia';

const socialStore = useSocialStore();
const notesStore = useNotesStore();
const skillsStore = useSkillsStore();
const uiStore = useUiStore();

const { friends } = storeToRefs(socialStore);

const modalData = computed(() => uiStore.modalData('shareResource'));
const resourceId = computed(() => modalData.value?.id);
const resourceType = computed(() => modalData.value?.type); // 'note' or 'skill'
const resourceName = computed(() => modalData.value?.name);

const selectedUsername = ref('');
const isSharing = ref(false);

onMounted(() => {
    if (socialStore.friends.length === 0) socialStore.fetchFriends();
});

async function handleShare() {
    if (!selectedUsername.value) return;
    
    isSharing.value = true;
    try {
        if (resourceType.value === 'note') {
            await notesStore.shareNote(resourceId.value, selectedUsername.value);
        } else if (resourceType.value === 'skill') {
            await skillsStore.shareSkill(resourceId.value, selectedUsername.value);
        }
        uiStore.closeModal('shareResource');
    } finally {
        isSharing.value = false;
    }
}
</script>

<template>
  <GenericModal modalName="shareResource" :title="`Send ${resourceType}`" maxWidthClass="max-w-md">
    <template #body>
      <div class="space-y-4">
        <div class="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border dark:border-gray-700">
            <p class="text-xs text-gray-500 uppercase font-black tracking-widest mb-1">Sending:</p>
            <p class="font-bold text-gray-900 dark:text-white">{{ resourceName }}</p>
        </div>

        <label class="block text-sm font-medium">Select a friend to receive a copy:</label>
        
        <div class="max-h-60 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
            <div v-for="friend in friends" :key="friend.id" 
                 @click="selectedUsername = friend.username"
                 class="flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-colors"
                 :class="selectedUsername === friend.username ? 'bg-blue-100 dark:bg-blue-900/50 ring-1 ring-blue-500' : 'hover:bg-gray-100 dark:hover:bg-gray-700'">
                <UserAvatar :icon="friend.icon" :username="friend.username" size-class="h-8 w-8" />
                <span class="text-sm font-medium">{{ friend.username }}</span>
                <div v-if="selectedUsername === friend.username" class="ml-auto">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-blue-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" /></svg>
                </div>
            </div>
            <div v-if="friends.length === 0" class="text-center py-4 text-gray-500 italic text-sm">
                No friends found to share with.
            </div>
        </div>
      </div>
    </template>
    <template #footer>
        <button @click="uiStore.closeModal('shareResource')" class="btn btn-secondary">Cancel</button>
        <button @click="handleShare" class="btn btn-primary" :disabled="!selectedUsername || isSharing">
            {{ isSharing ? 'Sending...' : 'Send Copy' }}
        </button>
    </template>
  </GenericModal>
</template>