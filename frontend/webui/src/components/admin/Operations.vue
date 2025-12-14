<script setup>
import { ref, computed, onMounted } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import { useSocialStore } from '../../stores/social';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import IconArchiveBox from '../../assets/icons/IconArchiveBox.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconSend from '../../assets/icons/IconSend.vue';
import IconChatBubbleLeftRight from '../../assets/icons/IconChatBubbleLeftRight.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const socialStore = useSocialStore();

const connectedUsers = computed(() => adminStore.connectedUsers);
const allUsers = computed(() => adminStore.allUsers);
const isLoadingConnected = computed(() => adminStore.isLoadingConnectedUsers);

// Renamed local ref to avoid any naming conflict with the store action (though scope rules should allow it)
const broadcastMsg = ref('');
const isBroadcasting = ref(false);

const liveUsersList = computed(() => {
    // Merge connected IDs with full user details
    if (!allUsers.value.length) return connectedUsers.value;
    return connectedUsers.value.map(cu => {
        const full = allUsers.value.find(u => u.id === cu.id);
        return full || cu;
    });
});

onMounted(() => {
    adminStore.fetchConnectedUsers();
    adminStore.fetchAllUsers();
});

async function handleBackup() {
    const { confirmed, value } = await uiStore.showConfirmation({
        title: 'Secure System Backup',
        message: 'Enter a MANDATORY password to encrypt the backup.',
        confirmText: 'Backup',
        inputType: 'password',
        inputPlaceholder: 'Encryption Password'
    });

    if (confirmed) {
        if (!value) {
            uiStore.addNotification('Password is required for backup.', 'error');
            return;
        }
        try {
            await adminStore.createBackup(value);
            uiStore.addNotification('Secure backup task started.', 'info');
        } catch (e) {
            uiStore.addNotification('Failed to start backup.', 'error');
        }
    }
}

async function handlePurge() {
  const confirmed = await uiStore.showConfirmation({
    title: 'Purge Temporary Files?',
    message: 'Delete temporary files older than 24 hours from all user directories?',
    confirmText: 'Purge',
    cancelText: 'Cancel'
  });
  if (confirmed && confirmed.confirmed) {
    adminStore.purgeUnusedUploads();
    uiStore.addNotification('Purge task started.', 'info');
  }
}

async function handleBroadcast() {
    if (!broadcastMsg.value.trim()) return;
    isBroadcasting.value = true;
    try {
        await adminStore.broadcastMessage(broadcastMsg.value);
        uiStore.addNotification('Broadcast sent successfully.', 'success');
        broadcastMsg.value = '';
    } finally {
        isBroadcasting.value = false;
    }
}

function dmUser(user) {
    socialStore.openConversation({
        id: user.id,
        username: user.username,
        icon: user.icon
    });
    uiStore.setMainView('chat'); // Ensure chat view is active if redirecting
}
</script>

<template>
    <div class="space-y-8">
        <h3 class="text-xl font-bold text-gray-900 dark:text-white">System Operations</h3>

        <!-- Maintenance Actions -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Backup -->
            <div class="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
                <div class="flex items-center gap-4 mb-4">
                    <div class="p-3 bg-blue-100 dark:bg-blue-900/30 text-blue-600 rounded-full">
                        <IconArchiveBox class="w-6 h-6"/>
                    </div>
                    <div>
                        <h4 class="font-bold text-lg">System Backup</h4>
                        <p class="text-sm text-gray-500">Create an encrypted full backup.</p>
                    </div>
                </div>
                <button @click="handleBackup" class="btn btn-primary w-full">Start Backup</button>
            </div>

            <!-- Purge -->
            <div class="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
                <div class="flex items-center gap-4 mb-4">
                    <div class="p-3 bg-red-100 dark:bg-red-900/30 text-red-600 rounded-full">
                        <IconTrash class="w-6 h-6"/>
                    </div>
                    <div>
                        <h4 class="font-bold text-lg">Cleanup</h4>
                        <p class="text-sm text-gray-500">Purge old temporary files.</p>
                    </div>
                </div>
                <button @click="handlePurge" class="btn btn-danger-outline w-full">Purge Temp Files</button>
            </div>
        </div>

        <!-- Broadcast -->
        <div class="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
            <h4 class="font-bold text-lg mb-4 flex items-center gap-2">
                <IconSend class="w-5 h-5 text-gray-500"/> Broadcast Message
            </h4>
            <div class="flex gap-2">
                <input 
                    v-model="broadcastMsg" 
                    type="text" 
                    class="input-field flex-grow" 
                    placeholder="Type a message to send to all connected users..."
                    @keyup.enter="handleBroadcast"
                >
                <button 
                    @click="handleBroadcast" 
                    :disabled="!broadcastMsg || isBroadcasting" 
                    class="btn btn-primary px-6"
                >
                    Send
                </button>
            </div>
        </div>

        <!-- Connected Users -->
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div class="p-4 bg-gray-50 dark:bg-gray-700/50 border-b dark:border-gray-700 flex justify-between items-center">
                <h4 class="font-bold text-lg">Live Users</h4>
                <div class="flex items-center gap-2">
                    <span class="text-sm font-medium px-2 py-1 bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 rounded-full">
                        {{ liveUsersList.length }} Online
                    </span>
                    <button @click="adminStore.fetchConnectedUsers" class="btn-icon p-1">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" :class="{'animate-spin': isLoadingConnected}" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd" /></svg>
                    </button>
                </div>
            </div>
            
            <div class="max-h-96 overflow-y-auto p-4">
                <div v-if="liveUsersList.length === 0" class="text-center text-gray-500 py-4">No users currently connected.</div>
                <div v-else class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                    <div v-for="user in liveUsersList" :key="user.id" class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/30 rounded-lg border border-gray-200 dark:border-gray-700">
                        <div class="flex items-center gap-3 overflow-hidden">
                            <UserAvatar :icon="user.icon" :username="user.username" size-class="h-8 w-8" />
                            <div class="truncate">
                                <p class="font-medium text-sm truncate" :title="user.username">{{ user.username }}</p>
                                <p class="text-xs text-gray-500">ID: {{ user.id }}</p>
                            </div>
                        </div>
                        <button @click="dmUser(user)" class="btn btn-secondary btn-xs" title="Send Direct Message">
                            <IconChatBubbleLeftRight class="w-4 h-4"/>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
