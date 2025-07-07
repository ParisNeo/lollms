<script setup>
import { ref, computed, onMounted, defineAsyncComponent } from 'vue'; // Import defineAsyncComponent
import { useSocialStore } from '../../stores/social';
import { useAuthStore } from '../../stores/auth';
import UserAvatar from '../ui/UserAvatar.vue';

// Dynamically import CommentCard to break any potential circular dependency issues
// that can arise with HMR (Hot Module Replacement) in development.
const CommentCard = defineAsyncComponent(() => import('./CommentCard.vue'));

const props = defineProps({
  postId: {
    type: Number,
    required: true,
  },
});

const socialStore = useSocialStore();
const authStore = useAuthStore();

const newCommentContent = ref('');
const isSubmitting = ref(false);

const comments = computed(() => socialStore.getCommentsForPost(props.postId));
const isLoading = computed(() => socialStore.isLoadingComments[props.postId] ?? false);
const user = computed(() => authStore.user);
const canComment = computed(() => user.value && user.value.user_ui_level >= 2);

onMounted(() => {
  // Fetch comments only if they haven't been fetched yet
  if (!comments.value) {
    socialStore.fetchComments(props.postId);
  }
});

const isSubmitDisabled = computed(() => {
    return isSubmitting.value || newCommentContent.value.trim() === '';
});

async function handleCommentSubmit() {
    if (isSubmitDisabled.value) return;

    isSubmitting.value = true;
    try {
        await socialStore.createComment({
            postId: props.postId,
            content: newCommentContent.value,
        });
        newCommentContent.value = ''; // Reset form on success
    } catch(error) {
        // Error is handled by the store's notification system
    } finally {
        isSubmitting.value = false;
    }
}
</script>

<template>
  <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
    <!-- Loading State -->
    <div v-if="isLoading && !comments" class="text-center py-4">
      <p class="text-sm text-gray-500 dark:text-gray-400">Loading comments...</p>
    </div>

    <!-- Comments List -->
    <div v-if="comments && comments.length > 0" class="space-y-2">
      <CommentCard 
        v-for="comment in comments" 
        :key="comment.id" 
        :comment="comment" 
      />
    </div>

    <!-- Empty State -->
    <div v-if="!isLoading && comments && comments.length === 0" class="py-4 text-center">
        <p class="text-sm text-gray-500 dark:text-gray-400">No comments yet. Be the first to reply!</p>
    </div>

    <!-- New Comment Form -->
    <div v-if="canComment" class="mt-4 flex space-x-3 items-start">
      <div class="flex-shrink-0">
        <UserAvatar v-if="user" :icon="user.icon" :username="user.username" size-class="h-8 w-8" />
      </div>
      <div class="flex-1 min-w-0">
        <textarea
          v-model="newCommentContent"
          class="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-gray-50 dark:bg-gray-700 focus:ring-blue-500 focus:border-blue-500 transition text-sm"
          rows="2"
          placeholder="Write a comment..."
          @keydown.enter.prevent="handleCommentSubmit"
        ></textarea>
        <div class="mt-2 flex justify-end">
            <button
                @click="handleCommentSubmit"
                :disabled="isSubmitDisabled"
                class="btn btn-primary btn-sm"
            >
                {{ isSubmitting ? 'Replying...' : 'Reply' }}
            </button>
        </div>
      </div>
    </div>
  </div>
</template>
