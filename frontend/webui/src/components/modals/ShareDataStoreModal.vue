<script setup>
import { ref, computed, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import { useSocialStore } from '../../stores/social';
import GenericModal from './GenericModal.vue';

const uiStore = useUiStore();
const dataStore = useDataStore();
const socialStore = useSocialStore();

const storeToShare = computed(() => uiStore.modalData('shareDataStore')?.store);
const friends = computed(() => socialStore.friends);

const selectedFriendIds = ref([]); // Now an array for multiple selections
const isLoading = ref(false);
const permissionLevel = ref('read_query');

const permissions = [
    { value: 'read_query', label: 'Read (Query)' },
    { value: 'read_write', label: 'Read/Write' },
    { value: 'revectorize', label: 'Read/Write & Revectorize' }
];

// Computed property to check if all friends are selected
const isAllSelected = computed({
    get: () => friends.value.length > 0 && selectedFriendIds.value.length === friends.value.length,
    set: (value) => {
        if (value) {
            selectedFriendIds.value = friends.value.map(friend => friend.id);
        } else {
            selectedFriendIds.value = [];
        }
    }
});

// Fetch friends when the modal is likely to be opened
onMounted(() => {
    if (socialStore.friends.length === 0) {
        socialStore.fetchFriends();
    }
});

async function handleShare() {
    if (selectedFriendIds.value.length === 0 || !storeToShare.value) return;

    isLoading.value = true;
    const count = selectedFriendIds.value.length;

    try {
        const sharePayloadBase = {
            storeId: storeToShare.value.id,
            permissionLevel: permissionLevel.value
        };

        const sharePromises = selectedFriendIds.value.map(friendId => {
            const friend = friends.value.find(f => f.id === friendId);
            if (friend) {
                return dataStore.shareDataStore({ ...sharePayloadBase, username: friend.username });
            }
            return Promise.resolve(); // Should not happen, but a safe fallback
        });

        await Promise.all(sharePromises);
        uiStore.addNotification(`Store shared with ${count} friend${count > 1 ? 's' : ''}.`, 'success');
        handleClose();

    } catch (error) {
        // Error notification is handled by the dataStore
    } finally {
        isLoading.value = false;
    }
}

function handleClose() {
    selectedFriendIds.value = []; // Reset the array
    permissionLevel.value = 'read_query';
    uiStore.closeModal('shareDataStore');
}
</script>

<template>
  <GenericModal
    modalName="shareDataStore"
    :title="`Share '${storeToShare?.name || 'Data Store'}'`"
    :allow-overlay-close="!isLoading"
  >
    <template #body>
      <form @submit.prevent="handleShare" class="space-y-4">
        <!-- Friend Selection List -->
        <div>
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Share with
          </label>
          <div v-if="friends.length > 0">
            <!-- Select All Checkbox -->
            <div class="border-b border-gray-200 dark:border-gray-600 pb-2 mb-2">
              <label class="flex items-center space-x-3 cursor-pointer p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700">
                <input
                  type="checkbox"
                  v-model="isAllSelected"
                  class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span class="font-medium text-gray-800 dark:text-gray-200">Select All Friends</span>
              </label>
            </div>
            <!-- Friend List -->
            <div class="max-h-60 overflow-y-auto space-y-1 pr-2">
              <label v-for="friend in friends" :key="friend.id" class="flex items-center space-x-3 cursor-pointer p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700">
                <input
                  type="checkbox"
                  :value="friend.id"
                  v-model="selectedFriendIds"
                  class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span class="text-gray-700 dark:text-gray-300">{{ friend.username }}</span>
              </label>
            </div>
          </div>
          <p v-else class="mt-2 text-sm text-gray-500 bg-gray-50 dark:bg-gray-700/50 p-4 rounded-md">
            You don't have any friends to share with yet. Add some from the Friends page!
          </p>
        </div>
        
        <!-- Permission Level -->
        <div>
          <label for="permission-level" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
            As
          </label>
          <select id="permission-level" v-model="permissionLevel" class="input-field mt-1">
            <option v-for="perm in permissions" :key="perm.value" :value="perm.value">
              {{ perm.label }}
            </option>
          </select>
        </div>
      </form>
    </template>
    
    <template #footer>
      <button type="button" @click="handleClose" :disabled="isLoading" class="btn btn-secondary">
        Cancel
      </button>
      <button
        type="button"
        @click="handleShare"
        :disabled="isLoading || selectedFriendIds.length === 0"
        class="btn btn-primary"
      >
        {{ isLoading ? 'Sharing...' : `Share with ${selectedFriendIds.length} Friend${selectedFriendIds.length !== 1 ? 's' : ''}` }}
      </button>
    </template>
  </GenericModal>
</template>