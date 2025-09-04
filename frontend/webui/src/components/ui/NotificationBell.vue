<script setup>
import { ref, computed } from 'vue';
import { useSocialStore } from '../../stores/social';
import { useUiStore } from '../../stores/ui';
import { useRouter } from 'vue-router';
import UserAvatar from './UserAvatar.vue';

const socialStore = useSocialStore();
const uiStore = useUiStore();
const router = useRouter();

const isOpen = ref(false);
const triggerRef = ref(null);

const totalUnreadCount = computed(() => socialStore.totalUnreadDms);
const recentConversations = computed(() => {
    return socialStore.conversations
        .filter(c => c.unread_count > 0)
        .slice(0, 5); // Show up to 5 recent unread conversations
});

function toggleDropdown() {
    isOpen.value = !isOpen.value;
}

function closeDropdown() {
    isOpen.value = false;
}

async function goToMessages(convo) {
    await router.push('/messages');
    socialStore.openConversation({
        id: convo.partner_user_id,
        username: convo.partner_username,
        icon: convo.partner_icon,
    });
    closeDropdown();
}

const vOnClickOutside = {
  mounted: (el, binding) => {
    el.clickOutsideEvent = event => {
      const triggerEl = triggerRef.value;
      if (!(el === event.target || el.contains(event.target) || triggerEl?.contains(event.target))) {
        binding.value();
      }
    };
    document.addEventListener('mousedown', el.clickOutsideEvent);
  },
  unmounted: el => {
    document.removeEventListener('mousedown', el.clickOutsideEvent);
  },
};
</script>

<template>
    <div class="relative" ref="triggerRef">
        <button @click="toggleDropdown" class="btn-icon" title="Notifications">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            <span v-if="totalUnreadCount > 0" class="absolute -top-1 -right-1 flex h-5 w-5">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-5 w-5 bg-red-500 text-white text-xs items-center justify-center">
                    {{ totalUnreadCount }}
                </span>
            </span>
        </button>
        <transition
            enter-active-class="transition ease-out duration-100"
            enter-from-class="transform opacity-0 scale-95"
            enter-to-class="transform opacity-100 scale-100"
            leave-active-class="transition ease-in duration-75"
            leave-from-class="transform opacity-100 scale-100"
            leave-to-class="transform opacity-0 scale-95"
        >
            <div 
                v-if="isOpen"
                v-on-click-outside="closeDropdown"
                class="absolute right-0 mt-2 w-80 origin-top-right rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 dark:ring-gray-700 z-20"
            >
                <div class="p-2 border-b dark:border-gray-700">
                    <h3 class="font-semibold text-sm">Notifications</h3>
                </div>
                <div class="max-h-96 overflow-y-auto">
                    <div v-if="recentConversations.length === 0" class="p-4 text-center text-sm text-gray-500">
                        No new notifications.
                    </div>
                    <ul v-else>
                        <li v-for="convo in recentConversations" :key="convo.partner_user_id">
                            <a href="#" @click.prevent="goToMessages(convo)" class="flex items-center p-3 hover:bg-gray-100 dark:hover:bg-gray-700">
                                <UserAvatar :icon="convo.partner_icon" :username="convo.partner_username" size-class="h-8 w-8" />
                                <div class="ml-3">
                                    <p class="text-sm font-medium">{{ convo.partner_username }}</p>
                                    <p class="text-xs text-gray-500 truncate max-w-xs">{{ convo.last_message }}</p>
                                </div>
                                <span class="ml-auto text-xs font-bold text-white bg-red-500 rounded-full h-5 w-5 flex items-center justify-center">{{ convo.unread_count }}</span>
                            </a>
                        </li>
                    </ul>
                </div>
                <div class="p-2 border-t dark:border-gray-700">
                    <router-link to="/messages" @click="closeDropdown" class="block w-full text-center text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline">
                        View All Messages
                    </router-link>
                </div>
            </div>
        </transition>
    </div>
</template>