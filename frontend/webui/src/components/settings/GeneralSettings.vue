<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import { storeToRefs } from 'pinia';

const authStore = useAuthStore();
const dataStore = useDataStore();

const { user } = storeToRefs(authStore);
// The 'languages' ref now comes from the dataStore and includes the fallback logic
const { languages } = storeToRefs(dataStore);

const form = ref({
    user_ui_level: 0,
    first_page: 'feed',
    ai_response_language: 'auto',
    auto_title: false,
    show_token_counter: true,
    fun_mode: false,
    put_thoughts_in_context: false
});

const isSaving = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

const uiLevels = [
    { value: 0, label: 'Beginner' },
    { value: 1, label: 'Novice' },
    { value: 2, label: 'Intermediate' },
    { value: 3, label: 'Advanced' },
    { value: 4, label: 'Expert' }
];

const homePages = [
    { value: 'feed', label: 'Social Feed' },
    { value: 'discussions', label: 'Discussions View' },
    { value: 'new_discussion', label: 'New Discussion' },
    { value: 'last_discussion', label: 'Last Used Discussion' }
];

function populateForm() {
    if (!user.value) return;

    form.value = {
        user_ui_level: user.value.user_ui_level,
        first_page: user.value.first_page || 'feed',
        ai_response_language: user.value.ai_response_language || 'auto',
        auto_title: user.value.auto_title,
        show_token_counter: user.value.show_token_counter,
        fun_mode: user.value.fun_mode,
        put_thoughts_in_context: user.value.put_thoughts_in_context
    };
    pristineState = JSON.stringify(form.value);
    hasChanges.value = false;
}

onMounted(() => {
    populateForm();
    // Trigger fetch if not already loaded
    dataStore.fetchLanguages();
});

watch(user, populateForm, { deep: true, immediate: true });

watch(form, (newValue) => {
    hasChanges.value = JSON.stringify(newValue) !== pristineState;
}, { deep: true });

async function handleSave() {
    isSaving.value = true;
    try {
        await authStore.updateUserPreferences(form.value);
    } finally {
        isSaving.value = false;
    }
}
</script>

<template>
    <div class="space-y-10">
        <form @submit.prevent="handleSave" v-if="user">
            <div class="space-y-8">
                <div>
                    <h3 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">General Settings</h3>
                    <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Customize your user experience and interface preferences.</p>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
                    <!-- UI Level -->
                    <div>
                        <label for="uiLevel" class="block text-sm font-medium text-gray-700 dark:text-gray-300">UI Level</label>
                        <select id="uiLevel" v-model.number="form.user_ui_level" class="input-field mt-1">
                            <option v-for="level in uiLevels" :key="level.value" :value="level.value">{{ level.label }}</option>
                        </select>
                        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">Controls the complexity and number of features shown.</p>
                    </div>

                    <!-- Default Home Page -->
                    <div>
                        <label for="homePage" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Default Home Page</label>
                        <select id="homePage" v-model="form.first_page" class="input-field mt-1">
                            <option v-for="page in homePages" :key="page.value" :value="page.value">{{ page.label }}</option>
                        </select>
                        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">Choose the first page you see after logging in.</p>
                    </div>

                    <!-- AI Response Language -->
                    <div>
                        <label for="language" class="block text-sm font-medium text-gray-700 dark:text-gray-300">AI Response Language</label>
                        <select id="language" v-model="form.ai_response_language" class="input-field mt-1">
                           <option v-for="lang in languages" :key="lang.value" :value="lang.value">{{ lang.label }}</option>
                        </select>
                        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">Instruct the AI to respond in a specific language.</p>
                    </div>
                </div>

                <div class="space-y-6 pt-6 border-t dark:border-gray-700">
                    <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                        <span class="flex-grow flex flex-col pr-4">
                            <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Auto Generate Discussion Titles</span>
                            <span class="text-xs text-gray-500 dark:text-gray-400">Automatically create a title for new discussions.</span>
                        </span>
                        <button @click="form.auto_title = !form.auto_title" type="button" :class="[form.auto_title ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800']">
                            <span :class="[form.auto_title ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>
                     <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                        <span class="flex-grow flex flex-col pr-4">
                            <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Show Token Counter</span>
                            <span class="text-xs text-gray-500 dark:text-gray-400">Display a token counter in the chat input bar.</span>
                        </span>
                        <button @click="form.show_token_counter = !form.show_token_counter" type="button" :class="[form.show_token_counter ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800']">
                            <span :class="[form.show_token_counter ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>
                    <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                        <span class="flex-grow flex flex-col pr-4">
                            <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Fun Mode</span>
                             <span class="text-xs text-gray-500 dark:text-gray-400">Enables more playful and whimsical AI responses.</span>
                        </span>
                         <button @click="form.fun_mode = !form.fun_mode" type="button" :class="[form.fun_mode ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800']">
                            <span :class="[form.fun_mode ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>
                    <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                        <span class="flex-grow flex flex-col pr-4">
                            <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Include AI Thoughts in Context</span>
                            <span class="text-xs text-gray-500 dark:text-gray-400">AI's internal "thoughts" will be part of the next turn's history.</span>
                        </span>
                        <button @click="form.put_thoughts_in_context = !form.put_thoughts_in_context" type="button" :class="[form.put_thoughts_in_context ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800']">
                            <span :class="[form.put_thoughts_in_context ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>
                </div>
            </div>

            <div class="mt-8 pt-5 border-t border-gray-200 dark:border-gray-700">
                <div class="flex justify-end">
                    <button type="submit" class="btn btn-primary" :disabled="isSaving || !hasChanges">
                        {{ isSaving ? 'Saving...' : 'Save General Settings' }}
                    </button>
                </div>
            </div>
        </form>
    </div>
</template>