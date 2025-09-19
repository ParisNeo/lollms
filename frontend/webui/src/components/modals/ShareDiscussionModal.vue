<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import { useSocialStore } from '../../stores/social';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import { storeToRefs } from 'pinia';
import MultiSelectMenu from '../ui/MultiSelectMenu.vue';

const socialStore = useSocialStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const { friends, isLoadingFriends } = storeToRefs(socialStore);

const modalData = computed(() => uiStore.modalProps.shareDiscussion);
const discussionId = computed(() => modalData.value?.discussionId);
const discussionTitle = computed(() => modalData.value?.title);
 
const sharedWith = ref([]);
const isLoadingSharedWith = ref(false);
const friendsToAdd = ref([]);
const newPermissionLevel = ref('view');
const isSending = ref(false);
const searchQuery = ref('');
const showAdvancedOptions = ref(false);
const bulkAction = ref('');
const selectedShares = ref(new Set());
const copyLinkSuccess = ref(false);

// Enhanced computed properties
const availableFriends = computed(() => {
    const sharedUserIds = new Set(sharedWith.value.map(s => s.owner_id));
    const filtered = (friends.value || [])
        .filter(f => !sharedUserIds.has(f.id))
        .map(f => ({
            id: f.id, 
            name: f.username, 
            icon: f.icon,
            email: f.email || '',
            lastActive: f.last_active || null
        }));
    
    if (!searchQuery.value) return filtered;
    
    const query = searchQuery.value.toLowerCase();
    return filtered.filter(f => 
        f.name.toLowerCase().includes(query) || 
        f.email.toLowerCase().includes(query)
    );
});

const shareStats = computed(() => ({
    total: sharedWith.value.length,
    canView: sharedWith.value.filter(s => s.permission_level === 'view').length,
    canInteract: sharedWith.value.filter(s => s.permission_level === 'interact').length
}));

const hasSelectedShares = computed(() => selectedShares.value.size > 0);

const canAddMore = computed(() => {
    const maxShares = 50; // Configurable limit
    return sharedWith.value.length < maxShares;
});

// Enhanced functions
async function refreshFriends() {
    try {
        await socialStore.fetchFriends();
        uiStore.addNotification("Friends list refreshed", "success");
    } catch (error) {
        uiStore.addNotification("Failed to refresh friends list", "error");
    }
}

async function fetchSharedWithList() {
    if (!discussionId.value) return;
    isLoadingSharedWith.value = true;
    try {
        const response = await (await import('../../services/api')).default.get(
            `/api/discussions/${discussionId.value}/shared-with`
        );
        sharedWith.value = response.data;
    } catch (error) {
        console.error('Failed to fetch shared with list:', error);
        uiStore.addNotification("Could not load sharing information.", "error");
        sharedWith.value = [];
    } finally {
        isLoadingSharedWith.value = false;
    }
}

watch(discussionId, (newId) => {
    if (newId) {
        fetchSharedWithList();
        refreshFriends();
        // Reset state when opening new discussion
        friendsToAdd.value = [];
        selectedShares.value.clear();
        searchQuery.value = '';
    } else {
        sharedWith.value = [];
    }
}, { immediate: true });

onMounted(() => {
    if (discussionId.value) {
        fetchSharedWithList();
        refreshFriends();
    }
});

async function handleAddShares() {
    if (friendsToAdd.value.length === 0) {
        uiStore.addNotification("Please select at least one friend to add.", "warning");
        return;
    }

    if (!canAddMore.value) {
        uiStore.addNotification("Maximum share limit reached.", "warning");
        return;
    }

    isSending.value = true;
    const errors = [];
    let successCount = 0;

    try {
        // Process shares with better error handling
        const sharePromises = friendsToAdd.value.map(async (friendId) => {
            try {
                await discussionsStore.shareDiscussion({
                    discussionId: discussionId.value,
                    targetUserId: friendId,
                    permissionLevel: newPermissionLevel.value
                });
                successCount++;
            } catch (error) {
                const friendName = friends.value.find(f => f.id === friendId)?.username || 'Unknown';
                errors.push(`Failed to share with ${friendName}`);
            }
        });

        await Promise.all(sharePromises);

        // Show appropriate notifications
        if (successCount > 0) {
            uiStore.addNotification(
                `Successfully shared with ${successCount} friend${successCount > 1 ? 's' : ''}.`, 
                "success"
            );
        }

        if (errors.length > 0) {
            errors.forEach(error => uiStore.addNotification(error, "error"));
        }

        friendsToAdd.value = [];
        await fetchSharedWithList();
    } finally {
        isSending.value = false;
    }
}

