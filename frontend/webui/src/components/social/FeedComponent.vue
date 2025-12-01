<script setup>
import { onMounted, computed, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useSocialStore } from '../../stores/social';
import { useAuthStore } from '../../stores/auth';
import CreatePostForm from './CreatePostForm.vue';
import PostCard from './PostCard.vue';
import DmFooter from '../layout/DmFooter.vue';
import UserAvatar from '../ui/Cards/UserAvatar.vue';

const socialStore = useSocialStore();
const authStore = useAuthStore();
const showCreateForm = ref(false);

const { feedPosts, isLoadingFeed } = storeToRefs(socialStore);
const user = computed(() => authStore.user);

const canPost = computed(() => user.value && user.value.user_ui_level >= 2);
const canChat = computed(() => user.value && user.value.chat_active && user.value.user_ui_level >= 2);

onMounted(() => {
  if (feedPosts.value.length === 0) {
    socialStore.fetchFeed();
  }
});

</script>

<template>
  <div class="flex flex-col h-full">
    <div class="flex-grow bg-gray-100 dark:bg-gray-900 overflow-y-auto">
      <div class="mx-auto py-6 px-4">
        <h1 class="text-2xl font-bold text-gray-800 dark:text-gray-100 mb-6">
          Home Feed
        </h1>

        <div v-if="canPost" class="mb-6">
          <!-- Placeholder that reveals the form on click -->
          <div v-if="!showCreateForm" @click="showCreateForm = true" class="w-full flex items-center p-4 bg-white dark:bg-gray-800 rounded-lg shadow-md hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors cursor-pointer">
            <UserAvatar v-if="user" :icon="user.icon" :username="user.username || 'User'" size-class="h-10 w-10" />
            <div class="ml-4 text-gray-500 dark:text-gray-400">What's on your mind, {{ user.username }}?</div>
          </div>
          <!-- The actual form, shown when the placeholder is clicked -->
          <CreatePostForm 
            v-else
            @posted="showCreateForm = false"
            @close="showCreateForm = false"
          />
        </div>

        <div>
          <div v-if="isLoadingFeed && feedPosts.length === 0" class="text-center py-10">
            <p class="text-gray-500 dark:text-gray-400">Loading your feed...</p>
          </div>

          <div v-else-if="!isLoadingFeed && feedPosts.length === 0" class="text-center py-10 bg-white dark:bg-gray-800 rounded-lg shadow-md">
            <h3 class="text-lg font-semibold text-gray-700 dark:text-gray-200">Your Feed is Empty</h3>
            <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
              Follow people or create your first post to see content here.
            </p>
          </div>

          <div v-else class="space-y-4">
            <PostCard
              v-for="post in feedPosts"
              :key="post.id"
              :post="post"
            />
          </div>
        </div>
      </div>
    </div>  
    <DmFooter v-if="canChat" />
  </div>
</template>
