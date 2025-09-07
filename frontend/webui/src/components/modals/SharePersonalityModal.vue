<script setup>
import { ref, computed, onMounted } from 'vue';
import GenericModal from '../ui/GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import { useSocialStore } from '../../stores/social';
import UserAvatar from '../ui/UserAvatar.vue';

const uiStore = useUiStore();
const dataStore = useDataStore();
const socialStore = useSocialStore();

const modalProps = computed(() => uiStore.modalData('sharePersonality'));
const personalityId = computed(() => modalProps.value?.personalityId);
const title = computed(() => modalProps.value?.title);

const targetUsername = ref('');
const isLoading = ref(false);

const friends = computed(() => socialStore.friends);

onMounted(() => {
    if (socialStore.friends.length === 0) {
        socialStore.fetchFriends();
    }
});

async function handleSubmit() {
    if (!targetUsername.value.trim()) {
        uiStore.addNotification('Please enter a username.', 'warning');
        return;
    }
    isLoading.value = true;
    try {
        await dataStore.sendPersonality({
            personalityId: personalityId.value,
            targetUsername: targetUsername.value
        });
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
  <GenericModal modal-name="sharePersonality" :title="`Share Personality: ${title}`">
    <template #body>
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div>
          <label for="target-username" class="block text-sm font-medium">Username</label>
          <input id="target-username" v-model="targetUsername" type="text" class="input-field mt-1" placeholder="Enter username to send to" required>
        </div>
        <div v-if="friends.length > 0">
          <p class="text-sm font-medium">Or select a friend:</p>
          <div class="mt-2 max-h-40 overflow-y-auto space-y-1 p-1 bg-gray-50 dark:bg-gray-700/50 rounded-md border dark:border-gray-600">
            <button v-for="friend in friends" :key="friend.id" @click.prevent="targetUsername = friend.username" type="button" class="w-full text-left p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2">
              <UserAvatar :icon="friend.icon" :username="friend.username" size-class="w-6 h-6" />
              <span>{{ friend.username }}</span>
            </button>
          </div>
        </div>
      </form>
    </template>
    <template #footer>
      <button @click="uiStore.closeModal('sharePersonality')" type="button" class="btn btn-secondary">Cancel</button>
      <button @click="handleSubmit" type="button" class="btn btn-primary" :disabled="isLoading || !targetUsername.trim()">
        {{ isLoading ? 'Sending...' : 'Send' }}
      </button>
    </template>
  </GenericModal>
</template>