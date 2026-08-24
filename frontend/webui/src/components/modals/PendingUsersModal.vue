<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import UserAvatar from '../ui/Cards/UserAvatar.vue';

// Icons
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconClock from '../../assets/icons/IconClock.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const { allUsers, isLoadingUsers, dashboardStats } = storeToRefs(adminStore);
const isProcessingId = ref(null);
const isLoading = ref(false);

const pendingUsers = computed(() => {
    return (allUsers.value || []).filter(u => 
        u.status === 'pending_admin_validation' || 
        u.status === 'pending' || 
        (!u.is_active && u.status !== 'inactivated_by_admin' && u.status !== 'blocked_by_lollms')
    );
});

async function loadPendingUsers() {
    isLoading.value = true;
    try {
        await Promise.all([
            adminStore.fetchAllUsers({ status_filter: 'pending_admin_validation' }),
            adminStore.fetchDashboardStats()
        ]);
    } finally {
        isLoading.value = false;
    }
}

onMounted(loadPendingUsers);

watch(() => uiStore.isModalOpen('pendingUsers'), (isOpen) => {
    if (isOpen) {
        loadPendingUsers();
    }
});

async function handleApprove(user) {
    isProcessingId.value = user.id;
    try {
        await adminStore.activateUser(user.id);
        await adminStore.fetchDashboardStats();
        await adminStore.fetchAllUsers({ status_filter: 'pending_admin_validation' });
        uiStore.addNotification(`Account for '${user.username}' activated successfully.`, 'success');
    } catch (e) {
        uiStore.addNotification(`Failed to activate ${user.username}.`, 'error');
    } finally {
        isProcessingId.value = null;
    }
}

async function handleReject(user) {
    const confirmed = await uiStore.showConfirmation({
        title: `Reject & Delete Registration`,
        message: `Are you sure you want to reject and remove registration for '${user.username}'?`,
        confirmText: 'Reject & Delete',
        danger: true
    });

    if (confirmed.confirmed) {
        isProcessingId.value = user.id;
        try {
            await adminStore.deleteUser(user.id);
            await adminStore.fetchDashboardStats();
            await adminStore.fetchAllUsers({ status_filter: 'pending_admin_validation' });
            uiStore.addNotification(`Registration for '${user.username}' removed.`, 'info');
        } finally {
            isProcessingId.value = null;
        }
    }
}

async function handleApproveAll() {
    if (pendingUsers.value.length === 0) return;
    isLoading.value = true;
    try {
        for (const user of pendingUsers.value) {
            await adminStore.activateUser(user.id);
        }
        await adminStore.fetchDashboardStats();
        await adminStore.fetchAllUsers({ status_filter: 'pending_admin_validation' });
        uiStore.addNotification('All pending accounts have been approved and activated.', 'success');
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal modalName="pendingUsers" title="Pending Account Approvals" maxWidthClass="max-w-2xl">
        <template #body>
            <div class="space-y-4 p-1 min-h-[300px] flex flex-col">
                
                <!-- Top Overview Bar -->
                <div class="p-4 bg-amber-50 dark:bg-amber-950/20 rounded-2xl border border-amber-200 dark:border-amber-900/40 flex items-center justify-between gap-4">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-900/40 text-amber-600 dark:text-amber-400 flex items-center justify-center font-bold shrink-0">
                            <IconClock class="w-5 h-5" />
                        </div>
                        <div>
                            <span class="text-[10px] font-black uppercase tracking-widest text-amber-700 dark:text-amber-400 block leading-tight">Review Queue</span>
                            <span class="text-xs font-bold text-gray-800 dark:text-gray-200">
                                {{ pendingUsers.length }} User(s) Awaiting Approval
                            </span>
                        </div>
                    </div>

                    <div class="flex items-center gap-2">
                        <button @click="loadPendingUsers" class="p-2 text-gray-400 hover:text-blue-500 rounded-lg" title="Refresh">
                            <IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoading}" />
                        </button>
                        <button 
                            v-if="pendingUsers.length > 1"
                            @click="handleApproveAll" 
                            class="btn btn-primary btn-xs py-1.5 px-3 font-bold"
                            :disabled="isLoading"
                        >
                            Approve All
                        </button>
                    </div>
                </div>

                <!-- Users List Stream -->
                <div class="grow overflow-y-auto custom-scrollbar space-y-2 pr-1 max-h-[50vh]">
                    <div v-if="isLoading && pendingUsers.length === 0" class="flex flex-col items-center justify-center py-16 text-gray-400 space-y-2">
                        <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin" />
                        <span class="text-xs font-bold uppercase tracking-widest">Checking queue...</span>
                    </div>

                    <div v-else-if="pendingUsers.length === 0" class="flex flex-col items-center justify-center py-16 text-gray-400 space-y-2 text-center">
                        <IconCheckCircle class="w-12 h-12 text-emerald-500/50 mb-1" />
                        <h4 class="font-bold text-sm text-gray-700 dark:text-gray-300">Approval Queue Empty</h4>
                        <p class="text-xs max-w-xs">All accounts have been reviewed and activated.</p>
                    </div>

                    <div 
                        v-for="user in pendingUsers" 
                        :key="user.id"
                        class="p-3.5 bg-white dark:bg-gray-800 rounded-2xl border border-gray-200/80 dark:border-gray-700 flex items-center justify-between gap-4 shadow-sm hover:shadow-md transition-all"
                    >
                        <div class="flex items-center gap-3 min-w-0">
                            <UserAvatar :icon="user.icon" :username="user.username" size-class="w-10 h-10" />
                            <div class="flex flex-col min-w-0">
                                <div class="flex items-center gap-2">
                                    <span class="font-bold text-sm text-gray-900 dark:text-white truncate">{{ user.username }}</span>
                                    <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 uppercase font-black">Pending</span>
                                </div>
                                <span v-if="user.email" class="text-xs text-gray-400 truncate">{{ user.email }}</span>
                                <span class="text-[9px] font-mono text-gray-400 mt-0.5">
                                    Registered: {{ user.created_at ? new Date(user.created_at).toLocaleDateString() : 'Recent' }}
                                </span>
                            </div>
                        </div>

                        <!-- Action Buttons -->
                        <div class="flex items-center gap-2 shrink-0">
                            <button 
                                @click="handleReject(user)" 
                                :disabled="isProcessingId === user.id"
                                class="btn btn-danger-outline btn-sm flex items-center gap-1.5"
                                title="Reject & Delete Account"
                            >
                                <IconTrash class="w-3.5 h-3.5" />
                                <span>Reject</span>
                            </button>

                            <button 
                                @click="handleApprove(user)" 
                                :disabled="isProcessingId === user.id"
                                class="btn btn-primary btn-sm flex items-center gap-1.5 shadow-md"
                                title="Approve & Activate"
                            >
                                <IconAnimateSpin v-if="isProcessingId === user.id" class="w-3.5 h-3.5 animate-spin" />
                                <IconCheckCircle v-else class="w-3.5 h-3.5" />
                                <span>Activate</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end w-full">
                <button @click="uiStore.closeModal('pendingUsers')" class="btn btn-primary px-8">Close</button>
            </div>
        </template>
    </GenericModal>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>