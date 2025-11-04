<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';

const adminStore = useAdminStore();

const form = ref({
    rss_feed_enabled: false,
    rss_feed_check_interval_minutes: 60
});
const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

const newsFeedSettings = computed(() => {
    return adminStore.globalSettings.filter(s => s.category === 'News Feed');
});

onMounted(() => {
    if (adminStore.globalSettings.length === 0) {
        adminStore.fetchGlobalSettings();
    } else {
        populateForm();
    }
});

watch(() => adminStore.globalSettings, populateForm, { deep: true });

watch(form, (newValue) => {
    hasChanges.value = JSON.stringify(newValue) !== pristineState;
}, { deep: true });

function populateForm() {
    const newFormState = {};
    if (newsFeedSettings.value.length > 0) {
        newsFeedSettings.value.forEach(setting => {
            newFormState[setting.key] = setting.value;
        });
        form.value = { ...form.value, ...newFormState };
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
    }
}

async function handleSave() {
    isLoading.value = true;
    try {
        await adminStore.updateGlobalSettings({ ...form.value });
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="p-6 border-b border-gray-200 dark:border-gray-700">
            <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                News Feed Settings
            </h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Enable and configure the automatic fetching and processing of RSS feeds.
            </p>
        </div>
        <form v-if="Object.keys(form).length" @submit.prevent="handleSave" class="p-6">
            <div class="space-y-6">
                <div class="toggle-container">
                    <span class="toggle-label">
                        Enable RSS Feed Service
                        <span class="toggle-description">Globally enables or disables the automatic checking of RSS feeds.</span>
                    </span>
                    <button @click="form.rss_feed_enabled = !form.rss_feed_enabled" type="button" :class="[form.rss_feed_enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'toggle-switch']">
                        <span :class="[form.rss_feed_enabled ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                    </button>
                </div>

                <div :class="{'opacity-50 cursor-not-allowed': !form.rss_feed_enabled}">
                    <label for="rss-interval" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Check Interval (minutes)</label>
                    <input 
                        id="rss-interval" 
                        v-model.number="form.rss_feed_check_interval_minutes" 
                        type="number" 
                        min="1"
                        class="input-field mt-1" 
                        :disabled="!form.rss_feed_enabled"
                    />
                    <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">How often the server should check for new articles. A server restart is required for this change to take effect.</p>
                </div>
            </div>

            <div class="mt-8 pt-5 border-t border-gray-200 dark:border-gray-700">
                <div class="flex justify-end">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">
                        {{ isLoading ? 'Saving...' : 'Save Settings' }}
                    </button>
                </div>
            </div>
        </form>
    </div>
</template>

<style scoped>
.toggle-container { @apply flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg; }
.toggle-label { @apply flex-grow flex flex-col text-sm font-medium text-gray-900 dark:text-gray-100; }
.toggle-description { @apply text-xs text-gray-500 dark:text-gray-400 font-normal mt-1; }
.toggle-switch { @apply relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out; }
.toggle-knob { @apply pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out; }
</style>