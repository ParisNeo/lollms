<script setup>
import { ref, computed, onMounted, defineAsyncComponent } from 'vue';
import { useSocialStore } from '../stores/social';
import IconUserGroup from '../assets/icons/IconUserGroup.vue';
import IconTicket from '../assets/icons/IconTicket.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconNoSymbol from '../assets/icons/IconNoSymbol.vue';
import IconArrowLeft from '../assets/icons/IconArrowLeft.vue';

// Async components
const AddFriend = defineAsyncComponent(() => import('../components/social/AddFriend.vue'));
const FriendRequestList = defineAsyncComponent(() => import('../components/social/FriendRequestList.vue'));
const FriendList = defineAsyncComponent(() => import('../components/social/FriendList.vue'));
const BlockedList = defineAsyncComponent(() => import('../components/social/BlockedList.vue'));

const socialStore = useSocialStore();

const activeTab = ref('all'); // 'all', 'requests', 'add', 'blocked'
const requestCount = computed(() => socialStore.friendRequestCount);

const tabs = computed(() => [
    { id: 'all', label: 'All Friends', icon: IconUserGroup },
    { id: 'requests', label: 'Requests', icon: IconTicket, count: requestCount.value },
    { id: 'add', label: 'Add Friend', icon: IconPlus },
    { id: 'blocked', label: 'Blocked', icon: IconNoSymbol },
]);

onMounted(() => {
    socialStore.fetchFriends();
    socialStore.fetchPendingRequests();
    socialStore.fetchBlockedUsers();
})

</script>

<template>
  <div class="flex flex-col h-screen bg-gray-100 dark:bg-gray-900 overflow-hidden">
    <header class="bg-white dark:bg-gray-800 border-b dark:border-gray-700 p-4 flex items-center justify-between shadow-sm flex-shrink-0">
      <div class="flex items-center space-x-3">
        <IconUserGroup class="h-6 w-6 text-gray-500 dark:text-gray-400" />
        <h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">Friends</h1>
      </div>
      <router-link
        to="/"
        class="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
      >
        <IconArrowLeft class="w-5 h-5" />
        <span>Back to App</span>
      </router-link>
    </header>

    <main class="flex-grow flex flex-col overflow-y-auto">
        <!-- Tab Navigation -->
        <div class="border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
            <nav class="-mb-px flex space-x-6 px-6" aria-label="Tabs">
                <button
                    v-for="tab in tabs"
                    :key="tab.id"
                    @click="activeTab = tab.id"
                    :class="[
                        activeTab === tab.id
                            ? 'border-blue-500 text-blue-600 dark:border-blue-400 dark:text-blue-300'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-500',
                        'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors flex items-center space-x-2'
                    ]"
                >
                    <component :is="tab.icon" class="w-5 h-5" />
                    <span>{{ tab.label }}</span>
                     <span v-if="tab.count > 0" class="ml-2 bg-red-500 text-white text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center">
                        {{ tab.count }}
                    </span>
                </button>
            </nav>
        </div>

        <!-- Tab Content -->
        <div class="flex-grow p-6">
            <div v-show="activeTab === 'all'">
                <Suspense>
                    <FriendList />
                    <template #fallback>
                        <div class="text-center text-gray-500">Loading friends...</div>
                    </template>
                </Suspense>
            </div>
            <div v-if="activeTab === 'requests'">
                <Suspense>
                    <FriendRequestList />
                    <template #fallback>
                        <div class="text-center text-gray-500">Loading requests...</div>
                    </template>
                </Suspense>
            </div>
            <div v-if="activeTab === 'add'">
                <Suspense>
                    <AddFriend />
                     <template #fallback>
                        <div class="text-center text-gray-500">Loading...</div>
                    </template>
                </Suspense>
            </div>
             <div v-if="activeTab === 'blocked'">
                <Suspense>
                    <BlockedList />
                     <template #fallback>
                        <div class="text-center text-gray-500">Loading...</div>
                    </template>
                </Suspense>
            </div>
        </div>
    </main>
  </div>
</template>