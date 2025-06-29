<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import DiscussionItem from './DiscussionItem.vue';
import IconSelectMenu from '../ui/IconSelectMenu.vue';
import SimpleSelectMenu from '../ui/SimpleSelectMenu.vue';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const dataStore = useDataStore();

const searchQuery = ref('');
const sortMethod = ref('date_desc');
const isSortMenuOpen = ref(false);
const isSearchVisible = ref(false);
const searchInput = ref(null);

const activePersonalityId = computed({
    get: () => authStore.user?.active_personality_id || null,
    set: (value) => authStore.updateUserPreferences({ active_personality_id: value || null })
});

const activeModelName = computed({
    get: () => authStore.user?.lollms_model_name || '',
    set: (value) => authStore.updateUserPreferences({ lollms_model_name: value })
});

const selectedPersonality = computed(() => {
    // Add a check to ensure the stores are populated
    const allPersonalities = [...(dataStore.userPersonalities || []), ...(dataStore.publicPersonalities || [])];
    return allPersonalities.find(p => p.id === activePersonalityId.value);
});

const personalityItems = computed(() => {
    const items = [];
    if (dataStore.userPersonalities && dataStore.userPersonalities.length > 0) {
        items.push({
            isGroup: true,
            label: "Your Personalities",
            items: dataStore.userPersonalities.map(p => ({ id: p.id, name: p.name, icon_base64: p.icon_base64, description: p.description }))
        });
    }
    if (dataStore.publicPersonalities && dataStore.publicPersonalities.length > 0) {
         items.push({
            isGroup: true,
            label: "Public Personalities",
            items: dataStore.publicPersonalities.map(p => ({ id: p.id, name: p.name, icon_base64: p.icon_base64 }))
        });
    }
    return items;
});

const modelItems = computed(() => {
    // Add a check here too
    if (!dataStore.availableLollmsModels) return [];
    return dataStore.availableLollmsModels.map(m => ({ value: m.name, label: m.name }));
});

const sortOptions = {
  date_desc: 'Most Recent',
  date_asc: 'Oldest First',
  title_asc: 'Title (A-Z)',
  title_za: 'Title (Z-A)',
};


function createNewDiscussion() {
    uiStore.setMainView('chat');
    discussionsStore.createNewDiscussion();
}

watch(isSearchVisible, (isVisible) => {
    if(isVisible) {
        nextTick(() => { searchInput.value?.focus(); });
    } else {
        searchQuery.value = '';
    }
});

const filteredAndSortedDiscussions = computed(() => {
  // --- THIS IS THE CRITICAL FIX ---
  // Always ensure discussionsStore.discussions is an object before using Object.values
  const all = discussionsStore.discussions ? Object.values(discussionsStore.discussions) : [];
  
  if (all.length === 0) return []; // Return early if there's nothing to process

  const filtered = all.filter(d => 
    d && (d.title || '').toLowerCase().includes(searchQuery.value.toLowerCase())
  );

  return filtered.sort((a, b) => {
    // Add checks for a and b to prevent errors during sorting if data is malformed
    if (!a || !b) return 0;
    switch (sortMethod.value) {
      case 'date_asc': return new Date(a.last_activity_at || 0) - new Date(b.last_activity_at || 0);
      case 'title_asc': return (a.title || '').localeCompare(b.title || '');
      case 'title_za': return (b.title || '').localeCompare(a.title || '');
      case 'date_desc':
      default:
        return new Date(b.last_activity_at || 0) - new Date(a.last_activity_at || 0);
    }
  });
});

// These computed properties will now be safe because filteredAndSortedDiscussions always returns an array.
const starredDiscussions = computed(() => filteredAndSortedDiscussions.value.filter(d => d.is_starred));
const regularDiscussions = computed(() => filteredAndSortedDiscussions.value.filter(d => !d.is_starred));

function selectSort(method) {
  sortMethod.value = method;
  isSortMenuOpen.value = false;
}

