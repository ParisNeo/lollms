<template>
  <GenericModal modalName="shareResource" :title="`Send ${resourceType}`" maxWidthClass="max-w-xl">
    <template #body>
      <div class="space-y-4">
        <div class="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border dark:border-gray-700">
            <p class="text-xs text-gray-500 uppercase font-black tracking-widest mb-1">Sending:</p>
            <p class="font-bold text-gray-900 dark:text-white">{{ resourceName }}</p>
        </div>

        <!-- Tab Switcher -->
        <div class="flex border-b dark:border-gray-800 p-1 bg-gray-50 dark:bg-gray-900/50 rounded-lg shrink-0">
            <button @click="activeTab = 'friends'" class="flex-1 py-1.5 px-2 text-[10px] font-black uppercase tracking-widest rounded-md transition-all"
                    :class="activeTab === 'friends' ? 'bg-white dark:bg-gray-800 text-blue-600 shadow-sm' : 'text-gray-400'">
                Friends
            </button>
            <button @click="activeTab = 'groups'" class="flex-1 py-1.5 px-2 text-[10px] font-black uppercase tracking-widest rounded-md transition-all"
                    :class="activeTab === 'groups' ? 'bg-white dark:bg-gray-800 text-blue-600 shadow-sm' : 'text-gray-400'">
                Groups
            </button>
        </div>

        <!-- FRIENDS TAB -->
        <div v-if="activeTab === 'friends'" class="space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <label class="block text-sm font-medium">Select a friend to receive a copy:</label>

                <!-- Individual Permission Selector -->
                <div class="flex items-center gap-2">
                    <span class="text-[10px] font-black uppercase text-gray-400">Permission:</span>
                    <select v-model="individualPermissionLevel" class="input-field-sm py-1 h-8 w-32">
                        <option value="interact">Can Edit / Version</option>
                        <option value="view">View Only</option>
                    </select>
                </div>
            </div>

            <div class="max-h-48 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
                <div v-if="isLoadingSharedUsers" class="flex justify-center items-center py-8">
                    <IconAnimateSpin class="w-6 h-6 text-blue-500 animate-spin" />
                </div>
                <template v-else>
                    <div v-for="friend in friends" :key="friend.id" 
                         @click="!isAlreadyShared(friend.username) && (selectedUsername = friend.username)"
                         class="flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-all"
                         :class="[
                            selectedUsername === friend.username ? 'bg-blue-100 dark:bg-blue-900/50 ring-1 ring-blue-500' : 'hover:bg-gray-100 dark:hover:bg-gray-700',
                            isAlreadyShared(friend.username) ? 'opacity-50 cursor-not-allowed bg-gray-50/50 dark:bg-gray-900/10' : ''
                         ]">
                        <UserAvatar :icon="friend.icon" :username="friend.username" size-class="h-8 w-8" />
                        <span class="text-sm font-medium">{{ friend.username }}</span>
                        <div v-if="isAlreadyShared(friend.username)" class="ml-auto flex items-center gap-1 text-green-600 dark:text-green-400 select-none">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" /></svg>
                            <span class="text-[9px] font-black uppercase tracking-widest">Shared</span>
                        </div>
                        <div v-else-if="selectedUsername === friend.username" class="ml-auto">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-blue-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" /></svg>
                        </div>
                    </div>
                    <div v-if="friends.length === 0" class="text-center py-4 text-gray-500 italic text-sm">
                        No friends found to share with.
                    </div>
                </template>
            </div>

            <!-- List of Users currently with access -->
            <div v-if="sharedUsersWithAccess.length > 0" class="pt-4 border-t dark:border-gray-700">
                <span class="text-[9px] font-black uppercase tracking-widest text-gray-400 block mb-2">Who has access</span>
                <div class="space-y-1.5 max-h-32 overflow-y-auto custom-scrollbar">
                    <div v-for="u in sharedUsersWithAccess" :key="u.id" class="flex items-center justify-between p-2 rounded-lg bg-gray-50 dark:bg-gray-800 border dark:border-gray-750">
                        <div class="flex items-center gap-2">
                            <UserAvatar :icon="u.icon" :username="u.username" size-class="h-7 w-7" />
                            <span class="text-xs font-semibold text-gray-700 dark:text-gray-200">{{ u.username }}</span>
                        </div>
                        <button @click.stop="handleRevokeUser(u)" class="text-[9px] font-bold text-red-500 hover:text-red-600 uppercase tracking-widest" title="Revoke access">
                            Unshare
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- GROUPS TAB -->
        <div v-if="activeTab === 'groups'" class="space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <label class="block text-sm font-medium">Select a Group to grant/revoke access:</label>

                <!-- Group Permission Selector -->
                <div class="flex items-center gap-2">
                    <span class="text-[10px] font-black uppercase text-gray-400">Permission:</span>
                    <select v-model="groupPermissionLevel" class="input-field-sm py-1 h-8 w-32">
                        <option value="interact">Can Edit / Version</option>
                        <option value="view">View Only</option>
                    </select>
                </div>
            </div>

            <div class="max-h-72 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
                <div v-for="group in socialGroups" :key="group.id" class="p-3 bg-gray-50 dark:bg-gray-800 border dark:border-gray-750 rounded-xl flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <div class="w-9 h-9 rounded-lg bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 flex items-center justify-center font-bold">
                            {{ group.displayName ? group.displayName[0] : (group.display_name ? group.display_name[0] : 'G') }}
                        </div>
                        <div class="flex flex-col">
                            <span class="text-xs font-bold text-gray-800 dark:text-gray-100">{{ group.displayName || group.display_name }}</span>
                            <span class="text-[9px] text-gray-400">{{ (group.members || []).length }} member(s)</span>
                        </div>
                    </div>
                    <div class="flex gap-2">
                        <button @click="handleShareGroup(group)" class="px-3 py-1 bg-blue-600 text-white text-xs font-semibold rounded-lg hover:bg-blue-700 transition-colors shadow-sm">
                            Share Group
                        </button>
                        <button @click="handleUnshareGroup(group)" class="px-3 py-1 bg-gray-200 dark:bg-gray-700 hover:bg-red-500 hover:text-white dark:hover:bg-red-600 text-gray-700 dark:text-gray-200 text-xs font-semibold rounded-lg transition-colors">
                            Unshare
                        </button>
                    </div>
                </div>
                <div v-if="socialGroups.length === 0" class="text-center py-8 text-gray-500 italic text-sm">
                    No groups found. Start one in the Friends > Groups tab!
                </div>
            </div>
        </div>

      </div>
    </template>
    
    <template #footer>
        <button @click="uiStore.closeModal('shareResource')" class="btn btn-secondary">Close</button>
        <button v-if="activeTab === 'friends'" @click="handleShare" class="btn btn-primary" :disabled="!selectedUsername || isSharing">
            {{ isSharing ? 'Sending...' : 'Send Copy' }}
        </button>
    </template>
  </GenericModal>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useSocialStore } from '../../stores/social';
