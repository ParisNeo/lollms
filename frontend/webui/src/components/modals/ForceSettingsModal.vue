<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import GenericModal from './GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import { useDataStore } from '../../stores/data';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();
const dataStore = useDataStore();

const { allUsers, isLoadingUsers } = storeToRefs(adminStore);
const { availableLLMModelsGrouped, isLoadingLollmsModels } = storeToRefs(dataStore);
const props = computed(() => uiStore.modalData('forceSettings'));
const onSettingsApplied = computed(() => props.value?.onSettingsApplied);

const selectedModelProfile = ref('');
const selectedUserIds = ref([]);
const userSearchQuery = ref('');
const isLoading = ref(false);

const selectedProfileDetails = computed(() => {
    if (!selectedModelProfile.value) return null;
    for (const group of availableLLMModelsGrouped.value) {
        const item = group.items.find(m => m.id === selectedModelProfile.value);
        if (item) return item;
    }
    return null;
});

const filteredUsers = computed(() => {
    if (!userSearchQuery.value) {
        return allUsers.value;
    }
    const lowerQuery = userSearchQuery.value.toLowerCase();
    return allUsers.value.filter(u => u.username.toLowerCase().includes(lowerQuery));
});

const areAllUsersSelected = computed({
    get() {
        return filteredUsers.value.length > 0 && selectedUserIds.value.length === filteredUsers.value.length;
    },
    set(value) {
        if (value) {
            selectedUserIds.value = filteredUsers.value.map(u => u.id);
        } else {
            selectedUserIds.value = [];
        }
    }
});

watch(userSearchQuery, () => {
    selectedUserIds.value = [];
});

async function handleSubmit() {
    if (!selectedModelProfile.value) {
        uiStore.addNotification('Please select a model profile to apply.', 'warning');
        return;
    }
    if (selectedUserIds.value.length === 0) {
        uiStore.addNotification('Please select at least one user.', 'warning');
        return;
    }

    isLoading.value = true;
    try {
        const prof = selectedProfileDetails.value;
        const payload = { 
            user_ids: selectedUserIds.value,
            lollms_model_name: selectedModelProfile.value
        };

        if (prof && (prof.forced_context_size || prof.ctx_size)) {
            payload.llm_ctx_size = Number(prof.forced_context_size || prof.ctx_size);
        }

        await adminStore.batchUpdateUsers(payload);
        
        if (onSettingsApplied.value && typeof onSettingsApplied.value === 'function') {
            onSettingsApplied.value();
        }
        
        uiStore.addNotification(`Model profile '${prof?.name || selectedModelProfile.value}' applied to ${selectedUserIds.value.length} user(s).`, 'success');
        uiStore.closeModal('forceSettings');
    } finally {
        isLoading.value = false;
    }
}

onMounted(() => {
    if (dataStore.availableLLMModelsGrouped.length === 0) {
        dataStore.fetchAvailableLollmsModels();
    }
    if (allUsers.value.length === 0) {
        adminStore.fetchAllUsers();
    } else {
        const passedIds = props.value?.selectedUserIds;
        if (Array.isArray(passedIds) && passedIds.length > 0) {
            selectedUserIds.value = [...passedIds];
        } else {
            selectedUserIds.value = allUsers.value.map(u => u.id);
        }
    }
});

watch(allUsers, (newUsers) => {
    const passedIds = props.value?.selectedUserIds;
    if (Array.isArray(passedIds) && passedIds.length > 0) {
        selectedUserIds.value = [...passedIds];
    } else if (newUsers.length > 0 && selectedUserIds.value.length === 0) {
        selectedUserIds.value = newUsers.map(u => u.id);
    }
});
</script>

