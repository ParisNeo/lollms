<script setup>
import { onMounted, computed, ref } from 'vue';
import { useSocialStore } from '../../stores/social';
import { useAuthStore } from '../../stores/auth'; // To get friends list
import UserAvatar from '../ui/UserAvatar.vue';

const socialStore = useSocialStore();
const authStore = useAuthStore(); // Assuming friends list is part of auth/user data

// We need a way to get friends. Let's assume a getter or action in authStore.
// This might need to be created if it doesn't exist.
// For now, we'll placeholder it.
const friends = ref([]); // Placeholder
const conversations = computed(() => socialStore.conversations);
const isLoading = computed(() => socialStore.isLoadingConversations);

// This is a placeholder for fetching friends.
// Ideally, this lives in the authStore or a new friendsStore.
async function fetchFriends() {
    // try {
    //     friends.value = await authStore.fetchFriends();
    // } catch(e) { console.error("Could not fetch friends for DM footer", e); }
}


onMounted(() => {
  socialStore.fetchConversations();
  fetchFriends();
});

function openDm(user) {
    // This will find the user object in either friends or conversations list
    // and pass it to the openConversation action.
    const partner = {
        id: user.partner_user_id || user.id,
        username: user.partner_username || user.username,
        icon: user.icon || null // We might need to fetch the icon separately
    };
    socialStore.openConversation(partner);
}

// Combine and de-duplicate friends and conversation partners for the list
const contactList = computed(() => {
    const contacts = new Map();

    // Add people from conversations
    conversations.value.forEach(convo => {
        contacts.set(convo.partner_user_id, {
            id: convo.partner_user_id,
            username: convo.partner_username,
            unread_count: convo.unread_count,
            // Assuming we need to fetch icon
        });
    });

    // Add friends who might not be in recent conversations
    friends.value.forEach(friend => {
        if (!contacts.has(friend.id)) {
            contacts.set(friend.id, {
                id: friend.id,
                username: friend.username,
                unread_count: 0,
            });
        }
    });

    return Array.from(contacts.values());
});

</script>

<template>
    <footer class="bg-gray-100 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 shadow-lg z-20">
        <div class="max-w-full mx-auto px-4">
            <div class="flex items-center space-x-4 h-16">
                <div class="font-semibold text-sm text-gray-700 dark:text-gray-300">
                    Messenger
                </div>
                
                <!-- Horizontally Scrollable Contact List -->
                <div class="flex-1 min-w-0 overflow-x-auto">
                    <div class="flex items-center space-x-4">
                        <div v-if="isLoading" class="flex space-x-4">
                            <!-- Skeleton Loaders -->
                            <div v-for="i in 5" :key="i" class="h-10 w-10 bg-gray-300 dark:bg-gray-700 rounded-full animate-pulse"></div>
                        </div>

                        <button
                            v-for="contact in contactList"
                            :key="contact.id"
                            @click="openDm(contact)"
                            class="relative flex-shrink-0"
                            :title="contact.username"
                        >
                            <UserAvatar :username="contact.username" :icon="contact.icon" size-class="h-10 w-10" />
                            <!-- Unread count badge -->
                            <span v-if="contact.unread_count > 0" class="absolute -top-1 -right-1 flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-red-600 rounded-full border-2 border-gray-100 dark:border-gray-800">
                                {{ contact.unread_count }}
                            </span>
                        </button>

                        <div v-if="!isLoading && contactList.length === 0" class="text-sm text-gray-500">
                            No contacts available for messaging.
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </footer>
</template>