async function handleUpdatePermission(share) {
    const originalLevel = share.permission_level;
    try {
        await discussionsStore.shareDiscussion({
            discussionId: discussionId.value,
            targetUserId: share.owner_id,
            permissionLevel: share.permission_level
        });
        
        uiStore.addNotification(
            `Updated ${share.owner_username}'s permissions to ${share.permission_level}`, 
            "success"
        );
        await fetchSharedWithList();
    } catch (error) {
        // Revert the change on error
        share.permission_level = originalLevel;
        uiStore.addNotification(
            `Failed to update permissions for ${share.owner_username}`, 
            "error"
        );
    }
}

async function handleRevoke(share) {
    if (!confirm(`Are you sure you want to revoke access for ${share.owner_username}?`)) {
        return;
    }

    try {
        await discussionsStore.revokeShare({
            discussionId: discussionId.value,
            shareId: share.share_id
        });
        
        uiStore.addNotification(
            `Revoked access for ${share.owner_username}`, 
            "success"
        );
        await fetchSharedWithList();
    } catch (error) {
        uiStore.addNotification(
            `Failed to revoke access for ${share.owner_username}`, 
            "error"
        );
    }
}

// New bulk operations
async function handleBulkAction() {
    if (!hasSelectedShares.value || !bulkAction.value) return;

    const selectedSharesList = sharedWith.value.filter(s => selectedShares.value.has(s.share_id));
    
    if (bulkAction.value === 'revoke') {
        if (!confirm(`Are you sure you want to revoke access for ${selectedSharesList.length} user(s)?`)) {
            return;
        }

        for (const share of selectedSharesList) {
            try {
                await discussionsStore.revokeShare({
                    discussionId: discussionId.value,
                    shareId: share.share_id
                });
            } catch (error) {
                console.error(`Failed to revoke ${share.owner_username}:`, error);
            }
        }
        
        uiStore.addNotification(`Revoked access for ${selectedSharesList.length} user(s)`, "success");
    } else if (bulkAction.value === 'view' || bulkAction.value === 'interact') {
        for (const share of selectedSharesList) {
            try {
                await discussionsStore.shareDiscussion({
                    discussionId: discussionId.value,
                    targetUserId: share.owner_id,
                    permissionLevel: bulkAction.value
                });
            } catch (error) {
                console.error(`Failed to update ${share.owner_username}:`, error);
            }
        }
        
        uiStore.addNotification(
            `Updated permissions for ${selectedSharesList.length} user(s)`, 
            "success"
        );
    }

    selectedShares.value.clear();
    bulkAction.value = '';
    await fetchSharedWithList();
}

function toggleSelectAll() {
    if (selectedShares.value.size === sharedWith.value.length) {
        selectedShares.value.clear();
    } else {
        selectedShares.value = new Set(sharedWith.value.map(s => s.share_id));
    }
}

function toggleShareSelection(shareId) {
    if (selectedShares.value.has(shareId)) {
        selectedShares.value.delete(shareId);
    } else {
        selectedShares.value.add(shareId);
    }
}

async function copyShareableLink() {
    try {
        const link = `${window.location.origin}/discussions/${discussionId.value}`;
        await navigator.clipboard.writeText(link);
        copyLinkSuccess.value = true;
        uiStore.addNotification("Shareable link copied to clipboard", "success");
        
        setTimeout(() => {
            copyLinkSuccess.value = false;
        }, 2000);
    } catch (error) {
        uiStore.addNotification("Failed to copy link", "error");
    }
}

function getPermissionBadgeClass(level) {
    return level === 'interact' 
        ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
        : 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400';
}

