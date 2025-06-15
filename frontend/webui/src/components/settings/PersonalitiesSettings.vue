<script setup>
import { ref, watch, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';

const authStore = useAuthStore();
const dataStore = useDataStore();
const uiStore = useUiStore();

// --- Reactive State ---
const { user } = storeToRefs(authStore);
const { userPersonalities, publicPersonalities } = storeToRefs(dataStore);

const activePersonalityId = ref('');
const isLoading = ref(false);
const hasChanges = ref(false);

const isEditorOpen = ref(false);
const editorPersonality = ref(null); // Holds personality data for the editor

// --- Logic ---

// Populate form when component mounts or user data changes
const populateForm = () => {
    if (user.value) {
        activePersonalityId.value = user.value.active_personality_id || '';
        hasChanges.value = false; // Reset change tracking
    }
};

onMounted(() => {
    dataStore.fetchPersonalities(); // Ensure data is fresh
    populateForm();
});
watch(user, populateForm);

// Watch for changes to enable the save button
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
    editorPersonality.value = personality ? { ...personality } : { name: '', category: '', description: '', prompt_text: '', is_public: false };
    isEditorOpen.value = true;
}

async function handleSavePersonality(personalityData) {
    const action = personalityData.id ? dataStore.updatePersonality : dataStore.addPersonality;
    try {
        await action(personalityData);
        isEditorOpen.value = false; // Close editor on success
    } catch (error) {
        // Don't close editor on failure
    }
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
            activePersonalityId.value = '';
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
                <label for="activePersonality" class="block text-sm font-medium">Active Personality</label>
                <select id="activePersonality" v-model="activePersonalityId" class="input-field mt-1">
                    <option value="">None (Default)</option>
                    <optgroup label="Your Personalities">
                        <option v-for="p in userPersonalities" :key="p.id" :value="p.id">{{ p.name }}</option>
                    </optgroup>
                    <optgroup label="Public Personalities">
                        <option v-for="p in publicPersonalities" :key="p.id" :value="p.id">{{ p.name }}</option>
                    </optgroup>
                </select>
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
                    <span>{{ p.name }}</span>
                    <div class="space-x-2">
                        <button @click="openEditor(p)" class="text-blue-500 hover:text-blue-700">Edit</button>
                        <button @click="handleDeletePersonality(p)" class="text-red-500 hover:text-red-700">Delete</button>
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
                    <span>{{ p.name }} <em class="text-xs text-gray-500">by {{ p.author || 'System' }}</em></span>
                    <button @click="openEditor(p)" class="text-blue-500 hover:text-blue-700">Clone & Edit</button>
                </div>
            </div>
        </div>
    </section>

    <!-- Personality Editor Modal (Conceptual) -->
    <!-- A real implementation would use a separate component and the uiStore to manage the modal state -->
    <div v-if="isEditorOpen" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-xl w-full max-w-lg">
        <h3 class="text-lg font-bold mb-4">{{ editorPersonality.id ? 'Edit' : 'Create' }} Personality</h3>
        <!-- A full form for editorPersonality would go here -->
        <p>Name: <input v-model="editorPersonality.name" class="input-field"></p>
        <p class="mt-2">Prompt: <textarea v-model="editorPersonality.prompt_text" rows="5" class="input-field"></textarea></p>
        <div class="flex justify-end space-x-2 mt-4">
          <button @click="isEditorOpen = false" class="btn btn-secondary">Cancel</button>
          <button @click="handleSavePersonality(editorPersonality)" class="btn btn-primary">Save</button>
        </div>
      </div>
    </div>
</template>