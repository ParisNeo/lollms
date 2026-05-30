<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useSocialStore } from '../../stores/social';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import UserAvatar from '../ui/Cards/UserAvatar.vue';

// Icon Imports
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconSend from '../../assets/icons/IconSend.vue';

const socialStore = useSocialStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const { socialGroups, isLoadingGroups, activeGroupDetails, isLoadingGroupDetails, groupFeedPosts, isLoadingGroupFeed, friends } = storeToRefs(socialStore);
const currentUser = computed(() => authStore.user);

const selectedGroupId = ref(null);
const isCreating = ref(false);
const isEditing = ref(false);

// Forms
const groupForm = ref({
    display_name: '',
    description: ''
});
const editForm = ref({
    display_name: '',
    description: '',
    icon: ''
});
const postContent = ref('');
const isSubmittingPost = ref(false);
const selectedFriendIdToAdd = ref('');

// Computed
const isOwner = computed(() => {
    if (!activeGroupDetails.value || !currentUser.value) return false;
    const ownerId = activeGroupDetails.value.owner?.id || activeGroupDetails.value.owner_id;
    return ownerId === currentUser.value.id;
});

const nonMemberFriends = computed(() => {
    if (!activeGroupDetails.value) return [];
    const memberIds = new Set((activeGroupDetails.value.members || []).map(m => m.id));
    return (friends.value || []).filter(f => !memberIds.has(f.id));
});

// Watch selected group to load details & feed
watch(selectedGroupId, async (newId) => {
    if (newId) {
        try {
            await socialStore.fetchSocialGroupDetails(newId);
            await socialStore.fetchSocialGroupFeed(newId);
        } catch (e) {
            selectedGroupId.value = null;
        }
    } else {
        socialStore.activeGroupDetails = null;
        socialStore.groupFeedPosts = [];
        isEditing.value = false;
    }
});

onMounted(() => {
    socialStore.fetchSocialGroups();
    socialStore.fetchFriends();
});

// Actions
function selectGroup(groupId) {
    selectedGroupId.value = groupId;
}

function startCreate() {
    isCreating.value = true;
    groupForm.value = { display_name: '', description: '' };
}

function cancelCreate() {
    isCreating.value = false;
}

async function handleCreate() {
    if (!groupForm.value.display_name.trim()) return;
    try {
        await socialStore.createSocialGroup({
            display_name: groupForm.value.display_name.trim(),
            description: groupForm.value.description.trim()
        });
        isCreating.value = false;
    } catch (e) {
        // Handled by store
    }
}

function startEdit() {
    if (!activeGroupDetails.value) return;
    editForm.value = {
        display_name: activeGroupDetails.value.displayName || activeGroupDetails.value.display_name || '',
        description: activeGroupDetails.value.description || '',
        icon: activeGroupDetails.value.icon || ''
    };
    isEditing.value = true;
}

function cancelEdit() {
    isEditing.value = false;
}

async function handleUpdate() {
    if (!activeGroupDetails.value || !editForm.value.display_name.trim()) return;
    try {
        await socialStore.updateSocialGroup(activeGroupDetails.value.id, {
            display_name: editForm.value.display_name.trim(),
            description: editForm.value.description.trim(),
            icon: editForm.value.icon.trim()
        });
        isEditing.value = false;
    } catch (e) {
        // Handled by store
    }
}

async function handleDeleteGroup() {
    if (!activeGroupDetails.value) return;
    const confirmed = await uiStore.showConfirmation({
        title: "Delete Group",
        message: `Are you sure you want to permanently delete the group "${activeGroupDetails.value.displayName || activeGroupDetails.value.display_name}"? This cannot be undone.`,
        confirmText: "Delete",
        danger: true
    });
    if (confirmed.confirmed) {
        try {
            await socialStore.deleteSocialGroup(activeGroupDetails.value.id);
            selectedGroupId.value = null;
        } catch (e) {
            // Handled by store
        }
    }
}

