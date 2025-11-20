<script setup>
import { ref } from 'vue';
import { useAdminStore } from '../../stores/admin';
import apiClient from '../../services/api';
import { useUiStore } from '../../stores/ui';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const message = ref('');
const isSending = ref(false);
const broadcastType = ref('notification'); // 'notification' or 'dm'

async function sendBroadcast() {
    if (!message.value.trim()) return;
    
    isSending.value = true;
    try {
        if (broadcastType.value === 'notification') {
            await adminStore.broadcastMessage(message.value);
            uiStore.addNotification('Broadcast notification sent!', 'success');
        } else {
            await apiClient.post('/api/dm/broadcast', { content: message.value });
            uiStore.addNotification('DM broadcast task started. Check Tasks for progress.', 'success');
        }
        message.value = '';
    } catch (error) {
        uiStore.addNotification('Failed to send broadcast.', 'error');
    } finally {
        isSending.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg p-6">
        <h3 class="text-xl font-semibold mb-4 text-gray-800 dark:text-gray-100">Broadcast Message</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
            Send a message to all active users.
        </p>
        
        <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Broadcast Type</label>
            <div class="flex items-center space-x-4">
                <label class="flex items-center cursor-pointer">
                    <input type="radio" v-model="broadcastType" value="notification" class="form-radio text-blue-600">
                    <span class="ml-2 text-sm text-gray-700 dark:text-gray-300">System Notification (Toast)</span>
                </label>
                <label class="flex items-center cursor-pointer">
                    <input type="radio" v-model="broadcastType" value="dm" class="form-radio text-blue-600">
                    <span class="ml-2 text-sm text-gray-700 dark:text-gray-300">Direct Message (DM)</span>
                </label>
            </div>
        </div>

        <textarea 
            v-model="message" 
            rows="4" 
            class="input-field w-full mb-4" 
            placeholder="Type your message here..."
        ></textarea>
        
        <div class="flex justify-end">
            <button 
                @click="sendBroadcast" 
                :disabled="isSending || !message.trim()" 
                class="btn btn-primary"
            >
                {{ isSending ? 'Sending...' : 'Broadcast' }}
            </button>
        </div>
    </div>
</template>
