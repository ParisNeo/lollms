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
import IconYoutube from '../../assets/icons/IconYoutube.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';

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

const youtubeInputUrl = ref('');
const isYoutubeInputOpen = ref(false);

// AI Post Generation Modal & State
const isAiDraftModalOpen = ref(false);
const isGeneratingAiPost = ref(false);
const aiTopicPrompt = ref('');
const aiUseWebSearch = ref(true);
const aiSearchProvider = ref('ddg');
const aiTone = ref('engaging');
const aiIncludeHashtags = ref(true);
const lastGeneratedSources = ref([]);
const lastToolsUsed = ref([]);

const isAdmin = computed(() => authStore.isAdmin);
const user = computed(() => authStore.user);

// --- MENTION & CARET POSITIONING STATE ---
const mentionQuery = ref('');
const mentionSuggestions = ref([]);
const isMentioning = ref(false);
const selectedMentionIndex = ref(0);
const caretPosition = ref({ top: 40, left: 10, height: 20 });
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
  div.id = 'input-textarea-caret-mirror';
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

function handleEmbedYoutube() {
  const target = youtubeInputUrl.value.trim();
  if (!target) return;

  const listMatch = target.match(/[?&]list=([a-zA-Z0-9_-]{12,64})/i);
  const urlMatch = target.match(/(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?|shorts)\/|.*[?&]v=)|youtu\.be\/|youtube-nocookie\.com\/embed\/)([a-zA-Z0-9_-]{11})/i);
  const isDirectId = /^[a-zA-Z0-9_-]{11}$/.test(target);

  if (!urlMatch && !isDirectId && !listMatch) {
    uiStore.addNotification('Please enter a valid YouTube video URL, playlist link, or video ID.', 'warning');
    return;
  }

  let youtubeTag = '';
  if (listMatch && !urlMatch && !isDirectId) {
    youtubeTag = `\n<youtube>https://www.youtube.com/playlist?list=${listMatch[1]}</youtube>\n`;
  } else {
    const videoId = isDirectId ? target : urlMatch[1];
    const listParam = listMatch ? `&list=${listMatch[1]}` : '';
    youtubeTag = `\n<youtube>https://www.youtube.com/watch?v=${videoId}${listParam}</youtube>\n`;
  }

  content.value = (content.value.trim() ? content.value.trim() + '\n' : '') + youtubeTag;
  youtubeInputUrl.value = '';
  isYoutubeInputOpen.value = false;
  uiStore.addNotification(listMatch && !urlMatch ? 'YouTube playlist embedded.' : 'YouTube video embedded into post.', 'success');
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

// AI Post Generator Trigger
function openAiPostModal() {
  if (content.value.trim() && !aiTopicPrompt.value) {
    aiTopicPrompt.value = content.value.trim();
  }
  isAiDraftModalOpen.value = true;
}

