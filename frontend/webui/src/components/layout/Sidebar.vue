<script setup>
import { computed, ref } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import UserAvatar from '../ui/UserAvatar.vue';
import ThemeToggle from '../ui/ThemeToggle.vue';
import DiscussionList from './DiscussionList.vue';
import UserInfo from './UserInfo.vue';
import logoUrl from '../../assets/logo.png';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const user = computed(() => authStore.user);
const mainView = computed(() => uiStore.mainView);
const currentDiscussionId = computed(() => discussionsStore.currentDiscussionId);
const isUserMenuOpen = ref(false);

const allDiscussions = computed(() => Object.values(discussionsStore.discussions).sort((a,b) => new Date(b.last_activity_at || 0) - new Date(a.last_activity_at || 0)));
const starredDiscussions = computed(() => allDiscussions.value.filter(d => d.is_starred));
const regularDiscussions = computed(() => allDiscussions.value.filter(d => !d.is_starred));

const searchTerm = ref('');
const filteredRegularDiscussions = computed(() => {
    if (!searchTerm.value) return regularDiscussions.value;
    const lowerCaseSearch = searchTerm.value.toLowerCase();
    return regularDiscussions.value.filter(d => d.title.toLowerCase().includes(lowerCaseSearch));
});



</script>

<template>
  <aside class="w-80 bg-gray-100 dark:bg-gray-800 flex flex-col h-full border-r dark:border-gray-700">
    <div class="p-4 border-b dark:border-gray-700 flex-shrink-0">
        <div class="flex items-center justify-between">
            <div class="relative">
                <button @click="isUserMenuOpen = !isUserMenuOpen" class="flex items-center space-x-3">
                    <UserAvatar v-if="user" :icon="user.icon" :username="user.username" size-class="h-10 w-10" />
                    <div>
                        <div class="font-semibold text-gray-800 dark:text-gray-100">{{ user?.username }}</div>
                        <div class="text-xs text-gray-500">Online</div>
                    </div>
                </button>
                <div v-if="isUserMenuOpen" v-on-click-outside="() => isUserMenuOpen = false" class="absolute left-0 mt-2 w-56 bg-white dark:bg-gray-900 rounded-md shadow-lg z-20 border dark:border-gray-700">
                    <div class="py-1">
                        <div class="border-t border-gray-200 dark:border-gray-700 my-1"></div>
                        <button @click="authStore.logout()" class="w-full text-left flex items-center px-4 py-2 text-sm text-red-600 hover:bg-gray-100 dark:hover:bg-gray-800">Logout</button>
                    </div>
                </div>
            </div>
            <ThemeToggle />
        </div>
        
    </div>
    
    <!-- Discussion List (Main scrolling area) -->
    <DiscussionList class="flex-1 overflow-y-auto" />

    <!-- User Info and Menu at the bottom -->
    <div class="p-3 border-t dark:border-gray-700">
    <UserInfo />
    </div>
  </aside>
</template>

<style scoped>
.main-nav-btn { @apply w-full py-2 px-3 rounded-md text-sm font-semibold transition-colors duration-200 text-gray-600 bg-gray-200 dark:text-gray-300 dark:bg-gray-700; }
.main-nav-btn:hover { @apply bg-gray-300 dark:bg-gray-600; }
.main-nav-btn.active { @apply bg-blue-500 text-white dark:bg-blue-600; }
.discussion-item { @apply w-full text-left flex items-center p-3 text-sm transition-colors duration-150 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700; }
.discussion-item.active { @apply bg-blue-500 text-white font-semibold dark:bg-blue-600; }
.sidebar-section-header { @apply px-3 pt-4 pb-2 text-xs font-bold uppercase text-gray-500 dark:text-gray-400; }
</style>