<template>
    <GenericModal modal-name="forceSettings" title="Apply Universal Model Profile to Users" maxWidthClass="max-w-2xl">
        <template #body>
            <form @submit.prevent="handleSubmit" class="space-y-6 p-1">
                <p class="text-xs text-gray-500 dark:text-gray-400">
                    Select a Universal Model Profile. The profile's context window, vision support, and parameters will be assigned to the selected accounts.
                </p>

                <!-- Model Profile Selector -->
                <div class="space-y-3 p-4 bg-gray-50 dark:bg-gray-900/50 rounded-2xl border border-gray-100 dark:border-gray-800">
                    <div>
                        <label for="force-model" class="block text-xs font-bold uppercase tracking-wider text-gray-700 dark:text-gray-300 mb-1">
                            Universal Model Profile *
                        </label>
                        <select id="force-model" v-model="selectedModelProfile" class="input-field text-xs" :disabled="isLoadingLollmsModels" required>
                            <option v-if="isLoadingLollmsModels" disabled value="">Loading profiles...</option>
                            <option v-else value="" disabled>-- Select a Profile --</option>
                            <optgroup v-for="group in availableLLMModelsGrouped" :key="group.label" :label="group.label">
                                <option v-for="model in group.items" :key="model.id" :value="model.id">
                                    {{ model.name }} {{ (model.vision_enabled || model.has_vision) ? '👁️' : '' }} ({{ model.id }})
                                </option>
                            </optgroup>
                        </select>
                    </div>

                    <!-- Selected Profile Meta Preview -->
                    <div v-if="selectedProfileDetails" class="p-3 bg-white dark:bg-gray-800 rounded-xl border border-gray-200/80 dark:border-gray-700/70 text-xs flex items-center justify-between gap-4">
                        <div class="flex items-center gap-3 min-w-0">
                            <div class="w-8 h-8 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0">
                                <IconCpuChip class="w-4 h-4" />
                            </div>
                            <div class="min-w-0">
                                <span class="font-bold text-gray-900 dark:text-white block truncate">{{ selectedProfileDetails.name }}</span>
                                <span class="text-[10px] text-gray-400 font-mono block truncate">{{ selectedProfileDetails.id }}</span>
                            </div>
                        </div>

                        <div class="flex items-center gap-3 shrink-0 font-mono text-[11px]">
                            <span class="text-blue-500 font-bold">
                                {{ (selectedProfileDetails.forced_context_size || selectedProfileDetails.ctx_size) ? `${(selectedProfileDetails.forced_context_size || selectedProfileDetails.ctx_size).toLocaleString()} tok` : 'Auto' }}
                            </span>
                            <span v-if="selectedProfileDetails.vision_enabled || selectedProfileDetails.has_vision" class="px-2 py-0.5 rounded bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 text-[9px] font-bold uppercase">
                                👁️ Vision
                            </span>
                        </div>
                    </div>
                </div>

                <!-- User Selection Box -->
                <div class="space-y-3 pt-2">
                    <div class="flex items-center justify-between">
                        <h4 class="text-xs font-black uppercase tracking-wider text-gray-700 dark:text-gray-300">
                            Target Users ({{ selectedUserIds.length }} of {{ allUsers.length }})
                        </h4>
                        <div class="flex items-center gap-2">
                            <label class="flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400 font-bold cursor-pointer select-none">
                                <input type="checkbox" v-model="areAllUsersSelected" class="rounded text-blue-600 focus:ring-blue-500">
                                <span>Select All</span>
                            </label>
                        </div>
                    </div>

                    <input type="text" v-model="userSearchQuery" placeholder="Filter user list..." class="input-field text-xs w-full">

                    <div class="max-h-56 overflow-y-auto border border-gray-200 dark:border-gray-700 rounded-2xl p-2 space-y-1 bg-gray-50/50 dark:bg-gray-900/30 custom-scrollbar">
                        <div v-if="isLoadingUsers" class="text-center text-xs text-gray-400 py-4">Loading users...</div>
                        <div v-else-if="filteredUsers.length === 0" class="text-center text-xs text-gray-400 py-4">No users match filter.</div>
                        <div 
                            v-for="user in filteredUsers" 
                            :key="user.id" 
                            class="flex items-center justify-between p-2 rounded-xl hover:bg-white dark:hover:bg-gray-800 transition-colors cursor-pointer"
                            @click="selectedUserIds.includes(user.id) ? selectedUserIds = selectedUserIds.filter(id => id !== user.id) : selectedUserIds.push(user.id)"
                        >
                            <div class="flex items-center gap-2.5 min-w-0">
                                <input 
                                    :id="`user-${user.id}`" 
                                    :value="user.id" 
                                    v-model="selectedUserIds" 
                                    type="checkbox" 
                                    @click.stop
                                    class="rounded text-blue-600 focus:ring-blue-500"
                                >
                                <label :for="`user-${user.id}`" class="text-xs font-bold text-gray-800 dark:text-gray-200 cursor-pointer truncate">
                                    {{ user.username }}
                                </label>
                            </div>
                            <span class="text-[10px] font-mono text-gray-400 truncate max-w-[180px]">{{ user.lollms_model_name || 'Default' }}</span>
                        </div>
                    </div>
                </div>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-end gap-2 w-full">
                <button type="button" class="btn btn-secondary text-xs" @click="uiStore.closeModal('forceSettings')" :disabled="isLoading">Cancel</button>
                <button type="submit" class="btn btn-primary text-xs" :disabled="isLoading || selectedUserIds.length === 0 || !selectedModelProfile" @click="handleSubmit">
                    <IconAnimateSpin v-if="isLoading" class="w-3.5 h-3.5 mr-1.5 animate-spin" />
                    <span>{{ isLoading ? 'Applying...' : `Assign Profile to ${selectedUserIds.length} User(s)` }}</span>
                </button>
            </div>
        </template>
    </GenericModal>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>