function formatShareDate(dateString) {
    return new Intl.DateTimeFormat('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    }).format(new Date(dateString));
}
</script>

<template>
  <GenericModal modalName="shareDiscussion" title="Share Discussion" size="large">
    <template #body>
      <div class="space-y-6">
        <!-- Discussion Info -->
        <div class="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4">
          <div class="flex items-start justify-between">
            <div class="flex-1 min-w-0">
              <p class="text-sm text-gray-600 dark:text-gray-400 mb-1">Sharing:</p>
              <h3 class="font-semibold text-gray-900 dark:text-gray-100 truncate" :title="discussionTitle">
                {{ discussionTitle || 'Untitled Discussion' }}
              </h3>
              
              <!-- Stats -->
              <div class="flex items-center gap-4 mt-2 text-xs text-gray-500 dark:text-gray-400">
                <span>{{ shareStats.total }} shares</span>
                <span>{{ shareStats.canView }} viewers</span>
                <span>{{ shareStats.canInteract }} contributors</span>
              </div>
            </div>
            
            <!-- Copy Link Button -->
            <button 
              @click="copyShareableLink"
              class="btn btn-secondary btn-sm"
              :class="{ 'btn-success': copyLinkSuccess }"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              {{ copyLinkSuccess ? 'Copied!' : 'Copy Link' }}
            </button>
          </div>
        </div>

        <!-- Existing Shares -->
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="font-medium text-gray-700 dark:text-gray-300">
              Shared With ({{ shareStats.total }})
            </h3>
            
            <!-- Bulk Actions -->
            <div v-if="sharedWith.length > 0" class="flex items-center gap-2">
              <button 
                @click="toggleSelectAll"
                class="text-xs text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
              >
                {{ selectedShares.size === sharedWith.length ? 'Deselect All' : 'Select All' }}
              </button>
              
              <div v-if="hasSelectedShares" class="flex items-center gap-2">
                <select v-model="bulkAction" class="input-field !py-1 !text-xs">
                  <option value="">Bulk Action</option>
                  <option value="view">Set to View Only</option>
                  <option value="interact">Set to Interact</option>
                  <option value="revoke">Revoke Access</option>
                </select>
                <button 
                  @click="handleBulkAction"
                  :disabled="!bulkAction"
                  class="btn btn-primary btn-sm"
                >
                  Apply
                </button>
              </div>
            </div>
          </div>

          <div v-if="isLoadingSharedWith" class="text-center py-8">
            <div class="animate-spin inline-block w-6 h-6 border-2 border-gray-300 border-t-blue-600 rounded-full"></div>
            <p class="text-sm text-gray-500 mt-2">Loading shares...</p>
          </div>

          <div v-else-if="sharedWith.length === 0" class="text-center py-8 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-lg">
            <svg xmlns="http://www.w3.org/2000/svg" class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            <p class="text-sm text-gray-500 mt-2">Not shared with anyone yet</p>
            <p class="text-xs text-gray-400">Add friends below to start sharing</p>
          </div>

          <div v-else class="max-h-64 overflow-y-auto space-y-2 pr-2">
            <div 
              v-for="share in sharedWith" 
              :key="share.share_id" 
              class="flex items-center gap-3 p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:shadow-sm transition-all"
            >
              <!-- Selection Checkbox -->
              <input 
                type="checkbox"
                :checked="selectedShares.has(share.share_id)"
                @change="toggleShareSelection(share.share_id)"
                class="rounded border-gray-300 text-blue-600 focus:ring-blue-500 dark:border-gray-600"
              >
              
              <!-- User Info -->
              <div class="flex items-center gap-3 flex-1 min-w-0">
                <UserAvatar 
                  :icon="share.owner_icon" 
                  :username="share.owner_username" 
                  size-class="h-10 w-10" 
                />
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="font-medium text-gray-900 dark:text-gray-100 truncate">
                      {{ share.owner_username }}
                    </span>
                    <span 
                      class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                      :class="getPermissionBadgeClass(share.permission_level)"
                    >
                      {{ share.permission_level === 'interact' ? 'Can Interact' : 'View Only' }}
                    </span>
                  </div>
                  <p class="text-xs text-gray-500 dark:text-gray-400">
                    Shared {{ formatShareDate(share.shared_at) }}
                  </p>
                </div>
              </div>

              <!-- Actions -->
              <div class="flex items-center gap-2 flex-shrink-0">
                <select 
                  v-model="share.permission_level" 
                  @change="handleUpdatePermission(share)" 
                  class="input-field !py-1 !text-xs w-28"
                >
                  <option value="view">View Only</option>
                  <option value="interact">Can Interact</option>
                </select>
                <button 
                  @click="handleRevoke(share)" 
                  class="btn btn-danger btn-sm !p-1.5" 
                  :title="`Revoke access for ${share.owner_username}`"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Add New Shares -->
        <div class="space-y-4 border-t border-gray-200 dark:border-gray-700 pt-6">
          <div class="flex items-center justify-between">
            <h4 class="font-medium text-gray-700 dark:text-gray-300">
              Add More Friends
              {{ !canAddMore ? '(Limit Reached)' : '' }}
            </h4>
            <button 
              @click="refreshFriends" 
              class="btn-icon" 
              title="Refresh friends list" 
              :disabled="isLoadingFriends"
            >
              <IconRefresh 
                class="w-4 h-4" 
                :class="{'animate-spin': isLoadingFriends}" 
              />
            </button>
          </div>
          
          <!-- Search Friends -->
          <div class="relative">
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search friends..."
              class="input-field pl-10"
              :disabled="!canAddMore"
            >
            <svg xmlns="http://www.w3.org/2000/svg" class="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          
          <MultiSelectMenu 
            v-model="friendsToAdd" 
            :items="availableFriends" 
            placeholder="Select friends to share with..." 
            :disabled="availableFriends.length === 0 || !canAddMore"
            :max-selections="10"
          />

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label for="permission-level" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Permission Level
              </label>
              <select 
                id="permission-level" 
                v-model="newPermissionLevel" 
                class="input-field w-full"
                :disabled="!canAddMore"
              >
                <option value="view">View Only - Can read discussion</option>
                <option value="interact">Can Interact - Can read and contribute</option>
              </select>
            </div>

            <!-- Advanced Options Toggle -->
            <div class="flex items-end">
              <button 
                @click="showAdvancedOptions = !showAdvancedOptions"
                class="text-sm text-blue-600 dark:text-blue-400 hover:underline"
              >
                {{ showAdvancedOptions ? 'Hide' : 'Show' }} Advanced Options
              </button>
            </div>
          </div>

          <!-- Advanced Options -->
          <div v-if="showAdvancedOptions" class="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 space-y-3">
            <h5 class="font-medium text-gray-700 dark:text-gray-300">Advanced Settings</h5>
            
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <label class="flex items-center">
                <input type="checkbox" class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                <span class="ml-2 text-sm text-gray-700 dark:text-gray-300">Send notification</span>
              </label>
              
              <label class="flex items-center">
                <input type="checkbox" class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                <span class="ml-2 text-sm text-gray-700 dark:text-gray-300">Allow resharing</span>
              </label>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Custom message (optional)
              </label>
              <textarea 
                class="input-field w-full" 
                rows="2" 
                placeholder="Add a personal message..."
              ></textarea>
            </div>
          </div>

          <!-- Help Text -->
          <div class="text-xs text-gray-500 dark:text-gray-400 bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
            <p><strong>View Only:</strong> Can read the discussion but cannot add messages or reactions.</p>
            <p><strong>Can Interact:</strong> Can read, add messages, reactions, and participate fully.</p>
          </div>
        </div>
      </div>
    </template>
    
    <template #footer>
      <div class="flex items-center justify-between w-full">
        <button 
          @click="uiStore.closeModal()" 
          type="button" 
          class="btn btn-secondary"
        >
          Close
        </button>
        
        <div class="flex items-center gap-2">
          <!-- Share Count Display -->
          <span v-if="friendsToAdd.length > 0" class="text-sm text-gray-600 dark:text-gray-400">
            Selected: {{ friendsToAdd.length }}
          </span>
          
          <button 
            @click="handleAddShares" 
            :disabled="friendsToAdd.length === 0 || isSending || !canAddMore"
            class="btn btn-primary"
          >
            <svg v-if="isSending" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ isSending ? 'Sharing...' : `Share with ${friendsToAdd.length || ''}` }}
          </button>
        </div>
      </div>
    </template>
  </GenericModal>
</template>

<style scoped>
/* Custom scrollbar for the shared with list */
.max-h-64::-webkit-scrollbar {
  width: 6px;
}

.max-h-64::-webkit-scrollbar-track {
  @apply bg-gray-100 dark:bg-gray-800 rounded;
}

.max-h-64::-webkit-scrollbar-thumb {
  @apply bg-gray-300 dark:bg-gray-600 rounded;
}

.max-h-64::-webkit-scrollbar-thumb:hover {
  @apply bg-gray-400 dark:bg-gray-500;
}

/* Smooth transitions */
.transition-all {
  transition: all 0.2s ease-in-out;
}

/* Loading state animation */
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.animate-spin {
  animation: spin 1s linear infinite;
}
</style>
