<script setup>
import { ref, computed, onMounted, defineAsyncComponent, nextTick } from 'vue';
import { useSocialStore } from '../../stores/social';
import { useAuthStore } from '../../stores/auth';
import UserAvatar from '../ui/Cards/UserAvatar.vue';

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
const commentInputRef = ref(null);

// --- MENTION STATE ---
const mentionQuery = ref('');
const mentionSuggestions = ref([]);
const isMentioning = ref(false);
let mentionDebounceTimer = null;
const mentionStartIndex = ref(-1);

const comments = computed(() => socialStore.getCommentsForPost(props.postId));
const isLoading = computed(() => socialStore.isLoadingComments[props.postId] ?? false);
const user = computed(() => authStore.user);
const canComment = computed(() => user.value && user.value.user_ui_level >= 2);

onMounted(() => {
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
        newCommentContent.value = '';
        isMentioning.value = false; 
    } catch(error) {
        // Error handled by store
    } finally {
        isSubmitting.value = false;
    }
}

// --- MENTION LOGIC ---
function handleInputForMentions(event) {
    const text = event.target.value;
    const cursorPosition = event.target.selectionStart;
    const textBeforeCursor = text.substring(0, cursorPosition);
    const atMatch = textBeforeCursor.match(/@(\w*)$/);

    if (atMatch) {
        mentionStartIndex.value = atMatch.index;
        const query = atMatch[1];
        mentionQuery.value = query;
        isMentioning.value = true;
        clearTimeout(mentionDebounceTimer);
        mentionDebounceTimer = setTimeout(async () => {
            if (mentionQuery.value === query) {
                mentionSuggestions.value = await socialStore.searchForMentions(query);
            }
        }, 200);
    } else {
        isMentioning.value = false;
        mentionSuggestions.value = [];
    }
}

function selectMention(user) {
    const beforeText = newCommentContent.value.substring(0, mentionStartIndex.value);
    const afterText = newCommentContent.value.substring(mentionStartIndex.value + mentionQuery.value.length + 1);
    const newText = `${beforeText}@${user.username} ${afterText}`;
    newCommentContent.value = newText;
    isMentioning.value = false;
    mentionSuggestions.value = [];
    nextTick(() => {
        const newCursorPos = beforeText.length + user.username.length + 2;
        commentInputRef.value.focus();
        commentInputRef.value.setSelectionRange(newCursorPos, newCursorPos);
    });
}
</script>

<template>
  <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
    <div v-if="isLoading && !comments" class="text-center py-4">
      <p class="text-sm text-gray-500 dark:text-gray-400">Loading comments...</p>
    </div>

    <div v-if="comments && comments.length > 0" class="space-y-2">
      <CommentCard 
        v-for="comment in comments" 
        :key="comment.id" 
        :comment="comment"
        :post-id="props.postId"
      />
    </div>

    <div v-if="!isLoading && comments && comments.length === 0" class="py-4 text-center">
        <p class="text-sm text-gray-500 dark:text-gray-400">No comments yet. Be the first to reply!</p>
    </div>

    <div v-if="canComment" class="mt-4 flex space-x-3 items-start">
      <div class="flex-shrink-0">
        <UserAvatar v-if="user" :icon="user.icon" :username="user.username || 'User'" size-class="h-8 w-8" />
      </div>
      <div class="flex-1 min-w-0 relative">
        <!-- MENTION POPUP -->
        <div v-if="isMentioning && mentionSuggestions.length > 0" class="absolute bottom-full left-0 right-0 mb-2 p-2 bg-white dark:bg-gray-900 border dark:border-gray-700 rounded-lg shadow-lg max-h-48 overflow-y-auto z-10">
          <ul>
            <li v-for="u in mentionSuggestions" :key="u.id" @click="selectMention(u)" class="flex items-center p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer">
              <UserAvatar :icon="u.icon" :username="u.username" size-class="h-6 w-6" />
              <span class="ml-2 text-sm font-medium">{{ u.username }}</span>
            </li>
          </ul>
        </div>
        <textarea
          ref="commentInputRef"
          v-model="newCommentContent"
          @input="handleInputForMentions"
          class="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-gray-50 dark:bg-gray-700 focus:ring-blue-500 focus:border-blue-500 transition text-sm"
          rows="2"
          placeholder="Write a comment..."
          @keydown.enter.exact.prevent="handleCommentSubmit"
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
