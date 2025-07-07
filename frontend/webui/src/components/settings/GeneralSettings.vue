<script setup>
import { ref, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../../stores/auth';

const authStore = useAuthStore();
const { user } = storeToRefs(authStore);

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
        label: 'Fun Mode',
        description: 'If activated, the AI will be more playful and creative.',
        defaultValue: false
    },
    {
        key: 'chat_active',
        type: 'toggle',
        label: 'Activate Social Chat',
        description: 'Enable or disable direct messaging with other users.',
        defaultValue: false,
        minLevel: 2 // Requires Intermediate level or higher
    },
    {
        key: 'user_ui_level',
        type: 'select',
        label: 'UI Level',
        description: 'Adjust the complexity of the user interface. More advanced levels show more options.',
        defaultValue: 0,
        options: [
            { value: 0, text: 'Beginner' },
            { value: 1, text: 'Novice' },
            { value: 2, text: 'Intermediate' },
            { value: 3, text: 'Advanced' },
            { value: 4, text: 'Expert' }
        ]
    },
    {
        key: 'first_page',
        type: 'select',
        label: 'Home Page',
        description: 'Choose the default page you see after logging in.',
        defaultValue: 'feed',
        options: [
            { value: 'feed', text: 'Social Feed', minLevel: 2 },
            { value: 'new_discussion', text: 'New Discussion' },
            { value: 'last_discussion', text: 'Last Used Discussion' }
        ]
    },
    {
        key: 'ai_response_language',
        type: 'select',
        label: 'AI Response Language',
        description: 'Changes the output language of the AI messages.',
        defaultValue: 'auto',
        options: [
            { value: "auto", text: 'Auto' },
            { value: "en", text: 'English' },
            { value: "fr", text: 'French' },
            { value: "it", text: 'Italian' },
            { value: "es", text: 'Spanish' } // Corrected typo
        ]
    }
];

const form = ref({});
const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = {};

const populateForm = () => {
    if (user.value) {
        const newFormState = {};
        settingsConfig.forEach(setting => {
            newFormState[setting.key] = user.value[setting.key] ?? setting.defaultValue;
        });
        form.value = newFormState;
        pristineState = JSON.parse(JSON.stringify(form.value));
        hasChanges.value = false;
    }
};

onMounted(populateForm);
watch(user, populateForm, { deep: true });

watch(form, (newValue, oldValue) => {
    hasChanges.value = JSON.stringify(newValue) !== JSON.stringify(pristineState);

    // Business rule: When switching to Novice, set default first page to 'new_discussion'
    if (oldValue && newValue.user_ui_level === 1 && oldValue.user_ui_level !== 1) {
        form.value.first_page = 'new_discussion';
    }

    // Business rule: If UI level is too low for the selected first page, reset it
    if (newValue.user_ui_level < 2 && newValue.first_page === 'feed') {
        form.value.first_page = 'new_discussion';
    }
}, { deep: true });

async function handleSave() {
    isLoading.value = true;
    try {
        await authStore.updateUserPreferences(form.value);
    } catch (error) {
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
            <form v-if="user" @submit.prevent="handleSave" class="p-4 sm:p-6 space-y-8">
                <div v-for="setting in settingsConfig" :key="setting.key">
                    <!-- Renders a Select (Dropdown) Input -->
                    <div v-if="setting.type === 'select'">
                        <label :for="setting.key" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {{ setting.label }}
                        </label>
                        <select
                            :id="setting.key"
                            v-model="form[setting.key]"
                            class="input-field mt-1"
                            :value="form[setting.key]"
                        >
                            <option v-for="option in setting.options.filter(o => !o.minLevel || user.user_ui_level >= o.minLevel)" :key="option.value" :value="option.value">
                                {{ option.text }}
                            </option>
                        </select>
                        <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">{{ setting.description }}</p>
                    </div>

                    <!-- Renders a Toggle (Checkbox) Input -->
                    <div v-if="setting.type === 'toggle' && (!setting.minLevel || user.user_ui_level >= setting.minLevel)" class="relative flex items-start">
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
