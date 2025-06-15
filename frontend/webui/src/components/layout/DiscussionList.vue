<script setup>
import { ref, computed } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import DiscussionItem from './DiscussionItem.vue';

const discussionsStore = useDiscussionsStore();
const searchQuery = ref('');
const sortMethod = ref('date_desc');
const isSortMenuOpen = ref(false);

const sortOptions = {
  date_desc: 'Most Recent',
  date_asc: 'Oldest First',
  title_asc: 'Title (A-Z)',
  title_za: 'Title (Z-A)',
};

const filteredAndSortedDiscussions = computed(() => {
  const all = Object.values(discussionsStore.discussions);
  
  const filtered = all.filter(d => 
    (d.title || '').toLowerCase().includes(searchQuery.value.toLowerCase())
  );

  return filtered.sort((a, b) => {
    switch (sortMethod.value) {
      case 'date_asc': return new Date(a.last_activity_at) - new Date(b.last_activity_at);
      case 'title_asc': return (a.title || '').localeCompare(b.title || '');
      case 'title_za': return (b.title || '').localeCompare(a.title || '');
      case 'date_desc':
      default:
        return new Date(b.last_activity_at) - new Date(a.last_activity_at);
    }
  });
});

const starredDiscussions = computed(() => filteredAndSortedDiscussions.value.filter(d => d.is_starred));
const regularDiscussions = computed(() => filteredAndSortedDiscussions.value.filter(d => !d.is_starred));

function selectSort(method) {
  sortMethod.value = method;
  isSortMenuOpen.value = false;
}
</script>

<template>
  <div class="flex flex-col">
    <!-- Search and Sort Controls -->
    <div class="p-3 border-b dark:border-gray-700">
      <div class="relative flex items-center space-x-2">
        <input 
          type="text" 
          v-model="searchQuery"
          placeholder="Search discussions..." 
          class="input-field w-full !py-2 !px-3"
        >
        <div class="relative">
          <button 
            @click="isSortMenuOpen = !isSortMenuOpen"
            title="Sort options" 
            class="flex-shrink-0 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 text-gray-500 dark:text-gray-400">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 4.5h14.25M3 9h9.75M3 13.5h5.25m5.25-.75L17.25 9m0 0L21 12.75M17.25 9v12" />
            </svg>
          </button>
          <div v-if="isSortMenuOpen" v-on-click-outside="() => isSortMenuOpen = false" class="absolute top-full right-0 mt-2 w-48 bg-white dark:bg-gray-800 border dark:border-gray-600 rounded-lg shadow-xl z-20">
            <a 
              v-for="(label, method) in sortOptions" 
              :key="method" 
              href="#"
              @click.prevent="selectSort(method)"
              class="block px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-blue-500 hover:text-white"
            >
              {{ label }}
            </a>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Discussion Items -->
    <div class="p-2 space-y-1">
      <div v-if="!discussionsStore.discussions || Object.keys(discussionsStore.discussions).length === 0">
        <p class="text-gray-500 dark:text-gray-400 text-sm text-center italic p-4">Loading discussions...</p>
      </div>
      
      <div v-else-if="filteredAndSortedDiscussions.length === 0">
         <p class="text-gray-500 dark:text-gray-400 text-sm text-center italic p-4">No discussions match your search.</p>
      </div>

      <div v-else>
        <!-- Starred Section -->
        <div v-if="starredDiscussions.length > 0">
          <h3 class="px-2 py-1 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Starred</h3>
          <DiscussionItem v-for="discussion in starredDiscussions" :key="discussion.id" :discussion="discussion" />
        </div>

        <!-- Regular Section -->
        <div>
          <h3 class="px-2 py-1 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400 mt-2">Recent</h3>
          <DiscussionItem v-for="discussion in regularDiscussions" :key="discussion.id" :discussion="discussion" />
        </div>
      </div>
    </div>
  </div>
</template>