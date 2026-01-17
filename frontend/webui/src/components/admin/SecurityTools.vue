<script setup>
import { ref } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import IconShieldCheck from '../../assets/icons/IconShieldCheck.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconLock from '../../assets/icons/IconLock.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const isSanitizing = ref(false);

async function handleSanitize() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Run Content Sanitization?',
        message: 'This will scan all existing posts, comments, and messages in the database and strip out potentially malicious scripts. This operation might take a while.',
        confirmText: 'Run Scan',
        isDanger: false
    });

    if (confirmed.confirmed) {
        isSanitizing.value = true;
        try {
            await adminStore.sanitizeDatabase();
            uiStore.addNotification("Sanitization task started. Check Task Manager.", "info");
        } catch (error) {
            console.error(error);
            uiStore.addNotification("Failed to start sanitization.", "error");
        } finally {
            isSanitizing.value = false;
        }
    }
}
</script>

<template>
    <div class="space-y-6 animate-fade-in-up">
        <div class="flex items-center gap-3 mb-6">
            <div class="p-3 bg-indigo-100 dark:bg-indigo-900/30 rounded-lg text-indigo-600 dark:text-indigo-400">
                <IconShieldCheck class="w-8 h-8" />
            </div>
            <div>
                <h2 class="text-2xl font-bold text-gray-900 dark:text-white">Security & Maintenance</h2>
                <p class="text-sm text-gray-500 dark:text-gray-400">Manage application security and data integrity.</p>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Content Sanitization Card -->
            <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
                <div class="p-6">
                    <div class="flex items-start justify-between">
                        <div class="flex items-center gap-3">
                            <IconRefresh class="w-6 h-6 text-green-500" />
                            <h3 class="text-lg font-semibold text-gray-900 dark:text-white">Database Sanitization</h3>
                        </div>
                    </div>
                    <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
                        Scan existing database content (Posts, Comments, DMs) to retroactively remove XSS scripts and malicious tags.
                        Run this after updates to security policies.
                    </p>
                    <div class="mt-6">
                        <button 
                            @click="handleSanitize" 
                            :disabled="isSanitizing"
                            class="w-full btn btn-primary flex items-center justify-center gap-2"
                        >
                            <IconShieldCheck class="w-5 h-5" />
                            {{ isSanitizing ? 'Starting Task...' : 'Run Content Sanitizer' }}
                        </button>
                    </div>
                </div>
                <div class="bg-gray-50 dark:bg-gray-700/50 px-6 py-3 border-t border-gray-200 dark:border-gray-700">
                    <span class="text-xs text-gray-500 flex items-center gap-1">
                        <IconLock class="w-3 h-3" />
                        Recommended: Run periodically or after major updates.
                    </span>
                </div>
            </div>

            <!-- Future Tool Placeholder -->
            <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-dashed border-gray-300 dark:border-gray-600 flex flex-col items-center justify-center p-8 opacity-60">
                <IconShieldCheck class="w-10 h-10 text-gray-300 dark:text-gray-600 mb-2" />
                <p class="text-sm font-medium text-gray-500">More security tools coming soon.</p>
            </div>
        </div>
    </div>
</template>
