<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue';
import { marked } from 'marked';
import { useAuthStore } from '../../stores/auth';
import { useSocialStore } from '../../stores/social';
import { useUiStore } from '../../stores/ui';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import CommentSection from './CommentSection.vue';

const props = defineProps({
  post: {
    type: Object,
    required: true,
  },
});

const authStore = useAuthStore();
const socialStore = useSocialStore();
const uiStore = useUiStore();

const isOptionsMenuOpen = ref(false);
const isCommentsVisible = ref(false);

const user = computed(() => authStore.user);
// Safe access to author properties
const isAuthor = computed(() => user.value?.id === props.post.author?.id);
const canDelete = computed(() => isAuthor.value || user.value?.is_admin || user.value?.is_moderator);

const commentCount = computed(() => {
  const comments = socialStore.getCommentsForPost(props.post.id);
  return comments ? comments.length : (props.post.comments?.length || 0);
});

const formattedContent = computed(() => {
  if (!props.post.content) return '';
  try {
      // Robust check for marked availability
      if (typeof marked === 'function') {
          return marked(props.post.content);
      } else if (marked && typeof marked.parse === 'function') {
          return marked.parse(props.post.content, { gfm: true, breaks: true });
      } else {
          // Fallback if marked is missing/broken
          return props.post.content.replace(/\n/g, '<br>');
      }
  } catch (e) {
      console.error("Markdown parsing error:", e);
      return props.post.content;
  }
});

function formatTimestamp(dateString) {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

function closeOptionsMenu() {
  isOptionsMenuOpen.value = false;
}
function handleLikeClick() {
    socialStore.toggleLike(props.post.id);
}
function handleClickOutside(event) {
  if (isOptionsMenuOpen.value && !event.target.closest('.options-menu-container')) {
    closeOptionsMenu();
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
});

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside);
});

function toggleOptionsMenu() {
  isOptionsMenuOpen.value = !isOptionsMenuOpen.value;
}

function handleEdit() {
    console.log("Editing post:", props.post.id);
    closeOptionsMenu();
}

async function handleDelete() {
    closeOptionsMenu();
    if (confirm('Are you sure you want to delete this post?')) {
        await socialStore.deletePost(props.post.id);
    }
}

function handleCopyMarkdown() {
  navigator.clipboard.writeText(props.post.content).then(() => {
    uiStore.addNotification('Markdown copied to clipboard!', 'copy');
  }).catch(err => {
    uiStore.addNotification('Failed to copy markdown.', 'error');
  });
  closeOptionsMenu();
}

async function handleShare() {
  const shareData = {
    title: `Post by ${props.post.author?.username}`,
    text: `Check out this post by ${props.post.author?.username}`,
    url: window.location.origin + `/posts/${props.post.id}`
  };
  if (navigator.share && navigator.canShare(shareData)) {
    try { await navigator.share(shareData); } catch (err) { if (err.name !== 'AbortError') console.error('Share failed:', err); }
  } else {
    navigator.clipboard.writeText(shareData.url).then(() => {
      uiStore.addNotification('Post link copied to clipboard!', 'copy');
    }).catch(err => {
      uiStore.addNotification('Failed to copy link.', 'error');
    });
  }
}

function toggleComments() {
  isCommentsVisible.value = !isCommentsVisible.value;
}
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md flex flex-col">
    <div class="p-4 flex space-x-4">
      <!-- Avatar Column -->
      <div class="flex-shrink-0">
        <router-link :to="`/profile/${post.author?.username}`">
          <UserAvatar :icon="post.author?.icon" :username="post.author?.username" size-class="h-10 w-10" />
        </router-link>
      </div>

      <!-- Main Content Column -->
      <div class="flex-1 min-w-0">
        <!-- Post Header -->
        <div class="flex justify-between items-center">
          <div>
            <router-link :to="`/profile/${post.author?.username}`" class="font-bold text-gray-900 dark:text-gray-100 hover:underline">
              {{ post.author?.username }}
            </router-link>
            <span class="text-sm text-gray-500 dark:text-gray-400 ml-2">
              · {{ formatTimestamp(post.created_at) }}
            </span>
          </div>
          
          <!-- Options Menu -->
          <div v-if="canDelete" class="relative options-menu-container">
            <button @click.stop="toggleOptionsMenu"  class="p-1 rounded-full text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" /></svg>
            </button>
            <div v-if="isOptionsMenuOpen" class="absolute right-0 mt-2 w-56 bg-white dark:bg-gray-900 rounded-md shadow-lg z-10 border dark:border-gray-700">
              <div class="py-1">
                <button v-if="isAuthor" @click="handleEdit" class="w-full text-left flex items-center px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-3" viewBox="0 0 20 20" fill="currentColor"><path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" /><path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" /></svg>
                  Edit Post
                </button>
                <button @click="handleCopyMarkdown" class="w-full text-left flex items-center px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-3" viewBox="0 0 20 20" fill="currentColor"><path d="M7 2a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V4a2 2 0 00-2-2H7zm0 2h8v12H7V4z"/><path d="M4 6a2 2 0 012-2h2v2H6v12h8v-2h2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6z"/></svg>
                  Copy as Markdown
                </button>
                <div v-if="canDelete" class="border-t border-gray-100 dark:border-gray-800 my-1"></div>
                <button v-if="canDelete" @click="handleDelete" class="w-full text-left flex items-center px-4 py-2 text-sm text-red-600 hover:bg-gray-100 dark:hover:bg-gray-800">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-3" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>
                  Delete Post
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Post Content -->
        <div class="mt-2 prose prose-sm dark:prose-invert max-w-none" v-html="formattedContent"></div>

        <!-- Action Buttons -->
        <div class="mt-4 flex justify-between text-gray-500">
          <button @click="handleLikeClick" class="flex items-center space-x-2 hover:text-blue-500 transition-colors" :class="{'text-blue-600 dark:text-blue-400 font-semibold': post.has_liked}">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" :fill="post.has_liked ? 'currentColor' : 'none'" :stroke="post.has_liked ? 'none' : 'currentColor'" stroke-width="1.5"><path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0016.556 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" /></svg>
            <span>{{ post.has_liked ? 'Liked' : 'Like' }}</span>
            <span v-if="post.like_count > 0" class="text-xs font-bold">{{ post.like_count }}</span>
          </button>
          
          <button @click="toggleComments" class="flex items-center space-x-2 hover:text-green-500 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 5v8a2 2 0 01-2 2h-5l-5 4v-4H4a2 2 0 01-2-2V5a2 2 0 012-2h12a2 2 0 012 2zM7 8H5v2h2V8zm2 0h2v2H9V8zm6 0h-2v2h2V8z" clip-rule="evenodd" /></svg>
            <span>Comment</span>
            <span v-if="commentCount > 0" class="text-xs font-bold">{{ commentCount }}</span>
          </button>
          
          <button @click="handleShare" class="flex items-center space-x-2 hover:text-purple-500 transition-colors">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path d="M15 8a3 3 0 10-2.977-2.63l-4.94 2.47a3 3 0 100 4.319l4.94 2.47a3 3 0 10.895-1.789l-4.94-2.47a3.027 3.027 0 000-.74l4.94-2.47C13.456 7.68 14.19 8 15 8z" /></svg>
            <span>Share</span>
          </button>
        </div>
      </div>
    </div>
    
    <!-- Comment Section (conditionally rendered) -->
    <div v-if="isCommentsVisible" class="px-4 pb-2">
       <CommentSection :post-id="post.id" />
    </div>
  </div>
</template>
