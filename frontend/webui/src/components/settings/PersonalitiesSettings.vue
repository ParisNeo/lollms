<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import IconSelectMenu from '../ui/IconSelectMenu.vue'; // Import the new component

const authStore = useAuthStore();
const dataStore = useDataStore();
const uiStore = useUiStore();

// --- Reactive State ---
const { user } = storeToRefs(authStore);
const { userPersonalities, publicPersonalities } = storeToRefs(dataStore);

const activePersonalityId = ref('');
const isLoading = ref(false);
const hasChanges = ref(false);

// Format items for the IconSelectMenu
const personalityItems = computed(() => {
    const items = [];
    if (userPersonalities.value.length > 0) {
        items.push({
            isGroup: true,
            label: "Your Personalities",
            items: userPersonalities.value.map(p => ({ id: p.id, name: p.name, icon_base64: p.icon_base64 }))
        });
    }
    if (publicPersonalities.value.length > 0) {
         items.push({
            isGroup: true,
            label: "Public Personalities",
            items: publicPersonalities.value.map(p => ({ id: p.id, name: p.name, icon_base64: p.icon_base64 }))
        });
    }
    return items;
});


// --- Logic ---

const populateForm = () => {
    if (user.value) {
        activePersonalityId.value = user.value.active_personality_id || null;
        hasChanges.value = false;
    }
};

onMounted(() => {
    dataStore.fetchPersonalities();
    populateForm();
});
watch(user, populateForm);

watch(activePersonalityId, (newValue) => {
    if (user.value) {
        hasChanges.value = (newValue || null) !== (user.value.active_personality_id || null);
    }
});

// --- Actions ---

async function handleSaveActivePersonality() {
    isLoading.value = true;
    try {
        await authStore.updateUserPreferences({ active_personality_id: activePersonalityId.value || null });
        hasChanges.value = false;
    } catch (error) {
        // Handled by interceptor
    } finally {
        isLoading.value = false;
    }
}

function openEditor(personality = null) {
    const isCloning = personality && personality.owner_username !== user.value.username;
    let personalityData;

    if (isCloning) {
        personalityData = { ...personality, id: null, owner_username: null, is_public: false };
    } else {
        personalityData = personality 
            ? { ...personality } 
            : { name: '', category: '', description: '', prompt_text: '', is_public: false, icon_base64: null };
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
        await dataStore.deletePersonality(personality.id);
        if (activePersonalityId.value === personality.id) {
            activePersonalityId.value = null; // Set to null for the 'None' option
            handleSaveActivePersonality();
        }
    }
}
</script>

<template>
    <section>
        <h4 class="text-lg font-semibold mb-4 border-b dark:border-gray-600 pb-2">Personalities</h4>
        
        <!-- Active Personality Selection -->
        <form @submit.prevent="handleSaveActivePersonality" class="space-y-4 max-w-md mb-8">
            <div>
                <label for="activePersonality" class="block text-sm font-medium mb-1">Active Personality</label>
                <IconSelectMenu
                    v-model="activePersonalityId"
                    :items="personalityItems"
                    placeholder="None (Default)"
                />
            </div>
             <div class="text-right">
                <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">
                    {{ isLoading ? 'Saving...' : 'Save Active Personality' }}
                </button>
            </div>
        </form>

        <!-- Manage Your Personalities -->
        <div class="mb-8">
            <div class="flex justify-between items-center mb-2">
                <h5 class="text-md font-semibold">Manage Your Personalities</h5>
                <button @click="openEditor()" class="btn btn-secondary !text-xs !py-1">+ Create New</button>
            </div>
            <div class="max-h-60 overflow-y-auto border dark:border-gray-600 rounded p-2 space-y-1">
                <p v-if="userPersonalities.length === 0" class="italic text-sm text-gray-500 p-2">You haven't created any personalities yet.</p>
                <div v-for="p in userPersonalities" :key="p.id" class="flex justify-between items-center py-1.5 px-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-sm">
                    <div class="flex items-center space-x-3">
                        <img v-if="p.icon_base64" :src="p.icon_base64" class="h-8 w-8 rounded-md object-cover bg-gray-200 dark:bg-gray-700"/>
                        <div v-else class="h-8 w-8 rounded-md bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-gray-400">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                        </div>
                        <span>{{ p.name }}</span>
                    </div>
                    <div class="space-x-2">
                        <button @click="openEditor(p)" class="font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300">Edit</button>
                        <button @click="handleDeletePersonality(p)" class="font-medium text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300">Delete</button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Available Public Personalities -->
        <div>
            <h5 class="text-md font-semibold mb-2">Available Public Personalities</h5>
             <div class="max-h-60 overflow-y-auto border dark:border-gray-600 rounded p-2 space-y-1">
                <p v-if="publicPersonalities.length === 0" class="italic text-sm text-gray-500 p-2">No public personalities available.</p>
                <div v-for="p in publicPersonalities" :key="p.id" class="flex justify-between items-center py-1.5 px-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-sm">
                    <div class="flex items-center space-x-3">
                        <img v-if="p.icon_base64" :src="p.icon_base64" class="h-8 w-8 rounded-md object-cover bg-gray-200 dark:bg-gray-700"/>
                         <div v-else class="h-8 w-8 rounded-md bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-gray-400">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                        </div>
                        <div>
                            <span>{{ p.name }}</span>
                            <em class="block text-xs text-gray-500">by {{ p.author || 'System' }}</em>
                        </div>
                    </div>
                    <button @click="openEditor(p)" class="font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300">Clone & Edit</button>
                </div>
            </div>
        </div>
    </section>
</template>