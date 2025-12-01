<script setup>
import { ref, computed, nextTick } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useSocialStore } from '../../stores/social';
import UserAvatar from '../ui/Cards/UserAvatar.vue';

const emit = defineEmits(['posted', 'close']);

const authStore = useAuthStore();
const socialStore = useSocialStore();

const content = ref('');
const visibility = ref('public');
const isSubmitting = ref(false);
const postInputRef = ref(null);

// --- MENTION STATE ---
const mentionQuery = ref('');
const mentionSuggestions = ref([]);
const isMentioning = ref(false);
let mentionDebounceTimer = null;
const mentionStartIndex = ref(-1);

const user = computed(() => authStore.user);

// --- DIRECTIVE: v-on-click-outside ---
const vOnClickOutside = {
  mounted(el, binding) {
    el.clickOutsideEvent = function(event) {
      if (!(el === event.target || el.contains(event.target))) {
        binding.value(event, el);
      }
    };
    document.body.addEventListener('click', el.clickOutsideEvent);
  },
  unmounted(el) {
    document.body.removeEventListener('click', el.clickOutsideEvent);
  },
};

const isPostDisabled = computed(() => {
  return isSubmitting.value || content.value.trim() === '';
});

async function handleSubmit() {
  if (isPostDisabled.value) return;

  isSubmitting.value = true;
  try {
    await socialStore.createPost({
      content: content.value,
      visibility: visibility.value,
    });
    content.value = '';
    visibility.value = 'public';
    isMentioning.value = false;
    emit('posted');
  } catch (error) {
    // Error notification is handled by the store
  } finally {
    isSubmitting.value = false;
  }
}

function handleCancel() {
  emit('close');
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
    const beforeText = content.value.substring(0, mentionStartIndex.value);
    const afterText = content.value.substring(mentionStartIndex.value + mentionQuery.value.length + 1);
    const newText = `${beforeText}@${user.username} ${afterText}`;
    content.value = newText;
    isMentioning.value = false;
    mentionSuggestions.value = [];
    nextTick(() => {
        const newCursorPos = beforeText.length + user.username.length + 2;
        postInputRef.value.focus();
        postInputRef.value.setSelectionRange(newCursorPos, newCursorPos);
    });
}

function closeMentionBox() {
    isMentioning.value = false;
}
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4">
    <div class="flex space-x-4">
      <div class="flex-shrink-0">
        <UserAvatar v-if="user" :icon="user.icon" :username="user.username || 'User'" size-class="h-10 w-10" />
      </div>

      <div class="flex-1 min-w-0 relative">
        <!-- MENTION POPUP -->
        <div v-if="isMentioning && mentionSuggestions.length > 0" v-on-click-outside="closeMentionBox" class="absolute bottom-full left-0 right-0 mb-2 p-2 bg-white dark:bg-gray-900 border dark:border-gray-700 rounded-lg shadow-lg max-h-48 overflow-y-auto z-10">
          <ul>
            <li v-for="u in mentionSuggestions" :key="u.id" @click="selectMention(u)" class="flex items-center p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer">
              <UserAvatar :icon="u.icon" :username="u.username" size-class="h-6 w-6" />
              <span class="ml-2 text-sm font-medium">{{ u.username }}</span>
            </li>
          </ul>
        </div>

        <textarea
          ref="postInputRef"
          v-model="content"
          @input="handleInputForMentions"
          placeholder="What's on your mind?"
          class="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 focus:ring-blue-500 focus:border-blue-500 transition text-sm"
          rows="4"
        ></textarea>
        
        <div class="mt-3 flex justify-between items-center">
          <div class="flex items-center space-x-2">
            <!-- Placeholder for future tools like image upload -->
          </div>

          <div class="flex items-center space-x-3">
            <select v-model="visibility" class="input-field !py-1.5 !px-2 text-sm">
              <option value="public">Public</option>
              <option value="followers">Followers Only</option>
              <option value="friends">Friends Only</option>
            </select>
            
            <button type="button" @click="handleCancel" class="btn btn-secondary">
              Cancel
            </button>

            <button
              @click="handleSubmit"
              :disabled="isPostDisabled"
              class="btn btn-primary"
            >
              {{ isSubmitting ? 'Posting...' : 'Post' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
