<script setup>
import { ref } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import IconSend from '../../assets/icons/IconSend.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const message = ref('');
const isLoading = ref(false);

async function handleBroadcast() {
    if (!message.value.trim() || isLoading.value) return;
    
    const confirmed = await uiStore.showConfirmation({
        title: 'Confirm Broadcast',
        message: 'This will send a notification to all currently connected users. Are you sure?',
        confirmText: 'Broadcast'
    });

    if (!confirmed) return;

    isLoading.value = true;
    try {
        await adminStore.broadcastMessage(message.value);
        uiStore.addNotification('Broadcast sent successfully!', 'success');
        message.value = '';
    } catch (error) {
        // Error is handled globally
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="p-6 border-b border-gray-200 dark:border-gray-700">
            <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                Broadcast Notification
            </h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Send a persistent notification message to all online users. It will remain visible until they close it.
            </p>
        </div>
        <form @submit.prevent="handleBroadcast" class="p-6">
            <div class="space-y-4">
                <div>
                    <label for="broadcast-message" class="block text-sm font-medium">Message</label>
                    <textarea
                        id="broadcast-message"
                        v-model="message"
                        rows="4"
                        class="input-field mt-1"
                        placeholder="Enter your notification message here..."
                        required
                    ></textarea>
                </div>
            </div>
            <div class="mt-8 pt-5 border-t border-gray-200 dark:border-gray-700">
                <div class="flex justify-end">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !message.trim()">
                        <IconAnimateSpin v-if="isLoading" class="w-5 h-5 mr-2" />
                        <IconSend v-else class="w-5 h-5 mr-2" />
                        {{ isLoading ? 'Sending...' : 'Send Broadcast' }}
                    </button>
                </div>
            </div>
        </form>
    </div>
</template>