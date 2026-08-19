<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useSocialStore } from '../../stores/social';
import { useUiStore } from '../../stores/ui';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import CommentSection from './CommentSection.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';

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
const isEditing = ref(false);
const editContent = ref('');
const editVisibility = ref('public');
const isSubmittingEdit = ref(false);

const user = computed(() => authStore.user);
const isAdmin = computed(() => authStore.isAdmin);
const isAuthor = computed(() => user.value?.id === props.post.author?.id);
const canDelete = computed(() => isAuthor.value || user.value?.is_admin || user.value?.is_moderator);
const isBot = computed(() => props.post.is_ai_generated || props.post.author?.username?.toLowerCase() === 'lollms');

// Media Categorizers
const postImages = computed(() => (props.post.media || []).filter(m => m.type === 'image'));
const postVideos = computed(() => (props.post.media || []).filter(m => m.type === 'video'));
const postAudios = computed(() => (props.post.media || []).filter(m => m.type === 'audio'));
const postLinks = computed(() => (props.post.media || []).filter(m => m.type === 'link'));

function openImageLightbox(index) {
  const list = postImages.value.map(img => ({
    src: img.url,
    prompt: img.filename || `Image from ${props.post.author?.username}'s post`
  }));
  uiStore.openImageViewer({ imageList: list, startIndex: index });
}