async function handleLeaveGroup() {
    if (!activeGroupDetails.value || !currentUser.value) return;
    const confirmed = await uiStore.showConfirmation({
        title: "Leave Group",
        message: `Are you sure you want to leave the group "${activeGroupDetails.value.displayName || activeGroupDetails.value.display_name}"?`,
        confirmText: "Leave"
    });
    if (confirmed.confirmed) {
        try {
            await socialStore.removeMemberFromSocialGroup(activeGroupDetails.value.id, currentUser.value.id);
            socialStore.socialGroups = socialStore.socialGroups.filter(g => g.id !== activeGroupDetails.value.id);
            selectedGroupId.value = null;
            uiStore.addNotification("You have left the group.", "info");
        } catch (e) {
            // Handled by store
        }
    }
}

async function handleAddMember() {
    if (!selectedFriendIdToAdd.value || !activeGroupDetails.value) return;
    try {
        await socialStore.addMemberToSocialGroup(activeGroupDetails.value.id, parseInt(selectedFriendIdToAdd.value));
        selectedFriendIdToAdd.value = '';
    } catch (e) {
        // Handled by store
    }
}

async function handleRemoveMember(memberId, memberName) {
    if (!activeGroupDetails.value) return;
    const confirmed = await uiStore.showConfirmation({
        title: "Remove Member",
        message: `Are you sure you want to remove "${memberName}" from the group?`,
        confirmText: "Remove",
        danger: true
    });
    if (confirmed.confirmed) {
        try {
            await socialStore.removeMemberFromSocialGroup(activeGroupDetails.value.id, memberId);
        } catch (e) {
            // Handled by store
        }
    }
}

async function handleCreatePost() {
    if (!postContent.value.trim() || !activeGroupDetails.value) return;
    isSubmittingPost.value = true;
    try {
        await socialStore.createPost({
            content: postContent.value.trim(),
            group_id: activeGroupDetails.value.id
        });
        postContent.value = '';
        await socialStore.fetchSocialGroupFeed(activeGroupDetails.value.id);
    } catch (e) {
        // Handled by store
    } finally {
        isSubmittingPost.value = false;
    }
}

function getInitials(name) {
    if (!name) return 'GP';
    return name.split(' ').map(p => p[0]).join('').substring(0, 2).toUpperCase();
}
</script>

