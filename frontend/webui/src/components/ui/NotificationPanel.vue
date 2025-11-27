<script setup>
import { computed, watch, onUnmounted, ref } from 'vue';
import { useUiStore } from '../../stores/ui';
import { storeToRefs } from 'pinia';

// Import Icon Components
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconError from '../../assets/icons/IconError.vue';
import IconClose from '../../assets/icons/IconClose.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconSend from '../../assets/icons/IconSend.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';

const uiStore = useUiStore();
const { notifications } = storeToRefs(uiStore);

const timers = ref({});

const getIcon = (type) => {
  switch (type) {
    case 'success': return IconCheckCircle;
    case 'error': return IconError;
    case 'warning': return IconInfo; // Using Info for warning
    case 'broadcast': return IconSend;
    case 'copy': return IconCopy;
    case 'close': return IconClose;
    default: return IconInfo;
  }
};

const getTypeClass = (type) => {
  switch (type) {
    case 'success': return 'bg-green-500 text-white';
    case 'error': return 'bg-red-500 text-white';
    case 'warning': return 'bg-yellow-500 text-black';
    case 'broadcast': return 'bg-blue-600 text-white';
    default: return 'bg-blue-500 text-white';
  }
};

const pauseAndClearTimer = (notificationId) => {
  if (timers.value[notificationId]) {
    clearTimeout(timers.value[notificationId]);
    delete timers.value[notificationId];
  }
};

const startTimer = (notification, durationOverride = null) => {
  if (notification.persistent) return; // Do not start timers for persistent notifications

  pauseAndClearTimer(notification.id);
  const dismissalTime = durationOverride ?? notification.duration;
  if (dismissalTime > 0) {
    timers.value[notification.id] = setTimeout(() => {
      uiStore.removeNotification(notification.id);
    }, dismissalTime);
  }
};

const handleClose = (notificationId) => {
  pauseAndClearTimer(notificationId);
  uiStore.removeNotification(notificationId);
};

const clearAll = () => {
    // Clear all timers first
    Object.values(timers.value).forEach(clearTimeout);
    timers.value = {};
    // Assuming uiStore has a clear method or we empty the array if exposed
    if (uiStore.notifications) {
        // If we can't replace the array ref directly, we splice it
        uiStore.notifications.splice(0, uiStore.notifications.length);
    }
};

const copyMessage = (message) => {
  uiStore.copyToClipboard(message);
};

watch(notifications, (currentNotifications) => {
  const currentIds = new Set(currentNotifications.map((n) => n.id));

  for (const notification of currentNotifications) {
    if (notification.duration > 0 && !notification.persistent && !timers.value[notification.id]) {
      startTimer(notification);
    }
  }

  for (const timerId in timers.value) {
    if (!currentIds.has(Number(timerId))) {
      pauseAndClearTimer(Number(timerId));
    }
  }
}, { deep: true });

onUnmounted(() => {
  Object.values(timers.value).forEach(clearTimeout);
});
</script>

<template>
  <div class="fixed bottom-4 right-4 z-[9999] w-full max-w-sm space-y-2 flex flex-col items-end">
    <!-- Clear All Button -->
    <button 
        v-if="notifications.length > 1" 
        @click="clearAll"
        class="mb-2 px-3 py-1 bg-gray-800 text-white text-xs rounded-full shadow hover:bg-gray-700 transition-colors flex items-center gap-1"
    >
        <IconTrash class="w-3 h-3" /> Clear All
    </button>

    <transition-group name="list">
      <div
        v-for="notification in notifications"
        :key="notification.id"
        class="flex items-start p-3 rounded-md shadow-lg w-full"
        :class="getTypeClass(notification.type)"
        @mouseenter="pauseAndClearTimer(notification.id)"
        @mouseleave="startTimer(notification, 1000)"
      >
        <div class="flex items-center flex-grow min-w-0">
          <div class="flex-shrink-0 w-6 h-6 flex items-center justify-center">
            <component :is="getIcon(notification.type)" class="h-5 w-5" />
          </div>
          <div class="ml-3 text-sm font-medium break-words">
             <p v-if="notification.type === 'broadcast'" class="font-bold text-xs uppercase opacity-80">
                Broadcast<span v-if="notification.sender"> from {{ notification.sender }}</span>
            </p>
            {{ notification.message }}
          </div>
        </div>

        <div class="ml-4 flex-shrink-0 flex space-x-2">
          <button
            class="p-1 rounded-full hover:bg-black/20 focus:outline-none focus:ring-2 focus:ring-white/50 transition-colors"
            @click="copyMessage(notification.message)"
            title="Copy message"
          >
            <span class="sr-only">Copy message</span>
            <component :is="getIcon('copy')" class="h-4 w-4" />
          </button>
          <button
            class="p-1 rounded-full hover:bg-black/20 focus:outline-none focus:ring-2 focus:ring-white/50 transition-colors"
            @click="handleClose(notification.id)"
            title="Close notification"
          >
            <span class="sr-only">Close notification</span>
            <component :is="getIcon('close')" class="h-4 w-4" />
          </button>
        </div>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
.list-enter-active,
.list-leave-active {
  transition: all 0.5s ease;
}
.list-enter-from,
.list-leave-to {
  opacity: 0;
  transform: translateX(30px);
}
</style>
