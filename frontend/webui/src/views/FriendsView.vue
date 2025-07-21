<script setup>
import { ref, computed, onMounted, defineAsyncComponent } from 'vue';
import { useSocialStore } from '../stores/social';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import IconUserGroup from '../assets/icons/IconUserGroup.vue';
import IconTicket from '../assets/icons/IconTicket.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconNoSymbol from '../assets/icons/IconNoSymbol.vue';

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
  <PageViewLayout title="Friends" :title-icon="IconUserGroup">
    <template #sidebar>
        <button
            v-for="tab in tabs"
            :key="tab.id"
            @click="activeTab = tab.id"
            :class="[
                activeTab === tab.id
                    ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'
                    : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700',
                'w-full flex items-center justify-between text-left px-3 py-2.5 rounded-lg text-sm font-medium transition-colors'
            ]"
        >
            <div class="flex items-center space-x-3">
                <component :is="tab.icon" class="w-5 h-5 flex-shrink-0" />
                <span>{{ tab.label }}</span>
            </div>
            <span v-if="tab.count > 0" class="bg-red-500 text-white text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center">
                {{ tab.count }}
            </span>
        </button>
    </template>
    <template #main>
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
    </template>
  </PageViewLayout>
</template>