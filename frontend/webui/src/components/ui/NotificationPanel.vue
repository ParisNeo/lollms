<script setup>
import { ref, watch, onUnmounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useUiStore } from '../../stores/ui';

const uiStore = useUiStore();
const { notifications } = storeToRefs(uiStore);

const timers = ref({});

const getIcon = (type) => {
  switch (type) {
    case 'success':
      return '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" /></svg>';
    case 'error':
      return '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" /></svg>';
    case 'warning':
      return '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8.257 3.099c.636-1.1 2.15-1.1 2.786 0l5.482 9.5a1.75 1.75 0 01-1.528 2.65H4.293a1.75 1.75 0 01-1.528-2.65l5.482-9.5zM10 14a1 1 0 100-2 1 1 0 000 2zm-1-4a1 1 0 011-1h.01a1 1 0 110 2H10a1 1 0 01-1-1z" clip-rule="evenodd" /></svg>';
    case 'copy':
      return '<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>';
    case 'close':
      return '<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>';
    default:
      return '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" /></svg>';
  }
};

const getTypeClass = (type) => {
  switch (type) {
    case 'success':
      return 'bg-green-500 text-white';
    case 'error':
      return 'bg-red-500 text-white';
    case 'warning':
      return 'bg-yellow-500 text-black';
    default:
      return 'bg-blue-500 text-white';
  }
};

const pauseAndClearTimer = (notificationId) => {
  if (timers.value[notificationId]) {
    clearTimeout(timers.value[notificationId]);
    delete timers.value[notificationId];
  }
};

const startTimer = (notification, durationOverride = null) => {
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

const copyMessage = (message) => {
  uiStore.copyToClipboard(message);
};

watch(notifications, (currentNotifications) => {
  const currentIds = new Set(currentNotifications.map((n) => n.id));

  // Start timers for any new notification that doesn't have one yet.
  for (const notification of currentNotifications) {
    if (notification.duration > 0 && !timers.value[notification.id]) {
      startTimer(notification);
    }
  }

  // Clean up timers for any notification that has been removed.
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
  <div class="fixed bottom-4 right-4 z-[9999] w-full max-w-sm space-y-2">
    <transition-group name="list">
      <div
        v-for="notification in notifications"
        :key="notification.id"
        class="flex items-start p-3 rounded-md shadow-lg"
        :class="getTypeClass(notification.type)"
        @mouseenter="pauseAndClearTimer(notification.id)"
        @mouseleave="startTimer(notification, 1000)"
      >
        <div class="flex items-center flex-grow">
          <div
            class="flex-shrink-0"
            v-html="getIcon(notification.type)"
          ></div>
          <div class="ml-3 text-sm font-medium break-all">
            {{ notification.message }}
          </div>
        </div>

        <div class="ml-4 flex-shrink-0 flex space-x-2">
          <button
            class="p-1 rounded-full hover:bg-black/20 focus:outline-none focus:ring-2 focus:ring-white/50 transition-colors"
            @click="copyMessage(notification.message)"
          >
            <span class="sr-only">Copy message</span>
            <div v-html="getIcon('copy')"></div>
          </button>
          <button
            class="p-1 rounded-full hover:bg-black/20 focus:outline-none focus:ring-2 focus:ring-white/50 transition-colors"
            @click="handleClose(notification.id)"
          >
            <span class="sr-only">Close notification</span>
            <div v-html="getIcon('close')"></div>
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