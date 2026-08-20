<script setup>
import { ref, computed, nextTick } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useSocialStore } from '../../stores/social';
import { useUiStore } from '../../stores/ui';
import UserAvatar from '../ui/Cards/UserAvatar.vue';

// Icons
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const emit = defineEmits(['posted', 'close']);

const authStore = useAuthStore();
const socialStore = useSocialStore();
const uiStore = useUiStore();

const content = ref('');
const visibility = ref('public');
const isPinned = ref(false);
const isSubmitting = ref(false);
const isUploadingMedia = ref(false);
const isFetchingLink = ref(false);
const postInputRef = ref(null);
const fileInputRef = ref(null);

const stagedFiles = ref([]); // Raw File objects with preview URLs
const attachedMedia = ref([]); // Uploaded or link preview media objects
const linkInputUrl = ref('');
const isLinkInputOpen = ref(false);

const isAdmin = computed(() => authStore.isAdmin);
const user = computed(() => authStore.user);

// --- MENTION STATE ---
const mentionQuery = ref('');
const mentionSuggestions = ref([]);
const isMentioning = ref(false);
let mentionDebounceTimer = null;
const mentionStartIndex = ref(-1);

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
  return isSubmitting.value || isUploadingMedia.value || (content.value.trim() === '' && stagedFiles.value.length === 0 && attachedMedia.value.length === 0);
});

// File Selection
function triggerFilePicker() {
  fileInputRef.value?.click();
}

function handleFileSelection(event) {
  const files = Array.from(event.target.files || []);
  for (const file of files) {
    if (stagedFiles.value.length >= 10) {
      uiStore.addNotification('Maximum 10 attachments per post.', 'warning');
      break;
    }
    const isImage = file.type.startsWith('image/');
    const isVideo = file.type.startsWith('video/');
    const isAudio = file.type.startsWith('audio/');

    if (!isImage && !isVideo && !isAudio) {
      uiStore.addNotification(`Unsupported file type: ${file.name}`, 'error');
      continue;
    }

    stagedFiles.value.push({
      file,
      type: isImage ? 'image' : (isVideo ? 'video' : 'audio'),
      previewUrl: URL.createObjectURL(file),
      name: file.name
    });
  }
  event.target.value = '';
}

function removeStagedFile(index) {
  const removed = stagedFiles.value.splice(index, 1)[0];
  if (removed?.previewUrl) URL.revokeObjectURL(removed.previewUrl);
}

function removeAttachedMedia(index) {
  attachedMedia.value.splice(index, 1);
}

// Link Preview Resolver
async function handleAttachLink() {
  const target = linkInputUrl.value.trim();
  if (!target) return;

  if (!target.startsWith('http://') && !target.startsWith('https://')) {
    uiStore.addNotification('Please provide a full URL starting with http:// or https://', 'warning');
    return;
  }

  isFetchingLink.value = true;
  try {
    const preview = await socialStore.fetchLinkPreview(target);
    if (preview) {
      attachedMedia.value.push({
        type: 'link',
        ...preview
      });
      linkInputUrl.value = '';
      isLinkInputOpen.value = false;
    } else {
      uiStore.addNotification('Could not extract preview for this link.', 'warning');
    }
  } finally {
    isFetchingLink.value = false;
  }
}

async function handleSubmit() {
  if (isPostDisabled.value) return;

  isSubmitting.value = true;
  try {
    let finalMedia = [...attachedMedia.value];

    // 1. Upload any staged files first through safe endpoint
    if (stagedFiles.value.length > 0) {
      isUploadingMedia.value = true;
      const rawFiles = stagedFiles.value.map(s => s.file);
      const uploaded = await socialStore.uploadPostMedia(rawFiles);
      finalMedia.push(...uploaded);
    }

    // 2. Submit post
    await socialStore.createPost({
      content: content.value.trim(),
      visibility: visibility.value,
      is_pinned: isPinned.value,
      media: finalMedia.length > 0 ? finalMedia : null
    });

    // 3. Reset form
    stagedFiles.value.forEach(s => URL.revokeObjectURL(s.previewUrl));
    stagedFiles.value = [];
    attachedMedia.value = [];
    content.value = '';
    visibility.value = 'public';
    isPinned.value = false;
    isMentioning.value = false;
    emit('posted');
  } catch (error) {
    // Error notification handled by store
  } finally {
    isSubmitting.value = false;
    isUploadingMedia.value = false;
  }
}

