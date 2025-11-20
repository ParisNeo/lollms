<script setup>
import { onMounted, computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useSocialStore } from '../../stores/social';
import { useAuthStore } from '../../stores/auth';
import UserAvatar from '../ui/Cards/UserAvatar.vue';

const socialStore = useSocialStore();
const authStore = useAuthStore();
const router = useRouter();

const user = computed(() => authStore.user);

const friends = ref([]); // Placeholder
const conversations = computed(() => socialStore.conversations);
const isLoading = computed(() => socialStore.isLoadingConversations);

async function fetchFriends() {
    // try {
    //     friends.value = await authStore.fetchFriends();
    // } catch(e) { console.error("Could not fetch friends for DM footer", e); }
}


onMounted(() => {
  if (user.value?.chat_active) {
    socialStore.fetchConversations();
    fetchFriends();
  }
});

function openDm(user) {
    const partner = {
        id: user.partner_user_id || user.id,
        username: user.partner_username || user.username,
        icon: user.icon || null
    };
    socialStore.openConversation(partner);
    router.push('/messages');
}

const contactList = computed(() => {
    if (!user.value?.chat_active) return [];
    
    const contacts = new Map();

    conversations.value.forEach(convo => {
        contacts.set(convo.partner_user_id, {
            id: convo.partner_user_id,
            username: convo.partner_username,
            unread_count: convo.unread_count,
        });
    });

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
    <footer v-if="user?.chat_active" class="bg-gray-100 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 shadow-lg z-20">
        <div class="max-w-full mx-auto px-4">
            <div class="flex items-center space-x-4 h-16">
                <div class="font-semibold text-sm text-gray-700 dark:text-gray-300">
                    Messenger
                </div>
                
                <div class="flex-1 min-w-0 overflow-x-auto">
                    <div class="flex items-center space-x-4">
                        <div v-if="isLoading" class="flex space-x-4">
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
