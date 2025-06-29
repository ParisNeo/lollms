<script setup>
import { onMounted, computed } from 'vue';
import { useSocialStore } from '../../stores/social';
import CreatePostForm from './CreatePostForm.vue';
import PostCard from './PostCard.vue';
import DmFooter from '../layout/DmFooter.vue';

const socialStore = useSocialStore();

const feedPosts = computed(() => socialStore.feedPosts);
const isLoading = computed(() => socialStore.isLoadingFeed);

// Fetch the feed when the component is first mounted
onMounted(() => {
  // Only fetch if the feed is empty to avoid redundant calls
  if (feedPosts.value.length === 0) {
    socialStore.fetchFeed();
  }
});
</script>

<template>
  <div class="flex-grow bg-gray-100 dark:bg-gray-900 overflow-y-auto">
    <div class="max-w-2xl mx-auto py-6 px-4">
      <!-- Page Header -->
      <h1 class="text-2xl font-bold text-gray-800 dark:text-gray-100 mb-6">
        Home Feed
      </h1>

      <!-- Post Creation Form -->
      <div class="mb-6">
        <CreatePostForm />
      </div>

      <!-- Feed Content -->
      <div>
        <!-- Loading State -->
        <div v-if="isLoading && feedPosts.length === 0" class="text-center py-10">
          <p class="text-gray-500 dark:text-gray-400">Loading your feed...</p>
        </div>

        <!-- Empty State -->
        <div v-else-if="!isLoading && feedPosts.length === 0" class="text-center py-10 bg-white dark:bg-gray-800 rounded-lg shadow-md">
          <h3 class="text-lg font-semibold text-gray-700 dark:text-gray-200">Your Feed is Empty</h3>
          <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Follow people or create your first post to see content here.
          </p>
        </div>

        <!-- Posts List -->
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
<DmFooter />
</template>