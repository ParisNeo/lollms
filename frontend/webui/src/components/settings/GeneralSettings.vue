<script setup>
import { ref, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../../stores/auth';
// useDataStore is not needed for these settings, but kept in case you add settings that need it.
import { useDataStore } from '../../stores/data';

const authStore = useAuthStore();
const dataStore = useDataStore(); // Kept for future use

// Use storeToRefs to get reactive state from the stores
const { user } = storeToRefs(authStore);

// ====================================================================================
// Settings Configuration
// To add a new setting, simply add a new object to this array.
// The template will automatically generate the correct input field.
//
// Supported types: 'toggle', 'select'
// - key: The property name in the user object and the form state.
// - type: Determines the UI control to render.
// - label: The main text label for the setting.
// - description: Helper text shown below the label or control.
// - defaultValue: The value to use if the setting is not present on the user object.
// - options (for 'select' type): An array of { value, text } objects for the dropdown.
// ====================================================================================
const settingsConfig = [
    {
        key: 'auto_title',
        type: 'toggle',
        label: 'Automatic Discussion Title',
        description: 'If enabled, a title will be automatically generated for new discussions.',
        defaultValue: true
    },
    {
        key: 'fun_mode',
        type: 'toggle',
        label: 'Fun mode',
        description: 'If activated, the AI will be more funny.',
        defaultValue: true
    },
    {
        key: 'chat_active',
        type: 'toggle',
        label: 'Activate chat',
        description: 'If activated, the user will be able to communicate with other users via DMs.',
        defaultValue: true
    },
    {
        key: 'user_ui_level',
        type: 'select',
        label: 'UI Level',
        description: 'Adjust the complexity of the user interface. More advanced levels show more options.',
        defaultValue: 0, // 'Beginner'
        options: [
            { value: 0, text: 'Beginner' },
            { value: 1, text: 'Novice' },
            { value: 2, text: 'Intermediate' },
            { value: 3, text: 'Advanced' },
            { value: 4, text: 'Expert' }
        ]
    },
    {
        key: 'ai_response_language',
        type: 'select',
        label: 'AI Response language',
        description: 'Changes the output language of the AI messages.',
        defaultValue: 0, // 'Beginner'
        options: [
            { value: "auto", text: 'Auto' },
            { value: "en", text: 'English' },
            { value: "fr", text: 'French' },
            { value: "it", text: 'Italian' },
            { value: "es", text: 'Espagnol' }
        ]
    }
    // Future settings can be added here, e.g.:
    // {
    //     key: 'theme',
    //     type: 'select',
    //     label: 'Application Theme',
    //     description: 'Choose your preferred color theme.',
    //     defaultValue: 'system',
    //     options: [
    //         { value: 'light', text: 'Light' },
    //         { value: 'dark', text: 'Dark' },
    //         { value: 'system', text: 'System Default' }
    //     ]
    // }
];

// Reactive form state, dynamically created from the config
const form = ref({});

const isLoading = ref(false);
const hasChanges = ref(false);

// A pristine copy to compare against for changes
let pristineState = {};

// Function to populate form from user state and set pristine state
const populateForm = () => {
    if (user.value) {
        const newFormState = {};
        console.log(settingsConfig)
        console.log(user.value)
        // Populate form based on the settingsConfig, using user values or defaults
        settingsConfig.forEach(setting => {
            newFormState[setting.key] = user.value[setting.key] ?? setting.defaultValue;
        });
        form.value = newFormState;

        pristineState = JSON.parse(JSON.stringify(form.value));
        hasChanges.value = false; // Reset on populate
    }
};

// Populate form on mount and when user data changes
onMounted(populateForm);
watch(user, populateForm, { deep: true });

// Watch for changes in the form to enable/disable the save button
watch(form, (newValue) => {
    hasChanges.value = JSON.stringify(newValue) !== JSON.stringify(pristineState);
}, { deep: true });

// Handle form submission
async function handleSave() {
    isLoading.value = true;
    try {
        await authStore.updateUserPreferences(form.value);
        // The user watcher will repopulate the form and reset pristineState after the update is successful
    } catch (error) {
        // Error notification is assumed to be handled by an API interceptor or store action
        console.error("Failed to save settings:", error);
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="px-4 py-5 sm:p-6">
            <h2 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">General Settings</h2>
            <p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">
                Customize your user interface experience and general application behavior.
            </p>
        </div>
        <div class="border-t border-gray-200 dark:border-gray-700">
            <form @submit.prevent="handleSave" class="p-4 sm:p-6 space-y-8">
                <!-- Dynamically generate form fields from settingsConfig -->
                <div v-for="setting in settingsConfig" :key="setting.key">
                    <!-- Renders a Select (Dropdown) Input -->
                    <div v-if="setting.type === 'select'">
                        <label :for="setting.key" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {{ setting.label }}
                        </label>
                        <select
                            :id="setting.key"
                            v-model.number="form[setting.key]"
                            class="input-field mt-1"
                        >
                            <option v-for="option in setting.options" :key="option.value" :value="option.value">
                                {{ option.text }}
                            </option>
                        </select>
                        <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">{{ setting.description }}</p>
                    </div>

                    <!-- Renders a Toggle (Checkbox) Input -->
                    <div v-if="setting.type === 'toggle'" class="relative flex items-start">
                        <div class="flex h-6 items-center">
                            <input
                                :id="setting.key"
                                v-model="form[setting.key]"
                                type="checkbox"
                                class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 text-blue-600 focus:ring-blue-600 dark:focus:ring-blue-600 dark:ring-offset-gray-800"
                            >
                        </div>
                        <div class="ml-3 text-sm leading-6">
                            <label :for="setting.key" class="font-medium text-gray-900 dark:text-gray-300">
                                {{ setting.label }}
                            </label>
                            <p class="text-gray-500 dark:text-gray-400">{{ setting.description }}</p>
                        </div>
                    </div>
                </div>

                <!-- Save Button -->
                <div class="flex justify-end pt-4">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">
                        <span v-if="isLoading">Saving...</span>
                        <span v-else>Save General Settings</span>
                    </button>
                </div>
            </form>
        </div>
    </div>
</template>