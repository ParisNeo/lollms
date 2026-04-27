<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import PersonalityCard from '../ui/Cards/PersonalityCard.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';

const authStore = useAuthStore();
const dataStore = useDataStore();
const uiStore = useUiStore();

const { user } = storeToRefs(authStore);
const { userPersonalities, publicPersonalities } = storeToRefs(dataStore);

const STARRED_LOCALSTORAGE_KEY = 'lollms-starred-personalities';

const activePersonalityId = ref('');
const savingPersonalityId = ref(null);
const searchQuery = ref('');
const selectedCategory = ref('All');
const starredPersonalityIds = ref(new Set());
const importInputRef = ref(null);
const isSearchFocused = ref(false);

const allPersonalities = computed(() => [...userPersonalities.value, ...publicPersonalities.value]);

// Category configuration with colors and icons
const categoryConfig = {
    'Creative': { color: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300', icon: '✨' },
    'Coding': { color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300', icon: '💻' },
    'Educational': { color: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300', icon: '📚' },
    'Technical Support': { color: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300', icon: '🔧' },
    'Writing': { color: 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-300', icon: '✍️' },
    'Language': { color: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300', icon: '🌐' },
    'Art': { color: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300', icon: '🎨' },
    'Music': { color: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300', icon: '🎵' },
    'Science': { color: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-300', icon: '🔬' },
    'Business': { color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300', icon: '💼' },
    'Fun': { color: 'bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-900/30 dark:text-fuchsia-300', icon: '🎭' },
    'Generic': { color: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300', icon: '🤖' },
    'default': { color: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300', icon: '🎯' }
};

function getCategoryStyle(category) {
    return categoryConfig[category] || categoryConfig['default'];
}

const allCategories = computed(() => {
    const categories = new Set(['All', 'Starred']);
    allPersonalities.value.forEach(p => {
        if (p.category) categories.add(p.category);
    });
    return Array.from(categories).sort((a, b) => {
        if (a === 'All') return -1; if (b === 'All') return 1;
        if (a === 'Starred') return -1; if (b === 'Starred') return 1;
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
            (p.description && p.description.toLowerCase().includes(query)) ||
            (p.category && p.category.toLowerCase().includes(query))
        );
    }
    return list;
});

const filteredUserPersonalities = computed(() => filteredList.value.filter(p => !p.is_public && p.owner_username !== 'System'));
const filteredPublicPersonalities = computed(() => filteredList.value.filter(p => p.is_public || p.owner_username === 'System'));

const isShared = (personality) => {
    return personality.author && personality.author.startsWith('Sent by ');
};

const getSharedByUsername = (personality) => {
    if (isShared(personality)) {
        return personality.author.replace('Sent by ', '').trim();
    }
    return '';
};

// Stats for the header
const totalPersonalities = computed(() => userPersonalities.value.length);
const publicCount = computed(() => publicPersonalities.value.filter(p => p.owner_username === 'System').length);

onMounted(() => {
    dataStore.fetchPersonalities();
    try {
        const storedStarred = localStorage.getItem(STARRED_LOCALSTORAGE_KEY);
        if (storedStarred) starredPersonalityIds.value = new Set(JSON.parse(storedStarred));
    } catch (e) {
        console.error("Failed to load starred personalities from localStorage:", e);
        starredPersonalityIds.value = new Set();
    }
    if (user.value) {
        activePersonalityId.value = user.value.active_personality_id || '';
        selectedCategory.value = user.value.personalities_view_category || 'All';
    }
});

watch(() => user.value?.active_personality_id, (newId) => { activePersonalityId.value = newId || ''; });
watch(() => user.value?.personalities_view_category, (newCategory) => { selectedCategory.value = newCategory || 'All'; });

watch(selectedCategory, (newCategory) => {
    if (user.value && newCategory !== (user.value.personalities_view_category || 'All')) {
        authStore.updateUserPreferences({ personalities_view_category: newCategory });
    }
});

async function handleToggleStar(personality) {
    const newStarredSet = new Set(starredPersonalityIds.value);
    if (newStarredSet.has(personality.id)) newStarredSet.delete(personality.id);
    else newStarredSet.add(personality.id);
    starredPersonalityIds.value = newStarredSet;
    try {
        localStorage.setItem(STARRED_LOCALSTORAGE_KEY, JSON.stringify(Array.from(newStarredSet)));
    } catch (error) {
        console.error("Failed to save starred personalities:", error);
        uiStore.showToast({ message: 'Could not save favorite status.', type: 'error' });
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
    } finally {
        savingPersonalityId.value = null;
    }
}

async function handleDeselectAll() {
    if (!activePersonalityId.value || savingPersonalityId.value) return;
    savingPersonalityId.value = activePersonalityId.value;
    try {
        await authStore.updateUserPreferences({ active_personality_id: null });
    } finally {
        savingPersonalityId.value = null;
    }
}

function openEditor(personality = null) {
    let personalityData;
    if (personality) {
        personalityData = { ...personality };
        if ((personality.is_public || personality.owner_username === 'System') && !authStore.user.is_admin) {
            personalityData.id = null;
            personalityData.is_public = false;
            personalityData.owner_type = 'user';
        }
    } else {
        personalityData = { id: null, name: '', category: '', description: '', prompt_text: '', is_public: false, icon_base64: null };
    }
    uiStore.openModal('personalityEditor', { personality: personalityData });
}

function openGeneratePersonalityModal() {
    uiStore.openModal('generatePersonality');
}

async function handleDeletePersonality(personality) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete ${personality.name}`,
        message: 'Are you sure you want to delete this personality? This cannot be undone.',
        confirmText: 'Delete',
        confirmClass: 'btn-danger'
    });
    if (confirmed) {
        if (activePersonalityId.value === personality.id) await handleDeselectAll();
        if (starredPersonalityIds.value.has(personality.id)) handleToggleStar(personality);
        await dataStore.deletePersonality(personality.id);
    }
}

async function handleShare(personality) {
    uiStore.openModal('sharePersonality', {
        personalityId: personality.id,
        title: personality.name
    });
}

function triggerImport() {
    importInputRef.value.click();
}

async function handleImport(event) {
    const file = event.target.files[0];
    if (!file) return;
    await dataStore.importPersonality(file);
    event.target.value = '';
}

function clearSearch() {
    searchQuery.value = '';
}
</script>

<template>
    <section class="space-y-6">
        <!-- Enhanced Header -->
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
                <h2 class="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                    <span class="text-2xl">🎭</span>
                    Personality Studio
                </h2>
                <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    {{ totalPersonalities }} personal • {{ publicCount }} public personalities available
                </p>
            </div>
            <div class="flex items-center gap-2 flex-wrap">
                <input type="file" ref="importInputRef" @change="handleImport" class="hidden" accept=".zip">
                <button @click="triggerImport" class="btn btn-secondary flex items-center gap-2 hover:shadow-md transition-shadow" title="Import from Zip">
                    <IconArrowUpTray class="w-4 h-4" /> 
                    <span class="hidden sm:inline">Import</span>
                </button>
                <button @click="openGeneratePersonalityModal()" class="btn btn-primary flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 hover:shadow-lg transition-all">
                    <IconSparkles class="w-4 h-4" />
                    <span class="hidden sm:inline">Generate</span>
                </button>
                <button @click="openEditor()" class="btn btn-secondary flex items-center gap-2 hover:shadow-md transition-shadow">
                    <IconPlus class="w-4 h-4" />
                    <span class="hidden sm:inline">Create New</span>
                </button>
            </div>
        </div>
        
        <!-- Enhanced Search & Filter Bar -->
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 space-y-4">
            <div class="flex flex-col sm:flex-row gap-3">
                <!-- Search Input -->
                <div class="relative flex-1">
                    <IconMagnifyingGlass class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 transition-colors" :class="{ 'text-blue-500': isSearchFocused }" />
                    <input 
                        type="text" 
                        v-model="searchQuery" 
                        @focus="isSearchFocused = true"
                        @blur="isSearchFocused = false"
                        placeholder="Search personalities by name, description, or category..."
                        class="input-field w-full !pl-10 !pr-10 transition-all"
                        :class="{ 'ring-2 ring-blue-500/20 border-blue-300': isSearchFocused }"
                    />
                    <button 
                        v-if="searchQuery" 
                        @click="clearSearch" 
                        class="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 transition-colors"
                    >
                        <IconXMark class="w-4 h-4" />
                    </button>
                </div>
                <!-- Category Dropdown -->
                <div class="relative min-w-[160px]">
                    <select v-model="selectedCategory" class="input-field w-full appearance-none cursor-pointer">
                        <option v-for="cat in allCategories" :key="cat" :value="cat">
                            {{ cat === 'All' ? '📋 All Categories' : cat === 'Starred' ? '⭐ Starred' : cat }}
                        </option>
                    </select>
                    <div class="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
                        <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                    </div>
                </div>
            </div>
            
            <!-- Quick Category Chips (when not searching) -->
            <div v-if="!searchQuery && selectedCategory === 'All'" class="flex flex-wrap gap-2">
                <button 
                    v-for="cat in allCategories.filter(c => c !== 'All' && c !== 'Starred')" 
                    :key="cat"
                    @click="selectedCategory = cat"
                    class="px-3 py-1.5 rounded-full text-xs font-medium transition-all hover:scale-105"
                    :class="getCategoryStyle(cat).color"
                >
                    {{ getCategoryStyle(cat).icon }} {{ cat }}
                </button>
            </div>
        </div>

        <!-- Content Sections -->
        <div class="space-y-8">
            <!-- Starred Section (when selected) -->
            <div v-if="selectedCategory === 'Starred'">
                <div class="flex items-center gap-2 mb-4">
                    <span class="text-xl">⭐</span>
                    <h3 class="text-lg font-bold text-gray-900 dark:text-white">Starred Personalities</h3>
                    <span class="px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300 text-xs font-medium">
                        {{ filteredList.length }}
                    </span>
                </div>
                <div v-if="filteredList.length > 0" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    <PersonalityCard
                        v-for="p in filteredList"
                        :key="p.id"
                        :personality="p"
                        :is-user-personality="p.owner_username === user.username || (user && user.is_admin)"
                        :is-active="p.id === activePersonalityId"
                        :is-saving="p.id === savingPersonalityId"
                        :is-starred="starredPersonalityIds.has(p.id)"
                        :is-shared="isShared(p)"
                        :shared-by="getSharedByUsername(p)"
                        :category-style="getCategoryStyle(p.category)"
                        @select="handleSelectPersonality($event)"
                        @toggle-star="handleToggleStar($event)"
                        @clone="openEditor($event)"
                        @edit="openEditor($event)"
                        @delete="handleDeletePersonality($event)"
                        @share="handleShare($event)"
                    />
                </div>
                <div v-else class="text-center py-12 bg-gray-50 dark:bg-gray-800/50 rounded-xl border-2 border-dashed border-gray-200 dark:border-gray-700">
                    <span class="text-4xl mb-3 block">⭐</span>
                    <p class="text-gray-500 dark:text-gray-400 font-medium">
                        {{ searchQuery ? 'No starred personalities match your search.' : 'No starred personalities yet' }}
                    </p>
                    <p v-if="!searchQuery" class="text-sm text-gray-400 dark:text-gray-500 mt-1">
                        Click the star icon on any personality to add it here
                    </p>
                </div>
            </div>
            
            <template v-else>
                <!-- Your Personalities Section -->
                <div>
                    <div class="flex items-center gap-2 mb-4">
                        <span class="text-xl">👤</span>
                        <h3 class="text-lg font-bold text-gray-900 dark:text-white">Your Personalities</h3>
                        <span class="px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 text-xs font-medium">
                            {{ filteredUserPersonalities.length }}
                        </span>
                    </div>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                        <!-- No Personality Card -->
                        <div
                            @click="handleDeselectAll"
                            class="group flex flex-col items-center justify-center h-full min-h-[180px] bg-white dark:bg-gray-800 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl p-6 transition-all hover:border-gray-400 dark:hover:border-gray-500 cursor-pointer hover:shadow-md"
                            :class="{ '!border-solid !border-green-500 !bg-green-50 dark:!bg-green-900/20 !shadow-lg': !activePersonalityId }"
                        >
                            <div class="w-16 h-16 rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center mb-3 transition-transform group-hover:scale-110" :class="{ '!bg-green-100 dark:!bg-green-800': !activePersonalityId }">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-gray-400 transition-colors" :class="{ '!text-green-600': !activePersonalityId }" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                                </svg>
                            </div>
                            <span class="font-bold text-sm text-gray-700 dark:text-gray-300">No Personality</span>
                            <span class="text-xs text-gray-500 dark:text-gray-400 mt-1">Use default behavior</span>
                            <span v-if="!activePersonalityId" class="mt-2 px-2 py-0.5 rounded-full bg-green-100 text-green-700 dark:bg-green-800 dark:text-green-300 text-xs font-medium">Active</span>
                        </div>

                        <!-- User Personality Cards -->
                        <PersonalityCard
                            v-for="p in filteredUserPersonalities"
                            :key="p.id"
                            :personality="p"
                            :is-user-personality="true"
                            :is-active="p.id === activePersonalityId"
                            :is-saving="p.id === savingPersonalityId"
                            :is-starred="starredPersonalityIds.has(p.id)"
                            :is-shared="isShared(p)"
                            :shared-by="getSharedByUsername(p)"
                            :category-style="getCategoryStyle(p.category)"
                            @select="handleSelectPersonality($event)"
                            @toggle-star="handleToggleStar($event)"
                            @edit="openEditor($event)"
                            @delete="handleDeletePersonality($event)"
                            @share="handleShare($event)"
                        />
                    </div>
                    
                    <!-- Empty State -->
                    <div v-if="filteredUserPersonalities.length === 0 && userPersonalities.length === 0 && selectedCategory === 'All' && !searchQuery" class="mt-6 text-center py-12 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/10 dark:to-indigo-900/10 rounded-xl border border-blue-100 dark:border-blue-800">
                        <span class="text-5xl mb-4 block">🎭</span>
                        <h4 class="text-lg font-bold text-gray-900 dark:text-white mb-2">Create Your First Personality</h4>
                        <p class="text-sm text-gray-500 dark:text-gray-400 max-w-md mx-auto mb-4">
                            Personalities let you customize how the AI behaves. Create a coding assistant, a creative writer, or any character you can imagine.
                        </p>
                        <div class="flex gap-2 justify-center">
                            <button @click="openGeneratePersonalityModal()" class="btn btn-primary flex items-center gap-2">
                                <IconSparkles class="w-4 h-4" />
                                Generate with AI
                            </button>
                            <button @click="openEditor()" class="btn btn-secondary flex items-center gap-2">
                                <IconPlus class="w-4 h-4" />
                                Create Manually
                            </button>
                        </div>
                    </div>
                    <p v-else-if="filteredUserPersonalities.length === 0" class="text-center py-8 text-gray-500 dark:text-gray-400">
                        No matches found in your personalities.
                    </p>
                </div>

                <!-- Public & System Personalities Section -->
                <div>
                    <div class="flex items-center gap-2 mb-4">
                        <span class="text-xl">🌍</span>
                        <h3 class="text-lg font-bold text-gray-900 dark:text-white">Public & System Personalities</h3>
                        <span class="px-2 py-0.5 rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300 text-xs font-medium">
                            {{ filteredPublicPersonalities.length }}
                        </span>
                    </div>
                    
                    <div v-if="filteredPublicPersonalities.length > 0" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                        <PersonalityCard
                            v-for="p in filteredPublicPersonalities"
                            :key="p.id"
                            :personality="p"
                            :is-user-personality="user && user.is_admin"
                            :is-active="p.id === activePersonalityId"
                            :is-saving="p.id === savingPersonalityId"
                            :is-starred="starredPersonalityIds.has(p.id)"
                            :is-shared="isShared(p)"
                            :shared-by="getSharedByUsername(p)"
                            :category-style="getCategoryStyle(p.category)"
                            @select="handleSelectPersonality($event)"
                            @toggle-star="handleToggleStar($event)"
                            @clone="openEditor($event)"
                            @edit="openEditor($event)"
                            @delete="handleDeletePersonality($event)"
                            @share="handleShare($event)"
                        />
                    </div>
                    <div v-else class="text-center py-12 bg-gray-50 dark:bg-gray-800/50 rounded-xl border-2 border-dashed border-gray-200 dark:border-gray-700">
                        <span class="text-4xl mb-3 block">🌍</span>
                        <p class="text-gray-500 dark:text-gray-400 font-medium">
                            {{ searchQuery || selectedCategory !== 'All' ? 'No matches found in public personalities.' : 'No public personalities available' }}
                        </p>
                    </div>
                </div>
            </template>
        </div>
    </section>
</template>