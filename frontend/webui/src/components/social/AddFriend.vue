<script setup>
import { ref, computed } from 'vue';
import { useSocialStore } from '../../stores/social';
import UserAvatar from '../ui/UserAvatar.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';

const socialStore = useSocialStore();

const searchQuery = ref('');
const searchResults = ref([]);
const isLoading = ref(false);
let debounceTimer = null;

const searchStatus = computed(() => {
    if (isLoading.value) return 'Searching...';
    if (searchQuery.value && searchResults.value.length === 0) return 'No users found.';
    return '';
});

function handleSearchInput() {
    clearTimeout(debounceTimer);
    if (!searchQuery.value || searchQuery.value.length < 2) {
        searchResults.value = [];
        return;
    }
    isLoading.value = true;
    debounceTimer = setTimeout(async () => {
        try {
            // Using a direct API call here as search results are temporary
            const response = await (await import('../../services/api')).default.get('/api/users/search', {
                params: { q: searchQuery.value }
            });
            searchResults.value = response.data;
        } catch (error) {
            console.error("User search failed:", error);
            searchResults.value = [];
        } finally {
            isLoading.value = false;
        }
    }, 500); // 500ms debounce
}

async function handleAddFriend(username) {
    try {
        await socialStore.sendFriendRequest(username);
        // Remove user from search results after sending a request to prevent spamming
        searchResults.value = searchResults.value.filter(u => u.username !== username);
    } catch (error) {
        // Error notification handled by the store
    }
}
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <div class="relative">
      <input 
        type="text" 
        v-model="searchQuery" 
        @input="handleSearchInput"
        placeholder="Search by username..."
        class="input-field w-full !pl-10"
      />
      <div class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
        <svg class="w-5 h-5 text-gray-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd" /></svg>
      </div>
    </div>

    <div class="mt-4">
      <div v-if="searchStatus" class="text-center py-6 text-gray-500">{{ searchStatus }}</div>
      <ul v-else-if="searchResults.length > 0" class="space-y-3">
        <li v-for="user in searchResults" :key="user.id" class="bg-white dark:bg-gray-800 p-3 rounded-lg shadow-sm flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <UserAvatar :icon="user.icon" :username="user.username" size-class="h-10 w-10" />
            <span class="font-medium text-gray-800 dark:text-gray-100">{{ user.username }}</span>
          </div>
          <button @click="handleAddFriend(user.username)" class="btn btn-secondary btn-sm flex items-center space-x-1">
            <IconPlus class="w-4 h-4" />
            <span>Add</span>
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>