function setMainView(viewName) {
    uiStore.setMainView(viewName);
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Controls Area -->
    <div class="p-3 border-b dark:border-gray-700 space-y-2 flex-shrink-0">
      <!-- Buttons Row -->
      <div class="flex items-center justify-between space-x-1">
        <button @click="createNewDiscussion()" title="New Discussion" class="btn btn-primary !p-2 flex-shrink-0">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
        </button>

        <div class="flex-grow flex justify-end items-center space-x-1">
            <button title="Feed" @click="setMainView('feed')" class="main-nav-btn" :class="{ 'active': mainView === 'feed' }">
            <!-- Background card -->
            <svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="none">
              <!-- Outer rectangle (representing a feed card) -->
              <rect x="3" y="3" width="18" height="18" rx="3" fill="#f5f5f5" stroke="#888" stroke-width="1.5"/>

              <!-- Avatar circle -->
              <circle cx="7" cy="8" r="1.5" fill="#888" />

              <!-- Name line -->
              <rect x="10" y="7" width="8" height="1.5" rx="0.75" fill="#bbb" />

              <!-- Content lines -->
              <rect x="5" y="11" width="14" height="1.5" rx="0.75" fill="#ccc" />
              <rect x="5" y="14" width="12" height="1.5" rx="0.75" fill="#ccc" />

              <!-- Action dots (like/comment) -->
              <circle cx="8" cy="18" r="1" fill="#e74c3c"/>
              <circle cx="12" cy="18" r="1" fill="#3498db"/>
            </svg>
            </button>

            <button 
            @click="isSearchVisible = !isSearchVisible"
            title="Search discussions" 
            class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            :class="{'bg-blue-100 dark:bg-blue-900': isSearchVisible}"
            >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 text-gray-500 dark:text-gray-400">
                <path stroke-linecap="round" stroke-linejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
            </svg>
            </button>
            
            <div class="w-10 flex-shrink-0">
                <IconSelectMenu
                    v-model="activePersonalityId"
                    :items="personalityItems"
                    placeholder="None"
                >
                    <template #button="{ toggle }">
                        <button @click="toggle" class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 w-full" :title="`Personality: ${selectedPersonality ? selectedPersonality.name : 'None'}`">
                            <img v-if="selectedPersonality && selectedPersonality.icon_base64" :src="selectedPersonality.icon_base64" class="w-5 h-5 rounded-sm object-cover"/>
                            <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 text-gray-500 dark:text-gray-400"><path stroke-linecap="round" stroke-linejoin="round" d="M17.982 18.725A7.488 7.488 0 0 0 12 15.75a7.488 7.488 0 0 0-5.982 2.975m11.963 0a9 9 0 1 0-11.963 0m11.963 0A8.966 8.966 0 0 1 12 21a8.966 8.966 0 0 1-5.982-2.275M15 9.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg>
                        </button>
                    </template>
                    <template #footer>
                        <button @click="dataStore.fetchPersonalities()" class="w-full text-center py-1.5 text-xs text-blue-600 dark:text-blue-400 hover:bg-gray-100 dark:hover:bg-gray-700">Refresh List</button>
                    </template>
                </IconSelectMenu>
            </div>

            <div class="w-10 flex-shrink-0">
                <SimpleSelectMenu v-model="activeModelName" :items="modelItems" placeholder="Default">
                    <template #button="{ toggle }">
                        <button @click="toggle" class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 w-full" :title="`Model: ${activeModelName || 'Default'}`">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 text-gray-500 dark:text-gray-400"><path stroke-linecap="round" stroke-linejoin="round" d="m21 7.5-9-5.25L3 7.5m18 0-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" /></svg>
                        </button>
                    </template>
                     <template #footer>
                        <button @click="dataStore.fetchAvailableLollmsModels()" class="w-full text-center py-1.5 text-xs text-blue-600 dark:text-blue-400 hover:bg-gray-100 dark:hover:bg-gray-700">Refresh List</button>
                    </template>
                </SimpleSelectMenu>
            </div>

            <!-- FIX: Apply v-on-click-outside to the parent div -->
            <div class="relative" v-on-click-outside="() => isSortMenuOpen = false">
                <button 
                    @click="isSortMenuOpen = !isSortMenuOpen"
                    title="Sort options" 
                    class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 text-gray-500 dark:text-gray-400">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M3 4.5h14.25M3 9h9.75M3 13.5h5.25m5.25-.75L17.25 9m0 0L21 12.75M17.25 9v12" />
                    </svg>
                </button>
                <div v-if="isSortMenuOpen" class="absolute top-full right-0 mt-2 w-48 bg-white dark:bg-gray-800 border dark:border-gray-600 rounded-lg shadow-xl z-20">
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
      <!-- Search Input Row -->
      <div v-if="isSearchVisible">
          <input 
              ref="searchInput"
              type="text" 
              v-model="searchQuery"
              placeholder="Search discussions..." 
              class="input-field w-full !py-2 !px-3"
            >
      </div>
    </div>
    
    <!-- Discussion Items List -->
    <div class="p-2 space-y-1 flex-1 overflow-y-auto">
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