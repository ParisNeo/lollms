<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import PersonalityCard from '../ui/PersonalityCard.vue';

const authStore = useAuthStore();
const dataStore = useDataStore();
const uiStore = useUiStore();

const { user } = storeToRefs(authStore);
const { userPersonalities, publicPersonalities } = storeToRefs(dataStore);

const activePersonalityId = ref('');
const savingPersonalityId = ref(null);
const searchQuery = ref('');
const selectedCategory = ref('All');
const starredPersonalityIds = ref(new Set());

const allPersonalities = computed(() => [...userPersonalities.value, ...publicPersonalities.value]);

const allCategories = computed(() => {
    const categories = new Set(['All', 'Starred']);
    allPersonalities.value.forEach(p => {
        if (p.category) {
            categories.add(p.category);
        }
    });
    return Array.from(categories).sort((a, b) => {
        if (a === 'All') return -1;
        if (b === 'All') return 1;
        if (a === 'Starred') return -1;
        if (b === 'Starred') return 1;
        return a.localeCompare(b);
    });
});

const filteredList = computed(() => {
    let list = allPersonalities.value;

    if (selectedCategory.value === 'Starred') {
        list = list.filter(p => starredPersonalityIds.value.has(p.id));
    } else if (selectedCategory.value !== 'All') {
        list = list.filter(p => p.category === selectedCategory.value);
    }
    
    const query = searchQuery.value.toLowerCase().trim();
    if (query) {
        list = list.filter(p => 
            p.name.toLowerCase().includes(query) ||
            (p.description && p.description.toLowerCase().includes(query))
        );
    }
    return list;
});

const filteredUserPersonalities = computed(() => filteredList.value.filter(p => !p.is_public));
const filteredPublicPersonalities = computed(() => filteredList.value.filter(p => p.is_public));

onMounted(() => {
    dataStore.fetchPersonalities();
    if (user.value) {
        activePersonalityId.value = user.value.active_personality_id || '';
        starredPersonalityIds.value = new Set(user.value.starred_personality_ids || []);
        selectedCategory.value = user.value.personalities_view_category || 'All';
    }
});

watch(() => user.value?.active_personality_id, (newId) => {
    activePersonalityId.value = newId || '';
});

watch(() => user.value?.starred_personality_ids, (newIds) => {
    starredPersonalityIds.value = new Set(newIds || []);
}, { deep: true });

watch(() => user.value?.personalities_view_category, (newCategory) => {
    selectedCategory.value = newCategory || 'All';
});

watch(selectedCategory, (newCategory) => {
    if (user.value && newCategory !== (user.value.personalities_view_category || 'All')) {
        authStore.updateUserPreferences({ personalities_view_category: newCategory });
    }
});


// --- THIS IS THE CORRECTED FUNCTION ---
async function handleToggleStar(personality) {
    // 1. Keep a copy of the original state to revert to on failure.
    const originalStarredSet = new Set(starredPersonalityIds.value);
    
    // 2. Create the new state.
    const newStarredSet = new Set(originalStarredSet);
    if (newStarredSet.has(personality.id)) {
        newStarredSet.delete(personality.id);
    } else {
        newStarredSet.add(personality.id);
    }

    // 3. Apply the new state to the local UI immediately (Optimistic Update).
    starredPersonalityIds.value = newStarredSet;

    // 4. Try to save the change to the backend.
    try {
        await authStore.updateUserPreferences({ starred_personality_ids: Array.from(newStarredSet) });
    } catch (error) {
        // 5. If the save fails, revert the UI to the original state.
        starredPersonalityIds.value = originalStarredSet;
        uiStore.showToast({ message: 'Failed to update favorite status.', type: 'error' });
    }
}


async function handleSelectPersonality(personality) {
    if (savingPersonalityId.value) return;
    if (!personality || activePersonalityId.value === personality.id) {
        await handleDeselectAll();
        return;
    }
    
    savingPersonalityId.value = personality.id;
    try {
        await authStore.updateUserPreferences({ active_personality_id: personality.id });
    } catch (error) {
        // Handled by interceptor
    } finally {
        savingPersonalityId.value = null;
    }
}

async function handleDeselectAll() {
    if (!activePersonalityId.value || savingPersonalityId.value) return;
    
    savingPersonalityId.value = activePersonalityId.value;
    try {
        await authStore.updateUserPreferences({ active_personality_id: null });
    } catch (error) {
        // Handled by interceptor
    } finally {
        savingPersonalityId.value = null;
    }
}