<template>
    <div class="max-w-4xl mx-auto p-1 h-full flex flex-col overflow-hidden">
        <!-- --- VIEW 1: MASTER LIST & CREATE FORM --- -->
        <div v-if="!selectedGroupId" class="flex-1 flex flex-col min-h-0">
            <!-- Header Controls -->
            <div class="flex justify-between items-center mb-4 shrink-0">
                <h3 class="text-lg font-bold text-gray-900 dark:text-white">Social Groups</h3>
                <div class="flex gap-2">
                    <button @click="socialStore.fetchSocialGroups()" class="btn btn-secondary btn-sm" title="Refresh">
                        <IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingGroups}" />
                    </button>
                    <button v-if="!isCreating" @click="startCreate" class="btn btn-primary btn-sm flex items-center gap-1.5">
                        <IconPlus class="w-4 h-4" />
                        <span>Create Group</span>
                    </button>
                </div>
            </div>

            <!-- Create Form Card -->
            <div v-if="isCreating" class="bg-white dark:bg-gray-800 border dark:border-gray-700 p-5 rounded-2xl shadow-md mb-6 animate-in fade-in slide-in-from-top-2 shrink-0">
                <h4 class="font-bold text-sm mb-4">Create a New Group</h4>
                <div class="space-y-4">
                    <div>
                        <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Group Name <span class="text-red-500">*</span></label>
                        <input v-model="groupForm.display_name" type="text" class="input-field" placeholder="e.g. Science Club" required />
                    </div>
                    <div>
                        <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Description</label>
                        <textarea v-model="groupForm.description" rows="3" class="input-field resize-none" placeholder="What is this group about?"></textarea>
                    </div>
                    <div class="flex justify-end gap-2 pt-2">
                        <button type="button" @click="cancelCreate" class="btn btn-secondary btn-sm">Cancel</button>
                        <button type="button" @click="handleCreate" :disabled="!groupForm.display_name.trim()" class="btn btn-primary btn-sm">Create</button>
                    </div>
                </div>
            </div>

            <!-- Grid of Groups -->
            <div class="flex-1 overflow-y-auto custom-scrollbar">
                <div v-if="isLoadingGroups" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div v-for="i in 6" :key="i" class="h-28 bg-gray-100 dark:bg-gray-800 rounded-2xl animate-pulse"></div>
                </div>
                <div v-else-if="socialGroups.length === 0" class="text-center py-16 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border-2 border-dashed dark:border-gray-700">
                    <p class="text-gray-500 dark:text-gray-400 font-medium">No joined groups yet.</p>
                    <p class="text-xs text-gray-400 mt-1">Click "Create Group" to start a community space.</p>
                </div>
                <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div v-for="g in socialGroups" :key="g.id" @click="selectGroup(g.id)" 
                         class="p-4 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-2xl shadow-sm hover:shadow-md hover:border-blue-500/30 dark:hover:border-blue-500/30 cursor-pointer transition-all flex items-start gap-4 group">
                        
                        <!-- Group Icon / Initials -->
                        <div class="w-12 h-12 rounded-xl overflow-hidden bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 border dark:border-gray-700 flex items-center justify-center font-bold shrink-0">
                            <img v-if="g.icon" :src="g.icon" class="w-full h-full object-cover" />
                            <span v-else>{{ getInitials(g.displayName || g.display_name) }}</span>
                        </div>

                        <div class="min-w-0 flex-1">
                            <h4 class="font-bold text-sm text-gray-900 dark:text-gray-100 truncate group-hover:text-blue-500 transition-colors">
                                {{ g.displayName || g.display_name }}
                            </h4>
                            <p class="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2 min-h-[2rem]">
                                {{ g.description || 'No description provided.' }}
                            </p>
                            <div class="flex items-center gap-2 mt-2 text-[10px] font-black uppercase tracking-widest text-gray-400">
                                <span>{{ (g.members || []).length }} members</span>
                                <span v-if="g.owner_id === currentUser?.id" class="text-emerald-500">owner</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- --- VIEW 2: GROUP DETAILS, MEMBERS & FEED --- -->
        <div v-else class="flex-1 flex flex-col min-h-0 overflow-hidden">
            <!-- Details Loader -->
            <div v-if="isLoadingGroupDetails" class="grow flex flex-col items-center justify-center">
                <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin mb-3" />
                <p class="text-xs text-gray-500">Loading details...</p>
            </div>

            <div v-else-if="activeGroupDetails" class="flex-1 flex flex-col lg:flex-row min-h-0 gap-6 overflow-hidden">
                <!-- Left Section: Details & Management Panel -->
                <div class="w-full lg:w-80 shrink-0 flex flex-col max-h-full overflow-y-auto custom-scrollbar bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-2xl p-5 space-y-6">
                    <button @click="selectedGroupId = null" class="flex items-center gap-2 text-xs font-black uppercase tracking-widest text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors">
                        <IconArrowLeft class="w-4 h-4" />
                        <span>All Groups</span>
                    </button>

                    <!-- Group Title Info -->
                    <div class="flex items-center gap-4">
                        <div class="w-14 h-14 rounded-xl overflow-hidden bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 border dark:border-gray-700 flex items-center justify-center font-bold text-lg shrink-0">
                            <img v-if="activeGroupDetails.icon" :src="activeGroupDetails.icon" class="w-full h-full object-cover" />
                            <span v-else>{{ getInitials(activeGroupDetails.displayName || activeGroupDetails.display_name) }}</span>
                        </div>
                        <div class="min-w-0 flex-1">
                            <h3 class="font-bold text-base text-gray-900 dark:text-white truncate">
                                {{ activeGroupDetails.displayName || activeGroupDetails.display_name }}
                            </h3>
                            <p class="text-xs text-gray-400 mt-1">Created by {{ activeGroupDetails.owner?.username || 'System' }}</p>
                        </div>
                    </div>

                    <!-- Actions -->
                    <div class="flex flex-col gap-2 pt-2 border-t dark:border-gray-700">
                        <template v-if="isOwner">
                            <button v-if="!isEditing" @click="startEdit" class="btn btn-secondary btn-sm justify-center flex items-center gap-2">
                                <IconPencil class="w-4 h-4" />
                                <span>Edit Settings</span>
                            </button>
                            <button @click="handleDeleteGroup" class="btn btn-danger btn-sm justify-center flex items-center gap-2">
                                <IconTrash class="w-4 h-4" />
                                <span>Delete Group</span>
                            </button>
                        </template>
                        <button v-else @click="handleLeaveGroup" class="btn btn-danger btn-sm justify-center flex items-center gap-2">
                            <IconTrash class="w-4 h-4" />
                            <span>Leave Group</span>
                        </button>
                    </div>

                    <!-- Edit Settings Form -->
                    <div v-if="isEditing" class="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-xl border dark:border-gray-700 space-y-4 animate-in fade-in">
                        <h4 class="text-xs font-black uppercase text-blue-500">Edit Settings</h4>
                        <div class="space-y-3">
                            <div>
                                <label class="text-[10px] font-black uppercase text-gray-400">Name</label>
                                <input v-model="editForm.display_name" type="text" class="input-field !py-1 text-xs" required />
                            </div>
                            <div>
                                <label class="text-[10px] font-black uppercase text-gray-400">Description</label>
                                <textarea v-model="editForm.description" rows="2" class="input-field !py-1 text-xs resize-none"></textarea>
                            </div>
                            <div>
                                <label class="text-[10px] font-black uppercase text-gray-400">Icon URL</label>
                                <input v-model="editForm.icon" type="text" class="input-field !py-1 text-xs" placeholder="https://..." />
                            </div>
                            <div class="flex justify-end gap-2 pt-2 border-t dark:border-gray-700">
                                <button type="button" @click="cancelEdit" class="btn btn-secondary btn-sm">Cancel</button>
                                <button type="button" @click="handleUpdate" :disabled="!editForm.display_name.trim()" class="btn btn-primary btn-sm">Save</button>
                            </div>
                        </div>
                    </div>

                    <div v-else class="text-xs text-gray-600 dark:text-gray-400 leading-relaxed italic">
                        "{{ activeGroupDetails.description || 'No description provided.' }}"
                    </div>

                    <!-- Members Section -->
                    <div class="space-y-4 pt-4 border-t dark:border-gray-700">
                        <div class="flex items-center justify-between">
                            <h4 class="text-xs font-black uppercase text-gray-400 tracking-wider">Members ({{ (activeGroupDetails.members || []).length }})</h4>
                        </div>

                        <!-- Add Member Section (If Owner) -->
                        <div v-if="isOwner" class="space-y-2 bg-gray-50 dark:bg-gray-900/40 p-3 rounded-xl border dark:border-gray-750">
                            <span class="text-[9px] font-black uppercase text-blue-500">Add Friend</span>
                            <div class="flex gap-2">
                                <select v-model="selectedFriendIdToAdd" class="input-field !py-1 text-xs grow" :disabled="nonMemberFriends.length === 0">
                                    <option value="" disabled>{{ nonMemberFriends.length === 0 ? 'No friends to add' : 'Select Friend...' }}</option>
                                    <option v-for="f in nonMemberFriends" :key="f.id" :value="f.id">{{ f.name }}</option>
                                </select>
                                <button @click="handleAddMember" class="btn btn-primary btn-sm" :disabled="!selectedFriendIdToAdd"><IconPlus class="w-4 h-4"/></button>
                            </div>
                        </div>

                        <!-- Members list -->
                        <div class="space-y-2">
                            <div v-for="member in activeGroupDetails.members" :key="member.id" 
                                 class="flex items-center justify-between p-2 rounded-lg bg-gray-50/50 dark:bg-gray-900/20 border dark:border-gray-800">
                                <div class="flex items-center gap-2 min-w-0">
                                    <UserAvatar :icon="member.icon" :username="member.username" size-class="w-8 h-8" />
                                    <span class="text-xs font-bold text-gray-800 dark:text-gray-200 truncate">{{ member.username }}</span>
                                    <span v-if="(activeGroupDetails.owner?.id || activeGroupDetails.owner_id) === member.id" class="text-[9px] text-emerald-500 bg-emerald-50 dark:bg-emerald-950 px-1 rounded border border-emerald-200 shrink-0 select-none">owner</span>
                                </div>

                                <button v-if="isOwner && member.id !== currentUser?.id" 
                                        @click="handleRemoveMember(member.id, member.username)"
                                        class="p-1 rounded text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/20 shrink-0" 
                                        title="Remove Member">
                                    <IconTrash class="w-3.5 h-3.5" />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right Section: Group Feed -->
                <div class="flex-1 flex flex-col min-h-0 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-2xl p-5">
                    <div class="shrink-0 pb-4 border-b dark:border-gray-700">
                        <h4 class="font-black text-xs uppercase tracking-widest text-gray-400">Group Feed</h4>
                        <p class="text-xs text-gray-500 mt-1">Post updates and discuss topics with group members.</p>
                    </div>

                    <!-- Create Post Box -->
                    <div class="shrink-0 p-4 bg-gray-50 dark:bg-gray-900/40 rounded-2xl border dark:border-gray-750 my-4 space-y-3">
                        <textarea v-model="postContent" rows="2" class="w-full text-xs input-field resize-none bg-white dark:bg-gray-800" placeholder="Post a message to this group..."></textarea>
                        <div class="flex justify-end">
                            <button @click="handleCreatePost" :disabled="isSubmittingPost || !postContent.trim()" class="btn btn-primary btn-xs py-1.5 px-4 flex items-center gap-2 shadow-md">
                                <IconAnimateSpin v-if="isSubmittingPost" class="w-3.5 h-3.5 animate-spin" />
                                <IconSend v-else class="w-3.5 h-3.5" />
                                <span>Post</span>
                            </button>
                        </div>
                    </div>

                    <!-- Feed List -->
                    <div class="flex-1 overflow-y-auto custom-scrollbar space-y-4">
                        <div v-if="isLoadingGroupFeed" class="text-center py-10">
                            <IconAnimateSpin class="w-6 h-6 text-blue-500 animate-spin mx-auto" />
                        </div>
                        <div v-else-if="groupFeedPosts.length === 0" class="text-center py-12 text-gray-400 italic text-xs">
                            No posts in this group yet. Write the first one!
                        </div>
                        <div v-else class="space-y-4">
                            <div v-for="post in groupFeedPosts" :key="post.id" class="p-4 rounded-2xl border dark:border-gray-700 bg-white dark:bg-gray-800 hover:shadow-sm transition-all space-y-3">
                                <div class="flex items-center justify-between">
                                    <div class="flex items-center gap-2.5">
                                        <UserAvatar :icon="post.author.icon" :username="post.author.username" size-class="w-9 h-9" />
                                        <div class="flex flex-col">
                                            <span class="font-bold text-xs text-gray-800 dark:text-gray-200">{{ post.author.username }}</span>
                                            <span class="text-[9px] text-gray-400">{{ new Date(post.created_at).toLocaleString() }}</span>
                                        </div>
                                    </div>
                                    <!-- Delete option if owner of group, or author of post, or admin -->
                                    <button v-if="isOwner || post.author.id === currentUser?.id || currentUser?.is_admin" 
                                            @click="socialStore.deletePost(post.id).then(() => socialStore.fetchSocialGroupFeed(activeGroupDetails.id))" 
                                            class="text-gray-400 hover:text-red-500 p-1" title="Delete Post">
                                        <IconTrash class="w-4 h-4"/>
                                    </button>
                                </div>
                                <div class="text-sm text-gray-700 dark:text-gray-300 font-serif leading-relaxed whitespace-pre-wrap">
                                    {{ post.content }}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-200 dark:bg-gray-700 rounded-full; }
.menu-item { @apply flex items-center w-full px-4 py-2 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-left; }
.menu-divider { @apply my-1 border-t border-gray-100 dark:border-gray-700; }
</style>
