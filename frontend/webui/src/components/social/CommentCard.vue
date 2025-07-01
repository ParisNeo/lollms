<script setup>
import { computed } from 'vue';
import { marked } from 'marked';
import { useAuthStore } from '../../stores/auth';
import { useSocialStore } from '../../stores/social';
import UserAvatar from '../ui/UserAvatar.vue';

const props = defineProps({
  comment: {
    type: Object,
    required: true,
  },
});

const authStore = useAuthStore();
const socialStore = useSocialStore();

const isAuthor = computed(() => authStore.user?.id === props.comment.author.id);
const isAdmin = computed(() => authStore.user?.is_admin === true);

const formattedContent = computed(() => {
  return marked.parse(props.comment.content, { gfm: true, breaks: true });
});

function formatTimestamp(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const diff = Math.round((now - date) / 1000); // Difference in seconds

  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 2592000) return `${Math.floor(diff / 86400)}d ago`;

  return date.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

async function handleDelete() {
  if (confirm('Are you sure you want to delete this comment?')) {
    // Assuming the store will be updated with a deleteComment action
    // await socialStore.deleteComment(props.comment.id);
    console.log("Deleting comment:", props.comment.id)
  }
}
</script>

<template>
  <div class="flex space-x-3 py-2">
    <!-- Avatar -->
    <div class="flex-shrink-0">
      <router-link :to="`/profile/${comment.author.username}`">
        <UserAvatar :icon="comment.author.icon" :username="comment.author.username" size-class="h-8 w-8" />
      </router-link>
    </div>

    <!-- Comment Content -->
    <div class="flex-1 min-w-0">
      <div class="bg-gray-100 dark:bg-gray-700 rounded-xl p-3">
        <div class="flex justify-between items-center">
          <router-link :to="`/profile/${comment.author.username}`" class="font-bold text-sm text-gray-900 dark:text-gray-100 hover:underline">
            {{ comment.author.username }}
          </router-link>
          
          <button v-if="isAuthor || isAdmin" @click="handleDelete" class="text-gray-400 hover:text-red-500" title="Delete comment">
             <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>
          </button>
        </div>
        <div class="mt-1 prose prose-sm dark:prose-invert max-w-none" v-html="formattedContent"></div>
      </div>
      <div class="pl-3 mt-1 text-xs text-gray-500 dark:text-gray-400">
        {{ formatTimestamp(comment.created_at) }}
      </div>
    </div>
  </div>
</template>