async function handleGenerateAiPost() {
  if (!aiTopicPrompt.value.trim()) {
    uiStore.addNotification('Please provide a topic or prompt for LoLLMs.', 'warning');
    return;
  }

  isGeneratingAiPost.value = true;
  lastGeneratedSources.value = [];
  lastToolsUsed.value = [];

  try {
    const res = await socialStore.generatePostDraft({
      topic: aiTopicPrompt.value.trim(),
      use_websearch: aiUseWebSearch.value,
      search_provider: aiSearchProvider.value,
      tone: aiTone.value,
      include_hashtags: aiIncludeHashtags.value
    });

    if (res && res.content) {
      content.value = res.content;
      lastGeneratedSources.value = res.sources || [];
      lastToolsUsed.value = res.tools_used || [];
      isAiDraftModalOpen.value = false;
      uiStore.addNotification('Post draft generated by LoLLMs!', 'success');
      nextTick(() => {
        postInputRef.value?.focus();
      });
    }
  } catch (err) {
    console.error('AI draft generation failed:', err);
  } finally {
    isGeneratingAiPost.value = false;
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

// Mentions with Caret Coordinate Tracking
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

    // Calculate exact pixel position below the cursor
    if (postInputRef.value) {
      try {
        const coords = getCaretCoordinates(postInputRef.value, mentionStartIndex.value);
        const maxLeft = Math.max(0, postInputRef.value.clientWidth - 290);
        caretPosition.value = {
          top: coords.top + coords.height + 6,
          left: Math.min(Math.max(8, coords.left), maxLeft),
          height: coords.height
        };
      } catch (e) {
        caretPosition.value = { top: 40, left: 10, height: 20 };
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

function handleMentionKeyDown(event) {
  if (isMentioning.value && mentionSuggestions.value.length > 0) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      selectedMentionIndex.value = (selectedMentionIndex.value + 1) % mentionSuggestions.value.length;
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      selectedMentionIndex.value = (selectedMentionIndex.value - 1 + mentionSuggestions.value.length) % mentionSuggestions.value.length;
    } else if (event.key === 'Enter' || event.key === 'Tab') {
      event.preventDefault();
      const targetUser = mentionSuggestions.value[selectedMentionIndex.value] || mentionSuggestions.value[0];
      if (targetUser) {
        selectMention(targetUser);
      }
    } else if (event.key === 'Escape') {
      event.preventDefault();
      isMentioning.value = false;
    }
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

      <div class="flex-1 min-w-0">
        <!-- Relative Textarea Container with Inline Caret Popover -->
        <div class="relative">
          <textarea
            ref="postInputRef"
            v-model="content"
            @input="handleInputForMentions"
            @keydown="handleMentionKeyDown"
            placeholder="Share your thoughts, findings, images, videos or links with the community..."
            class="w-full p-3 border border-gray-200 dark:border-gray-700 rounded-xl bg-gray-50/50 dark:bg-gray-900/50 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition text-sm resize-none leading-relaxed"
            rows="3"
          ></textarea>

          <!-- DYNAMIC CARET-ALIGNED MENTION POPUP -->
          <div 
            v-if="isMentioning && mentionSuggestions.length > 0" 
            v-on-click-outside="() => isMentioning = false" 
            class="absolute p-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-2xl max-h-56 w-72 overflow-y-auto z-50 custom-scrollbar animate-in fade-in zoom-in-95 duration-150"
            :style="{ top: `${caretPosition.top}px`, left: `${caretPosition.left}px` }"
          >
            <div class="px-2 py-1 text-[9px] font-black uppercase tracking-wider text-gray-400 border-b dark:border-gray-800 mb-1">Mention user or bot</div>
            <ul class="space-y-0.5">
              <li 
                v-for="(u, idx) in mentionSuggestions" 
                :key="u.id" 
                @mousedown.prevent="selectMention(u)" 
                class="flex items-center p-2 rounded-xl cursor-pointer transition-colors"
                :class="selectedMentionIndex === idx ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300' : 'hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-800 dark:text-gray-200'"
              >
                <UserAvatar :icon="u.icon" :username="u.username" size-class="h-6 w-6" />
                <span class="ml-2 text-xs font-bold truncate">{{ u.username }}</span>
                <span v-if="u.username.toLowerCase() === 'lollms'" class="ml-auto text-[9px] bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 px-1.5 py-0.5 rounded font-black uppercase shrink-0">
                  AI Bot
                </span>
              </li>
            </ul>
          </div>
        </div>

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

        <!-- Inline YouTube Embed Input Drawer -->
        <div v-if="isYoutubeInputOpen" class="my-2.5 p-3 rounded-xl bg-red-50/50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/40 flex items-center gap-2 animate-in fade-in">
          <IconYoutube class="w-4 h-4 text-red-600 shrink-0" />
          <input 
            v-model="youtubeInputUrl" 
            @keyup.enter="handleEmbedYoutube"
            placeholder="Paste YouTube link (https://www.youtube.com/watch?v=... or https://youtu.be/...)" 
            class="input-field !py-1 text-xs grow"
          />
          <button @click="handleEmbedYoutube" class="btn bg-red-600 hover:bg-red-700 text-white btn-xs py-1.5 px-3" :disabled="!youtubeInputUrl.trim()">
            <span>Embed Video</span>
          </button>
          <button @click="isYoutubeInputOpen = false" class="p-1 text-gray-400 hover:text-red-500">
            <IconXMark class="w-4 h-4" />
          </button>
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
          <div class="flex items-center gap-2 flex-wrap">
            <!-- Ask LoLLMs to create post -->
            <button 
              @click="openAiPostModal" 
              type="button" 
              class="btn bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white btn-xs py-1.5 px-2.5 flex items-center gap-1.5 shadow-sm" 
              title="Ask LoLLMs to research and write a post with tools"
            >
              <IconSparkles class="w-4 h-4" />
              <span class="text-xs font-bold">Ask LoLLMs</span>
            </button>

            <!-- Media Attach Trigger -->
            <button @click="triggerFilePicker" class="btn btn-secondary btn-xs py-1.5 px-2.5 flex items-center gap-1.5" title="Attach image, video (MP4/WebM), or audio">
              <IconPhoto class="w-4 h-4 text-purple-500" />
              <span class="text-xs">Photo/Video</span>
            </button>
            <input ref="fileInputRef" type="file" @change="handleFileSelection" multiple accept="image/*,video/mp4,video/webm,video/ogg,audio/*" class="hidden" />

            <!-- YouTube Embed Trigger -->
            <button @click="isYoutubeInputOpen = !isYoutubeInputOpen; isLinkInputOpen = false;" class="btn btn-secondary btn-xs py-1.5 px-2.5 flex items-center gap-1.5" title="Embed a YouTube video player into this post">
              <IconYoutube class="w-4 h-4 text-red-500" />
              <span class="text-xs">YouTube</span>
            </button>

            <!-- Link Attach Trigger -->
            <button @click="isLinkInputOpen = !isLinkInputOpen; isYoutubeInputOpen = false;" class="btn btn-secondary btn-xs py-1.5 px-2.5 flex items-center gap-1.5" title="Attach rich link preview">
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

    <!-- AI POST CREATION MODAL / DRAWER -->
    <Teleport to="body">
      <div v-if="isAiDraftModalOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
        <div class="bg-white dark:bg-gray-800 w-full max-w-xl rounded-3xl shadow-2xl overflow-hidden border border-gray-100 dark:border-gray-700 animate-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">
          
          <!-- Header -->
          <div class="p-5 border-b dark:border-gray-700 flex justify-between items-center bg-gradient-to-r from-purple-600 to-indigo-600 text-white">
            <div class="flex items-center gap-2.5">
              <IconSparkles class="w-5 h-5 text-amber-300 animate-pulse" />
              <div>
                <h3 class="font-black text-base tracking-tight leading-none">Ask LoLLMs to Write Post</h3>
                <p class="text-[11px] opacity-80 mt-0.5">Use verified web search & AI tools to generate fact-backed posts</p>
              </div>
            </div>
            <button @click="isAiDraftModalOpen = false" class="p-1 hover:bg-white/20 rounded-full transition-colors">
              <IconXMark class="w-5 h-5" />
            </button>
          </div>

          <!-- Body -->
          <div class="p-6 space-y-5 overflow-y-auto custom-scrollbar grow">
            <div class="space-y-1.5">
              <label class="block text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                What should LoLLMs post about? *
              </label>
              <textarea 
                v-model="aiTopicPrompt" 
                rows="3" 
                class="input-field w-full text-sm leading-relaxed" 
                placeholder="e.g. Latest breakthroughs in quantum computing, summary of new release features, or explain how solar flares affect GPS..."
                :disabled="isGeneratingAiPost"
              ></textarea>
            </div>

            <!-- Tool Configurations -->
            <div class="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-2xl border dark:border-gray-700/80 space-y-3">
              <span class="text-[11px] font-black uppercase tracking-wider text-purple-700 dark:text-purple-300 flex items-center gap-1.5">
                <span>🔍 Research & Tool Backing</span>
              </span>

              <div class="flex items-center justify-between">
                <span class="text-xs font-bold text-gray-800 dark:text-gray-200">Enable Real-Time Web Search</span>
                <button 
                  type="button" 
                  @click="aiUseWebSearch = !aiUseWebSearch"
                  :class="[aiUseWebSearch ? 'bg-purple-600' : 'bg-gray-200 dark:bg-gray-700', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200']"
                >
                  <span :class="[aiUseWebSearch ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200']"></span>
                </button>
              </div>

              <!-- Provider selector if WebSearch enabled -->
              <div v-if="aiUseWebSearch" class="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t dark:border-gray-800 animate-in fade-in">
                <div>
                  <label class="block text-[10px] font-bold uppercase text-gray-400 mb-1">Search Engine / Tool</label>
                  <select v-model="aiSearchProvider" class="input-field !py-1 text-xs w-full">
                    <option value="ddg">DuckDuckGo Web Search</option>
                    <option value="google">Google Custom Search</option>
                    <option value="arxiv">ArXiv Academic Research</option>
                    <option value="all">Comprehensive (Web + ArXiv)</option>
                  </select>
                </div>
                <div>
                  <label class="block text-[10px] font-bold uppercase text-gray-400 mb-1">Writing Tone</label>
                  <select v-model="aiTone" class="input-field !py-1 text-xs w-full">
                    <option value="engaging">Engaging & Hook-Driven</option>
                    <option value="informative">Informative & Structured</option>
                    <option value="technical">Technical & In-Depth</option>
                    <option value="humorous">Witty & Lighthearted</option>
                    <option value="concise">Short & Punchy</option>
                  </select>
                </div>
              </div>

              <div class="flex items-center justify-between pt-1">
                <span class="text-xs text-gray-600 dark:text-gray-400">Include relevant hashtags</span>
                <input type="checkbox" v-model="aiIncludeHashtags" class="rounded text-purple-600 focus:ring-purple-500 w-4 h-4" />
              </div>
            </div>

            <!-- Anti-Prompt Injection Notice -->
            <div class="p-3 bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900/40 rounded-xl text-[11px] text-blue-700 dark:text-blue-300 flex items-start gap-2">
              <span class="text-sm shrink-0">🛡️</span>
              <span>External search data is sandboxed with zero-trust prompt-injection defenses and verified before generating the post.</span>
            </div>
          </div>

          <!-- Footer -->
          <div class="p-5 border-t dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/30 flex items-center justify-between">
            <button 
              type="button" 
              @click="isAiDraftModalOpen = false" 
              class="btn btn-secondary btn-sm"
              :disabled="isGeneratingAiPost"
            >
              Cancel
            </button>

            <button 
              type="button" 
              @click="handleGenerateAiPost" 
              class="btn bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white btn-sm px-6 flex items-center gap-2 shadow-lg"
              :disabled="isGeneratingAiPost || !aiTopicPrompt.trim()"
            >
              <IconAnimateSpin v-if="isGeneratingAiPost" class="w-4 h-4 animate-spin" />
              <IconSparkles v-else class="w-4 h-4 text-amber-300" />
              <span>{{ isGeneratingAiPost ? 'Searching & Drafting...' : 'Generate Post Draft' }}</span>
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>