const commentCount = computed(() => {
  const comments = socialStore.getCommentsForPost(props.post.id);
  return comments ? comments.length : (props.post.comments?.length || 0);
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
    editContent.value = props.post.content;
    editVisibility.value = props.post.visibility || 'public';
    isEditing.value = true;
    closeOptionsMenu();
}

async function handleSaveEdit() {
    if (!editContent.value.trim() || isSubmittingEdit.value) return;
    isSubmittingEdit.value = true;
    try {
        await socialStore.updatePost({
            postId: props.post.id,
            content: editContent.value.trim(),
            visibility: editVisibility.value
        });
        isEditing.value = false;
    } catch (err) {
        console.error("Failed to update post:", err);
    } finally {
        isSubmittingEdit.value = false;
    }
}

function handleCancelEdit() {
    isEditing.value = false;
    editContent.value = '';
}

async function handleTogglePin() {
    closeOptionsMenu();
    await socialStore.togglePinPost(props.post.id);
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
  <div 
    class="bg-white dark:bg-gray-800 rounded-2xl shadow-md border dark:border-gray-700/60 overflow-visible flex flex-col transition-all relative" 
    :class="[
      {'ring-2 ring-amber-500/40 border-amber-400 dark:border-amber-600 shadow-amber-500/5': post.is_pinned},
      {'z-30': isOptionsMenuOpen}
    ]"
  >

    <!-- Pinned / Featured Announcement Header -->
    <div v-if="post.is_pinned" class="rounded-t-2xl px-4 py-1.5 bg-gradient-to-r from-amber-500/15 via-orange-500/10 to-amber-500/5 dark:from-amber-500/20 dark:to-transparent border-b border-amber-300/40 dark:border-amber-700/40 flex items-center justify-between text-amber-800 dark:text-amber-300 select-none">
      <div class="flex items-center gap-2">
        <span class="text-xs">📌</span>
        <span class="text-[10px] font-black uppercase tracking-widest font-mono">Featured Announcement</span>
      </div>
      <span class="text-[9px] font-mono opacity-80 uppercase tracking-tighter">God Mode Pin</span>
    </div>

    <div class="p-4 flex space-x-4">
      <!-- Avatar Column -->
      <div class="shrink-0">
        <router-link :to="`/profile/${post.author?.username}`">
          <UserAvatar :icon="post.author?.icon" :username="post.author?.username" size-class="h-10 w-10" />
        </router-link>
      </div>

      <!-- Main Content Column -->
      <div class="flex-1 min-w-0">
        <!-- Post Header -->
        <div class="flex justify-between items-center mb-1">
          <div class="flex items-center flex-wrap gap-2">
            <router-link :to="`/profile/${post.author?.username}`" class="font-bold text-gray-900 dark:text-gray-100 hover:underline text-sm">
              {{ post.author?.username }}
            </router-link>

            <!-- AI Generated Tag Badge -->
            <span v-if="isBot" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 border border-purple-200 dark:border-purple-800 select-none shadow-xs">
              🤖 AI Generated
            </span>

            <span class="text-xs text-gray-500 dark:text-gray-400">
              · {{ formatTimestamp(post.created_at) }}
            </span>
          </div>

          <!-- Options Menu -->
          <div v-if="canDelete || isAdmin" class="relative options-menu-container z-30">
            <button @click.stop="toggleOptionsMenu" class="p-1.5 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" /></svg>
            </button>
            <div v-if="isOptionsMenuOpen" class="absolute right-0 mt-2 w-56 bg-white dark:bg-gray-900 rounded-xl shadow-2xl z-40 border dark:border-gray-700 py-1 overflow-hidden">
              <button v-if="isAuthor || isAdmin" @click="handleEdit" class="w-full text-left flex items-center px-4 py-2 text-xs font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-3 text-blue-500" viewBox="0 0 20 20" fill="currentColor"><path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" /><path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" /></svg>
                Edit Post
              </button>

              <button v-if="isAdmin" @click="handleTogglePin" class="w-full text-left flex items-center px-4 py-2 text-xs font-bold text-amber-600 dark:text-amber-400 hover:bg-gray-100 dark:hover:bg-gray-800">
                <span class="mr-3 text-sm">📌</span>
                {{ post.is_pinned ? 'Unpin Announcement' : 'Feature / Pin to Top' }}
              </button>

              <button @click="handleCopyMarkdown" class="w-full text-left flex items-center px-4 py-2 text-xs font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-3 text-gray-500" viewBox="0 0 20 20" fill="currentColor"><path d="M7 2a2 2 0 00-2 2v12a2 2 0 002 2h8a2 2 0 002-2V4a2 2 0 00-2-2H7zm0 2h8v12H7V4z"/><path d="M4 6a2 2 0 012-2h2v2H6v12h8v-2h2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6z"/></svg>
                Copy as Markdown
              </button>

              <div v-if="canDelete" class="border-t border-gray-100 dark:border-gray-800 my-1"></div>
              <button v-if="canDelete" @click="handleDelete" class="w-full text-left flex items-center px-4 py-2 text-xs font-bold text-red-600 hover:bg-red-50 dark:hover:bg-red-950/20">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-3" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>
                Delete Post
              </button>
            </div>
          </div>
        </div>

        <!-- Inline Post Edit Form -->
        <div v-if="isEditing" class="my-3 p-3 bg-gray-50 dark:bg-gray-900/60 rounded-xl border border-blue-200 dark:border-blue-800/50 space-y-3 animate-in fade-in">
          <textarea 
            v-model="editContent" 
            rows="4" 
            class="input-field w-full text-sm font-sans resize-none"
            placeholder="Edit your post content..."
          ></textarea>
          <div class="flex items-center justify-between">
            <select v-model="editVisibility" class="input-field !py-1 !text-xs">
              <option value="public">Public</option>
              <option value="followers">Followers Only</option>
              <option value="friends">Friends Only</option>
            </select>
            <div class="flex items-center gap-2">
              <button @click="handleCancelEdit" class="btn btn-secondary btn-sm" :disabled="isSubmittingEdit">Cancel</button>
              <button @click="handleSaveEdit" class="btn btn-primary btn-sm px-4" :disabled="isSubmittingEdit || !editContent.trim()">
                {{ isSubmittingEdit ? 'Saving...' : 'Save Changes' }}
              </button>
            </div>
          </div>
        </div>

        <!-- Post Content View -->
        <div v-else>
          <MessageContentRenderer :content="post.content" class="mt-2 prose prose-sm dark:prose-invert max-w-none" />

          <!-- Multi-Modal Media Rendering Pipeline (Images, Videos, Link Cards) -->
          <div v-if="post.media && post.media.length > 0" class="mt-4 space-y-3">
            <!-- 1. Embedded Image Gallery with Lightbox -->
            <div v-if="postImages.length > 0" class="grid gap-2" :class="postImages.length === 1 ? 'grid-cols-1 max-w-xl' : (postImages.length === 2 ? 'grid-cols-2' : 'grid-cols-2 sm:grid-cols-3')">
              <div 
                v-for="(img, iIdx) in postImages" 
                :key="iIdx" 
                @click="openImageLightbox(iIdx)"
                class="relative aspect-video sm:aspect-square rounded-xl overflow-hidden border border-gray-100 dark:border-gray-800 bg-black/5 dark:bg-black/40 cursor-pointer group/img shadow-sm"
              >
                <img :src="img.url" class="w-full h-full object-cover transition-transform duration-500 group-hover/img:scale-105" loading="lazy" />
                <div class="absolute inset-0 bg-black/20 opacity-0 group-hover/img:opacity-100 transition-opacity flex items-center justify-center">
                  <span class="text-white text-xs font-bold uppercase tracking-wider bg-black/60 px-2 py-1 rounded-lg backdrop-blur-sm">Zoom</span>
                </div>
              </div>
            </div>

            <!-- 2. Responsive Video Player -->
            <div v-for="(vid, vIdx) in postVideos" :key="'vid-'+vIdx" class="rounded-2xl overflow-hidden border border-gray-200 dark:border-gray-800 bg-black shadow-md max-w-2xl">
              <video 
                :src="vid.url" 
                controls 
                preload="metadata" 
                class="w-full max-h-[450px] object-contain mx-auto"
              ></video>
            </div>

            <!-- 3. Audio Player -->
            <div v-for="(aud, aIdx) in postAudios" :key="'aud-'+aIdx" class="p-3 bg-gray-50 dark:bg-gray-900/60 rounded-xl border border-gray-200 dark:border-gray-800 flex items-center gap-3">
              <span class="text-xl">🎵</span>
              <div class="flex-1 min-w-0">
                <span class="text-xs font-bold truncate block text-gray-800 dark:text-gray-200">{{ aud.filename || 'Audio Attachment' }}</span>
                <audio :src="aud.url" controls class="w-full h-8 mt-1"></audio>
              </div>
            </div>

            <!-- 4. Rich Link Cards -->
            <div v-for="(lnk, lIdx) in postLinks" :key="'lnk-'+lIdx" class="rounded-2xl overflow-hidden border border-gray-200 dark:border-gray-700 bg-gray-50/70 dark:bg-gray-900/50 hover:border-blue-500/50 transition-all shadow-sm group/link">
              <a :href="lnk.url" target="_blank" rel="noopener noreferrer" class="flex flex-col sm:flex-row gap-3 p-3.5 no-underline">
                <div v-if="lnk.image" class="w-full sm:w-32 h-24 rounded-xl overflow-hidden shrink-0 bg-gray-200 dark:bg-gray-800">
                  <img :src="lnk.image" class="w-full h-full object-cover group-hover/link:scale-105 transition-transform" />
                </div>
                <div class="min-w-0 flex-1 flex flex-col justify-center">
                  <span class="text-[9px] font-black uppercase tracking-wider text-blue-600 dark:text-blue-400">{{ lnk.domain || 'External Link' }}</span>
                  <h4 class="text-sm font-bold text-gray-900 dark:text-gray-100 truncate mt-0.5 group-hover/link:text-blue-600 transition-colors">{{ lnk.title || lnk.url }}</h4>
                  <p v-if="lnk.description" class="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 mt-1 leading-relaxed">{{ lnk.description }}</p>
                </div>
              </a>
            </div>
          </div>
        </div>

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
