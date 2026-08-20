<script setup>
import { ref, computed, onMounted, nextTick } from 'vue';
import { useSocialStore } from '../../stores/social';
import { useAuthStore } from '../../stores/auth';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
// Changed from async import to static to prevent chunk loading errors
import CommentCard from './CommentCard.vue';

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

// --- MENTION STATE & CARET POSITIONING ---
const mentionQuery = ref('');
const mentionSuggestions = ref([]);
const isMentioning = ref(false);
const selectedMentionIndex = ref(0);
const caretPosition = ref({ top: 35, left: 10, height: 20 });
let mentionDebounceTimer = null;
const mentionStartIndex = ref(-1);

const mirrorProps = [
  'boxSizing', 'width', 'height', 'overflowX', 'overflowY',
  'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth',
  'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
  'fontStyle', 'fontVariant', 'fontWeight', 'fontStretch', 'fontSize',
  'lineHeight', 'fontFamily', 'textAlign', 'textTransform', 'textIndent',
  'letterSpacing', 'wordSpacing'
];

function getCaretCoordinates(element, position) {
  const div = document.createElement('div');
  div.id = 'comment-textarea-caret-mirror';
  document.body.appendChild(div);

  const style = div.style;
  const computed = window.getComputedStyle(element);

  style.whiteSpace = 'pre-wrap';
  style.wordWrap = 'break-word';
  style.position = 'absolute';
  style.visibility = 'hidden';
  style.top = '0';
  style.left = '-9999px';

  mirrorProps.forEach(prop => {
    style[prop] = computed[prop];
  });

  div.textContent = element.value.substring(0, position);

  const span = document.createElement('span');
  span.textContent = element.value.substring(position) || '@';
  div.appendChild(span);

  const coordinates = {
    top: span.offsetTop + parseInt(computed.borderTopWidth || '0', 10) - element.scrollTop,
    left: span.offsetLeft + parseInt(computed.borderLeftWidth || '0', 10) - element.scrollLeft,
    height: parseInt(computed.lineHeight || computed.fontSize || '20', 10)
  };

  document.body.removeChild(div);
  return coordinates;
}

const comments = computed(() => socialStore.getCommentsForPost(props.postId));
const isLoading = computed(() => socialStore.isLoadingComments[props.postId] ?? false);
const user = computed(() => authStore.user);
const canComment = computed(() => user.value && user.value.user_ui_level >= 2);

onMounted(() => {
  // If comments are not already loaded in store, fetch them
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

// --- MENTION LOGIC WITH CARET TRACKING ---
function handleInputForMentions(event) {
    const text = event.target.value;
    const cursorPosition = event.target.selectionStart;
    const textBeforeCursor = text.substring(0, cursorPosition);
    const atMatch = textBeforeCursor.match(/@([a-zA-Z0-9_]*)$/);

    if (atMatch) {
        mentionStartIndex.value = atMatch.index;
        const query = atMatch[1] || '';
        mentionQuery.value = query;
        isMentioning.value = true;
        selectedMentionIndex.value = 0;

        if (commentInputRef.value) {
            try {
                const coords = getCaretCoordinates(commentInputRef.value, mentionStartIndex.value);
                const maxLeft = Math.max(0, commentInputRef.value.clientWidth - 260);
                caretPosition.value = {
                    top: coords.top + coords.height + 4,
                    left: Math.min(Math.max(8, coords.left), maxLeft),
                    height: coords.height
                };
            } catch (e) {
                caretPosition.value = { top: 35, left: 10, height: 20 };
            }
        }

        clearTimeout(mentionDebounceTimer);
        mentionDebounceTimer = setTimeout(async () => {
            if (mentionQuery.value === query) {
                mentionSuggestions.value = await socialStore.searchForMentions(query);
                selectedMentionIndex.value = 0;
            }
        }, 100);
    } else {
        isMentioning.value = false;
        mentionSuggestions.value = [];
    }
}

function handleCommentKeyDown(event) {
    if (isMentioning.value && mentionSuggestions.value.length > 0) {
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            selectedMentionIndex.value = (selectedMentionIndex.value + 1) % mentionSuggestions.value.length;
            return;
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            selectedMentionIndex.value = (selectedMentionIndex.value - 1 + mentionSuggestions.value.length) % mentionSuggestions.value.length;
            return;
        } else if (event.key === 'Tab' || (event.key === 'Enter' && !event.shiftKey)) {
            event.preventDefault();
            const targetUser = mentionSuggestions.value[selectedMentionIndex.value] || mentionSuggestions.value[0];
            if (targetUser) selectMention(targetUser);
            return;
        } else if (event.key === 'Escape') {
            event.preventDefault();
            isMentioning.value = false;
            return;
        }
    }

    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        handleCommentSubmit();
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
      <div class="shrink-0">
        <UserAvatar v-if="user" :icon="user.icon" :username="user.username || 'User'" size-class="h-8 w-8" />
      </div>
      <div class="flex-1 min-w-0 relative">
        <textarea
          ref="commentInputRef"
          v-model="newCommentContent"
          @input="handleInputForMentions"
          @keydown="handleCommentKeyDown"
          class="w-full p-2.5 border border-gray-300 dark:border-gray-600 rounded-xl bg-gray-50 dark:bg-gray-700 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition text-sm leading-relaxed"
          rows="2"
          placeholder="Write a comment..."
        ></textarea>

        <!-- DYNAMIC CARET-ALIGNED MENTION POPUP -->
        <div 
          v-if="isMentioning && mentionSuggestions.length > 0" 
          class="absolute p-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-2xl max-h-52 w-64 overflow-y-auto z-40 custom-scrollbar animate-in fade-in zoom-in-95 duration-150"
          :style="{ top: `${caretPosition.top}px`, left: `${caretPosition.left}px` }"
        >
          <div class="px-2 py-1 text-[9px] font-black uppercase tracking-wider text-gray-400 border-b dark:border-gray-800 mb-1">Mention user or bot</div>
          <ul class="space-y-0.5">
            <li 
              v-for="(u, idx) in mentionSuggestions" 
              :key="u.id" 
              @mousedown.prevent="selectMention(u)" 
              class="flex items-center p-2 rounded-xl cursor-pointer transition-colors"
              :class="selectedMentionIndex === idx ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300' : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-800 dark:text-gray-200'"
            >
              <UserAvatar :icon="u.icon" :username="u.username" size-class="h-6 w-6" />
              <span class="ml-2 text-xs font-bold truncate">{{ u.username }}</span>
              <span v-if="u.username.toLowerCase() === 'lollms'" class="ml-auto text-[9px] bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 px-1.5 py-0.5 rounded font-black uppercase shrink-0">
                AI Bot
              </span>
            </li>
          </ul>
        </div>
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