function handleCancel() {
  stagedFiles.value.forEach(s => URL.revokeObjectURL(s.previewUrl));
  stagedFiles.value = [];
  attachedMedia.value = [];
  emit('close');
}

// Mentions
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
    clearTimeout(mentionDebounceTimer);
    mentionDebounceTimer = setTimeout(async () => {
      if (mentionQuery.value === query) {
        mentionSuggestions.value = await socialStore.searchForMentions(query);
      }
    }, 100);
  } else {
    isMentioning.value = false;
    mentionSuggestions.value = [];
  }
}

function selectMention(u) {
  const beforeText = content.value.substring(0, mentionStartIndex.value);
  const afterText = content.value.substring(mentionStartIndex.value + mentionQuery.value.length + 1);
  content.value = `${beforeText}@${u.username} ${afterText}`;
  isMentioning.value = false;
  mentionSuggestions.value = [];
  nextTick(() => {
    const newCursorPos = beforeText.length + u.username.length + 2;
    postInputRef.value.focus();
    postInputRef.value.setSelectionRange(newCursorPos, newCursorPos);
  });
}
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-md p-4 border border-gray-100 dark:border-gray-700/60">
    <div class="flex space-x-4">
      <div class="shrink-0">
        <UserAvatar v-if="user" :icon="user.icon" :username="user.username || 'User'" size-class="h-10 w-10" />
      </div>

      <div class="flex-1 min-w-0 relative">
        <!-- MENTION POPUP -->
        <div v-if="isMentioning && mentionSuggestions.length > 0" v-on-click-outside="() => isMentioning = false" class="absolute bottom-full left-0 right-0 mb-2 p-2 bg-white dark:bg-gray-900 border dark:border-gray-700 rounded-xl shadow-2xl max-h-52 overflow-y-auto z-30">
          <ul>
            <li v-for="u in mentionSuggestions" :key="u.id" @mousedown.prevent="selectMention(u)" class="flex items-center p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer transition-colors">
              <UserAvatar :icon="u.icon" :username="u.username" size-class="h-6 w-6" />
              <span class="ml-2 text-xs font-bold text-gray-800 dark:text-gray-200">{{ u.username }}</span>
              <span v-if="u.username.toLowerCase() === 'lollms'" class="ml-2 text-[9px] bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 px-1.5 py-0.5 rounded font-black uppercase">
                AI Bot
              </span>
            </li>
          </ul>
        </div>

        <textarea
          ref="postInputRef"
          v-model="content"
          @input="handleInputForMentions"
          placeholder="Share your thoughts, findings, images, videos or links with the community..."
          class="w-full p-3 border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-50/50 dark:bg-gray-900/50 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition text-sm resize-none leading-relaxed"
          rows="3"
        ></textarea>

        <!-- Staged File Previews & Attached Links Area -->
        <div v-if="stagedFiles.length > 0 || attachedMedia.length > 0" class="my-3 space-y-2">
          <!-- Image/Video Grid Previews -->
          <div class="flex flex-wrap gap-2.5">
            <div 
              v-for="(staged, idx) in stagedFiles" 
              :key="idx" 
              class="relative w-20 h-20 rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-900 group shadow-xs"
            >
              <img v-if="staged.type === 'image'" :src="staged.previewUrl" class="w-full h-full object-cover" />
              <div v-else-if="staged.type === 'video'" class="w-full h-full flex flex-col items-center justify-center bg-gray-900 text-white p-1">
                <span class="text-xs">🎬</span>
                <span class="text-[8px] font-mono truncate w-full text-center">{{ staged.name }}</span>
              </div>
              <div v-else class="w-full h-full flex flex-col items-center justify-center bg-gray-800 text-white p-1">
                <span class="text-xs">🎵</span>
                <span class="text-[8px] font-mono truncate w-full text-center">{{ staged.name }}</span>
              </div>
              <button @click.stop="removeStagedFile(idx)" class="absolute top-1 right-1 bg-black/70 hover:bg-red-600 text-white rounded-full w-4 h-4 flex items-center justify-center text-[10px] transition-colors" title="Remove attachment">
                ×
              </button>
            </div>
          </div>

          <!-- Attached OpenGraph Link Previews -->
          <div v-for="(media, mIdx) in attachedMedia" :key="'media-'+mIdx" class="relative group/linkcard p-3 rounded-xl bg-blue-50/50 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900/40 flex items-center gap-3">
            <div v-if="media.image" class="w-12 h-12 rounded-lg overflow-hidden shrink-0 bg-gray-200">
              <img :src="media.image" class="w-full h-full object-cover" />
            </div>
            <div class="min-w-0 flex-1">
              <span class="text-[9px] font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wide">{{ media.domain }}</span>
              <p class="text-xs font-bold truncate text-gray-800 dark:text-gray-200">{{ media.title || media.url }}</p>
              <p v-if="media.description" class="text-[10px] text-gray-500 truncate">{{ media.description }}</p>
            </div>
            <button @click="removeAttachedMedia(mIdx)" class="text-gray-400 hover:text-red-500 p-1" title="Remove link">
              <IconXMark class="w-4 h-4" />
            </button>
          </div>
        </div>

        <!-- Inline Link Input Drawer -->
        <div v-if="isLinkInputOpen" class="my-2.5 p-3 rounded-xl bg-gray-50 dark:bg-gray-900/60 border border-gray-200 dark:border-gray-700 flex items-center gap-2 animate-in fade-in">
          <IconGlobeAlt class="w-4 h-4 text-blue-500 shrink-0" />
          <input 
            v-model="linkInputUrl" 
            @keyup.enter="handleAttachLink"
            placeholder="Paste article or web link (https://...)" 
            class="input-field !py-1 text-xs grow"
            :disabled="isFetchingLink"
          />
          <button @click="handleAttachLink" class="btn btn-primary btn-xs py-1.5 px-3" :disabled="isFetchingLink || !linkInputUrl.trim()">
            <IconAnimateSpin v-if="isFetchingLink" class="w-3.5 h-3.5 animate-spin mr-1" />
            <span>Attach Link</span>
          </button>
          <button @click="isLinkInputOpen = false" class="p-1 text-gray-400 hover:text-red-500">
            <IconXMark class="w-4 h-4" />
          </button>
        </div>

        <!-- Footer Control Bar -->
        <div class="mt-3 flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-gray-100 dark:border-gray-700/60">
          <div class="flex items-center gap-2">
            <!-- Media Attach Trigger -->
            <button @click="triggerFilePicker" class="btn btn-secondary btn-xs py-1.5 px-2.5 flex items-center gap-1.5" title="Attach image, video (MP4/WebM), or audio">
              <IconPhoto class="w-4 h-4 text-purple-500" />
              <span class="text-xs">Photo/Video</span>
            </button>
            <input ref="fileInputRef" type="file" @change="handleFileSelection" multiple accept="image/*,video/mp4,video/webm,video/ogg,audio/*" class="hidden" />

            <!-- Link Attach Trigger -->
            <button @click="isLinkInputOpen = !isLinkInputOpen" class="btn btn-secondary btn-xs py-1.5 px-2.5 flex items-center gap-1.5" title="Attach rich link preview">
              <IconGlobeAlt class="w-4 h-4 text-blue-500" />
              <span class="text-xs">Link</span>
            </button>
          </div>

          <div class="flex items-center gap-3">
            <label v-if="isAdmin" class="flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg text-xs font-bold text-amber-700 dark:text-amber-300 cursor-pointer select-none" title="Pin announcement to top of feed">
              <input type="checkbox" v-model="isPinned" class="rounded text-amber-600 focus:ring-amber-500 w-3.5 h-3.5" />
              <span>📌 Feature (Admin)</span>
            </label>

            <select v-model="visibility" class="input-field !py-1.5 !px-2 text-xs">
              <option value="public">Public</option>
              <option value="followers">Followers Only</option>
              <option value="friends">Friends Only</option>
            </select>

            <button type="button" @click="handleCancel" class="btn btn-secondary btn-sm">
              Cancel
            </button>

            <button
              @click="handleSubmit"
              :disabled="isPostDisabled"
              class="btn btn-primary btn-sm px-5 flex items-center gap-2"
            >
              <IconAnimateSpin v-if="isSubmitting || isUploadingMedia" class="w-4 h-4 animate-spin" />
              <span>{{ isUploadingMedia ? 'Uploading...' : (isSubmitting ? 'Posting...' : 'Post') }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