function openEditor(personality = null) {
    let personalityData;
    if (personality) {
        personalityData = { ...personality };
        if (personality.is_public) {
            personalityData.id = null;
            personalityData.is_public = false;
        }
    } else {
        personalityData = { name: '', category: '', description: '', prompt_text: '', is_public: false, icon_base64: null };
    }
    uiStore.openModal('personalityEditor', { personality: personalityData });
}

async function handleDeletePersonality(personality) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete ${personality.name}`,
        message: 'Are you sure you want to delete this personality? This cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed) {
        if (activePersonalityId.value === personality.id) {
            await handleDeselectAll();
        }
        await dataStore.deletePersonality(personality.id);
    }
}

async function handleShare(personality) {
    try {
        await navigator.clipboard.writeText(JSON.stringify(personality, null, 2));
        uiStore.showToast({ message: `${personality.name} copied to clipboard!`, type: 'success' });
    } catch (err) {
        uiStore.showToast({ message: 'Failed to copy to clipboard.', type: 'error' });
    }
}
</script>

<template>
    <section>
        <h4 class="text-lg font-semibold mb-2 border-b dark:border-gray-600 pb-2">Personalities</h4>
        
        <div class="my-6 grid grid-cols-1 md:grid-cols-2 gap-4">
             <div class="relative">
                <input 
                    type="text" 
                    v-model="searchQuery" 
                    placeholder="Search personalities..."
                    class="input-field w-full !pr-10"
                />
                <button v-if="searchQuery" @click="searchQuery = ''" class="absolute inset-y-0 right-0 flex items-center pr-3 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
            </div>
            <div>
                <select v-model="selectedCategory" class="input-field w-full">
                    <option v-for="cat in allCategories" :key="cat" :value="cat">{{ cat }}</option>
                </select>
            </div>
        </div>

        <div class="space-y-10">
            <div>
                <div class="flex justify-between items-center mb-4">
                    <h5 class="text-md font-semibold">Your Personalities</h5>
                    <button @click="openEditor()" class="btn btn-secondary !text-xs !py-1">+ Create New</button>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    <div
                        @click="handleDeselectAll"
                        class="flex flex-col items-center justify-center h-full min-h-[160px] bg-white dark:bg-gray-800 border-2 border-dashed dark:border-gray-600 rounded-lg p-4 transition-all hover:border-gray-400 dark:hover:border-gray-500 cursor-pointer"
                        :class="{ '!border-solid ring-2 ring-offset-2 ring-blue-500 dark:ring-offset-gray-900 !border-blue-500': !activePersonalityId }"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-gray-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                        </svg>
                        <span class="font-semibold text-sm text-gray-700 dark:text-gray-300">No Personality</span>
                        <span class="text-xs text-gray-500 dark:text-gray-400">(Default)</span>
                    </div>

                    <PersonalityCard
                        v-for="p in filteredUserPersonalities"
                        :key="p.id"
                        :personality="p"
                        :is-user-personality="true"
                        :is-active="p.id === activePersonalityId"
                        :is-saving="p.id === savingPersonalityId"
                        :is-starred="starredPersonalityIds.has(p.id)"
                        @select="handleSelectPersonality($event)"
                        @toggle-star="handleToggleStar($event)"
                        @edit="openEditor($event)"
                        @delete="handleDeletePersonality($event)"
                        @share="handleShare($event)"
                    />
                </div>
                <p v-if="filteredUserPersonalities.length === 0 && userPersonalities.length === 0" class="italic text-sm text-gray-500 p-2 mt-4">
                    You haven't created any personalities yet.
                </p>
                 <p v-else-if="filteredUserPersonalities.length === 0" class="italic text-sm text-gray-500 p-2 mt-4">
                    No matches found in your personalities.
                </p>
            </div>

            <div>
                <h5 class="text-md font-semibold mb-4">Public Personalities</h5>
                <div v-if="filteredPublicPersonalities.length > 0" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                     <PersonalityCard
                        v-for="p in filteredPublicPersonalities"
                        :key="p.id"
                        :personality="p"
                        :is-user-personality="false"
                        :is-active="p.id === activePersonalityId"
                        :is-saving="p.id === savingPersonalityId"
                        :is-starred="starredPersonalityIds.has(p.id)"
                        @select="handleSelectPersonality($event)"
                        @toggle-star="handleToggleStar($event)"
                        @clone="openEditor($event)"
                        @share="handleShare($event)"
                    />
                </div>
                <p v-else class="italic text-sm text-gray-500 p-2">
                    {{ searchQuery || selectedCategory !== 'All' ? 'No matches found in public personalities.' : "No public personalities available." }}
                </p>
            </div>
        </div>
    </section>
</template>