import { useNotesStore } from '../../stores/notes';
import { useSkillsStore } from '../../stores/skills';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import { storeToRefs } from 'pinia';

const socialStore = useSocialStore();
const notesStore = useNotesStore();
const skillsStore = useSkillsStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const { friends, socialGroups } = storeToRefs(socialStore);

const modalData = computed(() => uiStore.modalData('shareResource'));
const resourceId = computed(() => modalData.value?.id);
const resourceType = computed(() => modalData.value?.type); // 'note', 'skill', or 'artefact'
const resourceName = computed(() => modalData.value?.name);
const discussionId = computed(() => modalData.value?.discussionId || discussionsStore.currentDiscussionId);

const activeTab = ref('friends'); // 'friends' | 'groups'
const selectedUsername = ref('');
const isSharing = ref(false);
const sharedUsersWithAccess = ref([]);
const isLoadingSharedUsers = ref(false);

// New local permission selection states
const individualPermissionLevel = ref('interact'); // 'interact' | 'view'
const groupPermissionLevel = ref('interact'); // 'interact' | 'view'

const isAlreadyShared = (username) => {
    return sharedUsersWithAccess.value.some(u => u.username === username);
};

async function fetchSharedUsers() {
    if (!resourceName.value || !resourceType.value) return;
    isLoadingSharedUsers.value = true;
    try {
        const response = await (await import('../../services/api')).default.get(
            `/api/discussions/shared-with-users`,
            {
                params: {
                    resource_type: resourceType.value,
                    resource_name: resourceName.value
                }
            }
        );
        sharedUsersWithAccess.value = response.data || [];
    } catch (error) {
        console.error('Failed to fetch shared users:', error);
        sharedUsersWithAccess.value = [];
    } finally {
        isLoadingSharedUsers.value = false;
    }
}

watch(() => [resourceName.value, resourceType.value], () => {
    if (resourceName.value && resourceType.value) {
        fetchSharedUsers();
    }
}, { immediate: true });

onMounted(() => {
    if (socialStore.friends.length === 0) socialStore.fetchFriends();
    if (socialStore.socialGroups.length === 0) socialStore.fetchSocialGroups();
});

async function handleShare() {
    if (!selectedUsername.value) return;

    isSharing.value = true;
    try {
        if (resourceType.value === 'note') {
            await notesStore.shareNote(resourceId.value, selectedUsername.value);
        } else if (resourceType.value === 'skill') {
            await skillsStore.shareSkill(resourceId.value, selectedUsername.value);
        } else if (resourceType.value === 'artefact') {
            await discussionsStore.shareArtefact(
                discussionId.value, 
                resourceName.value, 
                selectedUsername.value, 
                individualPermissionLevel.value
            );
        }
        selectedUsername.value = '';
        await fetchSharedUsers();
    } finally {
        isSharing.value = false;
    }
}

async function handleRevokeUser(user) {
    const confirmation = await uiStore.showConfirmation({
        title: 'Revoke Access',
        message: `Are you sure you want to revoke access to "${resourceName.value}" for ${user.username}?`,
        confirmText: 'Unshare',
        danger: true
    });

    if (confirmation.confirmed) {
        try {
            if (resourceType.value === 'artefact') {
                await discussionsStore.unshareArtefact(discussionId.value, resourceName.value, user.id);
            }
            await fetchSharedUsers();
        } catch (e) {
            console.error("Revoke failed", e);
        }
    }
}

async function handleShareGroup(group) {
    if (resourceType.value !== 'artefact') {
        uiStore.addNotification("Group sharing is currently only available for workspace documents.", "warning");
        return;
    }

    try {
        await discussionsStore.shareArtefactWithGroup(
            discussionId.value, 
            resourceName.value, 
            group.id, 
            groupPermissionLevel.value
        );
        await fetchSharedUsers();
    } catch (e) {
        console.error("Group share failed:", e);
    }
}

async function handleUnshareGroup(group) {
    const confirmation = await uiStore.showConfirmation({
        title: 'Revoke Group Access',
        message: `Revoke access to "${resourceName.value}" for all members of "${group.displayName || group.display_name}"?`,
        confirmText: 'Unshare Group',
        danger: true
    });

    if (confirmation.confirmed) {
        try {
            await discussionsStore.unshareArtefactFromGroup(discussionId.value, resourceName.value, group.id);
            await fetchSharedUsers();
        } catch (e) {
             console.error("Group unshare failed:", e);
        }
    }
}
</script>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>
