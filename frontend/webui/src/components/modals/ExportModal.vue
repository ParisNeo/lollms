<script setup>
import { ref, computed, watch } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

// --- STATE for Search and Sort ---
const searchQuery = ref('');
const sortMethod = ref('date_desc');
const isSortMenuOpen = ref(false);

const sortOptions = {
  date_desc: 'Most Recent',
  date_asc: 'Oldest First',
  title_asc: 'Title (A-Z)',
  title_za: 'Title (Z-A)',
};

// --- Main Data Handling ---
const allDiscussions = computed(() => Object.values(discussionsStore.discussions));
const selectedIds = ref([]);
const isLoading = ref(false);

const isModalActive = computed(() => uiStore.isModalOpen('export'));

// Filtered and sorted list for display
const displayDiscussions = computed(() => {
    const filtered = allDiscussions.value.filter(d => 
        (d.title || '').toLowerCase().includes(searchQuery.value.toLowerCase())
    );

    return filtered.sort((a, b) => {
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

// "Select All" checkbox logic now applies only to the visible (filtered) items
const allVisibleSelected = computed({
    get: () => {
        const visibleIds = displayDiscussions.value.map(d => d.id);
        return visibleIds.length > 0 && visibleIds.every(id => selectedIds.value.includes(id));
    },
    set: (value) => {
        const visibleIds = displayDiscussions.value.map(d => d.id);
        if (value) {
            // Add all visible IDs to the selection, avoiding duplicates
            const newSelection = new Set([...selectedIds.value, ...visibleIds]);
            selectedIds.value = Array.from(newSelection);
        } else {
            // Remove all visible IDs from the selection
            const visibleIdSet = new Set(visibleIds);
            selectedIds.value = selectedIds.value.filter(id => !visibleIdSet.has(id));
        }
    }
});

// When the modal becomes visible, select all discussions by default.
watch(isModalActive, (isActive) => {
    if (isActive) {
        searchQuery.value = ''; // Reset search
        sortMethod.value = 'date_desc'; // Reset sort
        selectedIds.value = allDiscussions.value.map(d => d.id);
    }
});

function selectSort(method) {
  sortMethod.value = method;
  isSortMenuOpen.value = false;
}

async function handleExport() {
    isLoading.value = true;
    try {
        await discussionsStore.exportDiscussions(selectedIds.value);
        uiStore.closeModal('export');
    } catch (error) {
        // Handled by store/interceptor
    } finally {
        isLoading.value = false;
    }
}

// v-on-click-outside directive to close the sort dropdown
const vOnClickOutside = {
  mounted: (el, binding) => {
    el.__vueClickOutside__ = event => {
      if (!(el === event.target || el.contains(event.target))) {
        binding.value(event);
      }
    };
    document.body.addEventListener('click', el.__vueClickOutside__);
  },
  unmounted: (el) => {
    document.body.removeEventListener('click', el.__vueClickOutside__);
  }
};
</script>

<template>
  <GenericModal modalName="export" title="Export Discussions" maxWidthClass="max-w-xl">
    <template #body>
      <div class="space-y-4">
        <!-- Search and Sort Controls -->
        <div class="flex items-center space-x-2">
            <input 
              type="text" 
              v-model="searchQuery"
              placeholder="Search..." 
              class="input-field flex-grow"
            >
            <div class="relative">
                <button @click="isSortMenuOpen = !isSortMenuOpen" class="btn btn-secondary !px-3" title="Sort options">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 4.5h14.25M3 9h9.75M3 13.5h5.25m5.25-.75L17.25 9m0 0L21 12.75M17.25 9v12" /></svg>
                </button>
                <div v-if="isSortMenuOpen" v-on-click-outside="() => isSortMenuOpen = false" class="absolute top-full right-0 mt-2 w-48 bg-white dark:bg-gray-800 border dark:border-gray-600 rounded-lg shadow-xl z-20">
                    <a 
                        v-for="(label, method) in sortOptions" 
                        :key="method" 
                        href="#"
                        @click.prevent="selectSort(method)"
                        class="block px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-blue-500 hover:text-white"
                        :class="{'font-bold text-blue-600 dark:text-blue-400': sortMethod === method}"
                    >
                        {{ label }}
                    </a>
                </div>
            </div>
        </div>

        <!-- Discussion List -->
        <div class="border dark:border-gray-600 rounded-md max-h-80 overflow-y-auto">
            <div v-if="displayDiscussions.length > 0" class="p-3 space-y-2">
                <div class="border-b dark:border-gray-600 pb-2 mb-2">
                    <label class="flex items-center text-sm font-medium cursor-pointer p-1">
                        <input type="checkbox" v-model="allVisibleSelected" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 mr-3">
                        Select / Deselect All Visible
                    </label>
                </div>
                <label v-for="disc in displayDiscussions" :key="disc.id" class="flex items-center text-sm cursor-pointer p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700">
                    <input type="checkbox" :value="disc.id" v-model="selectedIds" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 mr-3">
                    <span class="truncate" :title="disc.title || 'Untitled Discussion'">{{ disc.title || 'Untitled Discussion' }}</span>
                </label>
            </div>
            <div v-else class="text-center italic text-gray-500 p-6">
                <p v-if="searchQuery">No discussions match your search.</p>
                <p v-else>No discussions to export.</p>
            </div>
        </div>
         <p class="text-xs text-center text-gray-500">
            Selected {{ selectedIds.length }} out of {{ allDiscussions.length }} total discussions.
        </p>
      </div>
    </template>
    <template #footer>
        <button @click="uiStore.closeModal('export')" class="btn btn-secondary">Cancel</button>
        <button @click="handleExport" class="btn btn-primary" :disabled="isLoading || selectedIds.length === 0">
            {{ isLoading ? 'Exporting...' : `Export ${selectedIds.length} Discussion(s)` }}
        </button>
    </template>
  </GenericModal>
</template>