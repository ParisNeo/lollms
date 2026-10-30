<script setup>
import { onMounted, computed, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useSocialStore } from '../../stores/social';
import { useAuthStore } from '../../stores/auth';
import CreatePostForm from './CreatePostForm.vue';
import PostCard from './PostCard.vue';
import DmFooter from '../layout/DmFooter.vue';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconTag from '../../assets/icons/IconTag.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';

const socialStore = useSocialStore();
const authStore = useAuthStore();
const showCreateForm = ref(false);

const { feedPosts, isLoadingFeed, themes, tags, activeTheme, activeTag, searchQuery, searchResults, isSearching } = storeToRefs(socialStore);
const user = computed(() => authStore.user);

const canPost = computed(() => user.value && user.value.user_ui_level >= 2);
const canChat = computed(() => user.value && user.value.chat_active && user.value.user_ui_level >= 2);

const isFiltering = computed(() => !!(activeTheme.value || activeTag.value || searchQuery.value.trim()));
const displayedPosts = computed(() => isFiltering.value ? searchResults.value : feedPosts.value);

const themeColors = {
  Technology: 'from-blue-500 to-cyan-500',
  Science: 'from-emerald-500 to-teal-500',
  Art: 'from-pink-500 to-rose-500',
  Politics: 'from-amber-500 to-orange-500',
  Health: 'from-red-500 to-pink-500',
  Business: 'from-indigo-500 to-purple-500',
  Entertainment: 'from-fuchsia-500 to-pink-500',
  Education: 'from-violet-500 to-indigo-500',
  Sports: 'from-lime-500 to-green-500',
  Other: 'from-gray-500 to-slate-500'
};

function themeGradient(theme) {
  return themeColors[theme] || 'from-gray-500 to-slate-500';
}

onMounted(() => {
  if (feedPosts.value.length === 0) socialStore.fetchFeed();
  socialStore.fetchThemes();
  socialStore.fetchTags();
});

function refreshFeed() {
  socialStore.fetchFeed();
  socialStore.fetchThemes();
  socialStore.fetchTags();
}

let searchTimer = null;
watch(searchQuery, (val) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    if (val.trim() || activeTheme.value || activeTag.value) {
      socialStore.searchPosts({ q: val, tag: activeTag.value, theme: activeTheme.value });
    } else {
      searchResults.value = [];
    }
  }, 300);
});

function selectTheme(theme) {
  activeTheme.value = activeTheme.value === theme ? null : theme;
  if (activeTheme.value || activeTag.value || searchQuery.value.trim()) {
    socialStore.searchPosts({ q: searchQuery.value, tag: activeTag.value, theme: activeTheme.value });
  } else {
    searchResults.value = [];
  }
}

function selectTag(tag) {
  activeTag.value = activeTag.value === tag ? null : tag;
  if (activeTheme.value || activeTag.value || searchQuery.value.trim()) {
    socialStore.searchPosts({ q: searchQuery.value, tag: activeTag.value, theme: activeTheme.value });
  } else {
    searchResults.value = [];
  }
}

function clearFilters() {
  activeTheme.value = null;
  activeTag.value = null;
  searchQuery.value = '';
  searchResults.value = [];
}
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="grow bg-[var(--brand-bg-app)] overflow-y-auto">
      <div class="feed-zone mx-auto py-4 px-4 w-full min-w-0 box-border">

        <!-- Theme-aware Hero Header -->
        <div class="relative mb-4 rounded-2xl overflow-hidden shadow-lg border border-[var(--brand-border-main)]">
          <div class="absolute inset-0 bg-gradient-to-r from-[var(--brand-primary)] via-[var(--brand-secondary)] to-[var(--brand-accent)]"></div>
          <div class="absolute inset-0 opacity-20" style="background-image: radial-gradient(circle at 20% 30%, rgba(255,255,255,0.5) 0, transparent 40%), radial-gradient(circle at 80% 70%, rgba(255,255,255,0.4) 0, transparent 40%);"></div>
          <div class="relative px-5 py-4 flex items-center justify-between">
            <div>
              <h1 class="text-2xl font-black text-[var(--brand-text-on-primary)] tracking-tight flex items-center gap-2 drop-shadow-sm">
                <IconSparkles class="w-6 h-6" />
                Home Feed
              </h1>
              <p class="text-[var(--brand-text-on-primary)] opacity-85 text-xs mt-0.5 font-medium">Discover what's buzzing across your network</p>
            </div>
            <button
              @click="refreshFeed"
              class="p-2 rounded-full bg-white/20 hover:bg-white/30 backdrop-blur-sm transition-all text-[var(--brand-text-on-primary)] border border-white/30"
              :disabled="isLoadingFeed"
              title="Refresh Feed"
            >
              <IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingFeed}" />
            </button>
          </div>
        </div>

        <!-- Two-column layout on wide screens (collapses to single column when sidebar is empty) -->
        <div
          class="grid grid-cols-1 gap-4"
          :class="(themes.length > 0 || tags.length > 0) ? 'lg:grid-cols-[minmax(0,1fr)_320px]' : 'lg:grid-cols-1'"
        >

          <!-- Main column -->
          <div class="min-w-0 w-full col-span-1">
            <!-- Search Bar -->
            <div class="mb-3 relative">
              <IconMagnifyingGlass class="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--brand-text-dim)] pointer-events-none" />
              <input
                v-model="searchQuery"
                type="text"
                placeholder="Search posts, tags, or themes..."
                class="w-full pl-10 pr-9 py-2.5 rounded-xl bg-[var(--brand-input-bg)] border border-[var(--brand-input-border)] shadow-sm focus:ring-2 focus:outline-none focus:ring-[var(--brand-primary)] focus:border-[var(--brand-primary)] transition-all text-sm text-[var(--brand-text-main)]"
              />
              <button v-if="searchQuery" @click="searchQuery = ''" class="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-[var(--brand-bg-hover)]">
                <IconXMark class="w-3.5 h-3.5 text-[var(--brand-text-dim)]" />
              </button>
            </div>

            <!-- Create Post -->
            <div v-if="canPost" class="mb-4">
              <div v-if="!showCreateForm" @click="showCreateForm = true" class="w-full flex items-center p-3 bg-[var(--brand-bg-card)] rounded-xl shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all cursor-pointer border border-[var(--brand-border-main)]">
                <UserAvatar v-if="user" :icon="user.icon" :username="user.username || 'User'" size-class="h-9 w-9" />
                <div class="ml-3 text-[var(--brand-text-dim)] text-sm">What's on your mind, {{ user.username }}?</div>
              </div>
              <CreatePostForm
                v-else
                @posted="showCreateForm = false"
                @close="showCreateForm = false"
              />
            </div>

            <!-- Filter indicator -->
            <div v-if="isFiltering" class="mb-3 flex items-center gap-1.5 text-[11px] text-[var(--brand-text-dim)]">
              <span>Filtering:</span>
              <span v-if="activeTheme" class="px-2 py-0.5 rounded-full text-white font-bold bg-gradient-to-r" :class="themeGradient(activeTheme)">{{ activeTheme }}</span>
              <span v-if="activeTag" class="px-2 py-0.5 rounded-full bg-[var(--brand-primary)] text-[var(--brand-text-on-primary)] font-bold">#{{ activeTag }}</span>
              <span v-if="searchQuery" class="px-2 py-0.5 rounded-full bg-[var(--brand-bg-hover)] font-bold">"{{ searchQuery }}"</span>
            </div>

            <!-- Posts -->
            <div>
              <div v-if="(isLoadingFeed || isSearching) && displayedPosts.length === 0" class="text-center py-10">
                <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-[var(--brand-primary)] border-t-transparent"></div>
                <p class="text-[var(--brand-text-dim)] mt-3 text-sm">Loading...</p>
              </div>

              <div v-else-if="!isLoadingFeed && !isSearching && displayedPosts.length === 0" class="text-center py-10 bg-[var(--brand-bg-card)] rounded-2xl shadow-sm border border-[var(--brand-border-main)]">
                <div class="text-5xl mb-2">🌱</div>
                <h3 class="text-base font-bold text-[var(--brand-text-main)]">
                  {{ isFiltering ? 'No posts match your filters' : 'Your Feed is Empty' }}
                </h3>
                <p class="mt-1 text-xs text-[var(--brand-text-dim)]">
                  {{ isFiltering ? 'Try clearing filters or searching for something else.' : 'Follow people or create your first post to see content here.' }}
                </p>
                <button v-if="isFiltering" @click="clearFilters" class="mt-3 btn btn-primary btn-sm">Clear Filters</button>
              </div>

              <div v-else class="space-y-3">
                <PostCard
                  v-for="post in displayedPosts"
                  :key="post.id"
                  :post="post"
                />
              </div>
            </div>
          </div>

          <!-- Sidebar column (themes + tags) -->
          <aside class="hidden lg:block">
            <div class="sticky top-4 space-y-3">
              <!-- Themes card -->
              <div v-if="themes.length > 0" class="bg-[var(--brand-bg-card)] rounded-xl shadow-sm border border-[var(--brand-border-main)] p-3">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-[10px] font-black uppercase tracking-widest text-[var(--brand-text-dim)]">Themes</span>
                  <button v-if="activeTheme || activeTag" @click="clearFilters" class="text-[10px] font-bold text-[var(--brand-primary)] hover:underline">Clear</button>
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <button
                    v-for="t in themes"
                    :key="t.theme"
                    @click="selectTheme(t.theme)"
                    :class="[
                      'px-2.5 py-1 rounded-full text-[11px] font-bold transition-all shadow-sm border',
                      activeTheme === t.theme
                        ? `bg-gradient-to-r ${themeGradient(t.theme)} text-white border-transparent shadow-md scale-105`
                        : 'bg-[var(--brand-bg-hover)] text-[var(--brand-text-main)] border-[var(--brand-border-main)] hover:shadow-md hover:-translate-y-0.5'
                    ]"
                  >
                    {{ t.theme }}
                    <span class="ml-1 opacity-70 text-[9px]">{{ t.count }}</span>
                  </button>
                </div>
              </div>

              <!-- Tags card -->
              <div v-if="tags.length > 0" class="bg-[var(--brand-bg-card)] rounded-xl shadow-sm border border-[var(--brand-border-main)] p-3">
                <div class="flex items-center gap-1.5 mb-2">
                  <IconTag class="w-3 h-3 text-[var(--brand-text-dim)]" />
                  <span class="text-[10px] font-black uppercase tracking-widest text-[var(--brand-text-dim)]">Popular Tags</span>
                </div>
                <div class="flex flex-wrap gap-1">
                  <button
                    v-for="tg in tags.slice(0, 24)"
                    :key="tg.tag"
                    @click="selectTag(tg.tag)"
                    :class="[
                      'px-2 py-0.5 rounded-md text-[10px] font-semibold transition-all border',
                      activeTag === tg.tag
                        ? 'bg-[var(--brand-primary)] text-[var(--brand-text-on-primary)] border-[var(--brand-primary)] shadow-md'
                        : 'bg-[var(--brand-bg-subtle)] text-[var(--brand-primary)] border-[var(--brand-border-main)] hover:bg-[var(--brand-bg-hover)]'
                    ]"
                  >
                    #{{ tg.tag }}
                  </button>
                </div>
              </div>
            </div>
          </aside>
        </div>

        <!-- Mobile-only theme/tag pills (below posts) -->
        <div class="lg:hidden mt-4 space-y-3">
          <div v-if="themes.length > 0" class="bg-[var(--brand-bg-card)] rounded-xl shadow-sm border border-[var(--brand-border-main)] p-3">
            <div class="flex items-center justify-between mb-2">
              <span class="text-[10px] font-black uppercase tracking-widest text-[var(--brand-text-dim)]">Themes</span>
              <button v-if="activeTheme || activeTag" @click="clearFilters" class="text-[10px] font-bold text-[var(--brand-primary)] hover:underline">Clear</button>
            </div>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="t in themes"
                :key="t.theme"
                @click="selectTheme(t.theme)"
                :class="[
                  'px-2.5 py-1 rounded-full text-[11px] font-bold transition-all shadow-sm border',
                  activeTheme === t.theme
                    ? `bg-gradient-to-r ${themeGradient(t.theme)} text-white border-transparent shadow-md`
                    : 'bg-[var(--brand-bg-hover)] text-[var(--brand-text-main)] border-[var(--brand-border-main)]'
                ]"
              >
                {{ t.theme }} <span class="ml-1 opacity-70 text-[9px]">{{ t.count }}</span>
              </button>
            </div>
          </div>
          <div v-if="tags.length > 0" class="bg-[var(--brand-bg-card)] rounded-xl shadow-sm border border-[var(--brand-border-main)] p-3">
            <div class="flex items-center gap-1.5 mb-2">
              <IconTag class="w-3 h-3 text-[var(--brand-text-dim)]" />
              <span class="text-[10px] font-black uppercase tracking-widest text-[var(--brand-text-dim)]">Popular Tags</span>
            </div>
            <div class="flex flex-wrap gap-1">
              <button
                v-for="tg in tags.slice(0, 16)"
                :key="tg.tag"
                @click="selectTag(tg.tag)"
                :class="[
                  'px-2 py-0.5 rounded-md text-[10px] font-semibold transition-all border',
                  activeTag === tg.tag
                    ? 'bg-[var(--brand-primary)] text-[var(--brand-text-on-primary)] border-[var(--brand-primary)]'
                    : 'bg-[var(--brand-bg-subtle)] text-[var(--brand-primary)] border-[var(--brand-border-main)]'
                ]"
              >
                #{{ tg.tag }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
    <DmFooter v-if="canChat" />
  </div>
</template>

<style scoped>
.feed-zone {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
}
</style>