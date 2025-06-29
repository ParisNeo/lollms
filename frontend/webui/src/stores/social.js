import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useAuthStore } from './auth';

export const useSocialStore = defineStore('social', () => {
    // --- STATE ---
    
    // Posts & Feed
    const feedPosts = ref([]);
    const profiles = ref({});
    const userPosts = ref({});
    const isLoadingFeed = ref(false);
    const isLoadingProfile = ref(false);

    // Direct Messages (DMs)
    const conversations = ref([]);
    const activeConversations = ref({}); // Keyed by other_user_id
    const isLoadingConversations = ref(false);
    const isLoadingMessages = ref(false);


    // --- GETTERS ---
    const getProfileByUsername = computed(() => (username) => profiles.value[username]);
    const getPostsByUsername = computed(() => (username) => userPosts.value[username] || []);
    const getActiveConversation = computed(() => (userId) => activeConversations.value[userId]);

    // --- ACTIONS ---

    // --- Post Actions ---
    async function fetchFeed() {
        isLoadingFeed.value = true;
        try {
            const response = await apiClient.get('/api/social/feed');
            // --- DEFENSIVE CHECK ---
            if (Array.isArray(response.data)) {
                feedPosts.value = response.data;
            } else {
                console.error("API did not return an array for feed posts. Got:", response.data);
                feedPosts.value = []; // Reset to empty array to prevent crashes
                useUiStore().addNotification('Received invalid data for the feed.', 'error');
            }
        } catch (error) {
            console.error("Failed to fetch main feed:", error);
            feedPosts.value = []; // Also reset on error
            // The global interceptor already shows a notification for network/500 errors.
        } finally {
            isLoadingFeed.value = false;
        }
    }

    async function fetchUserPosts(username) {
        isLoadingProfile.value = true;
        try {
            const response = await apiClient.get(`/api/social/users/${username}/posts`);
            userPosts.value[username] = response.data;
        } catch (error) {
            console.error(`Failed to fetch posts for ${username}:`, error);
        } finally {
            isLoadingProfile.value = false;
        }
    }

    async function createPost(postData) {
        const uiStore = useUiStore();
        try {
            const response = await apiClient.post('/api/social/posts', postData);
            feedPosts.value.unshift(response.data);
            uiStore.addNotification('Post created successfully!', 'success');
        } catch (error) {
            console.error("Failed to create post:", error);
            throw error; // Let the component handle loading state
        }
    }
    
    async function deletePost(postId) {
        const uiStore = useUiStore();
        try {
            await apiClient.delete(`/api/social/posts/${postId}`);
            feedPosts.value = feedPosts.value.filter(p => p.id !== postId);
            for (const username in userPosts.value) {
                userPosts.value[username] = userPosts.value[username].filter(p => p.id !== postId);
            }
            uiStore.addNotification('Post deleted.', 'success');
        } catch (error) {
            console.error("Failed to delete post:", error);
        }
    }

    // --- Follow Actions ---
    async function followUser(targetUserId) {
        try {
            await apiClient.post(`/api/social/users/${targetUserId}/follow`);
            useUiStore().addNotification('You are now following this user.', 'success');
        } catch (error) {
            console.error("Failed to follow user:", error);
        }
    }

    async function unfollowUser(targetUserId) {
        try {
            await apiClient.delete(`/api/social/users/${targetUserId}/follow`);
            useUiStore().addNotification('You have unfollowed this user.', 'info');
        } catch (error) {
            console.error("Failed to unfollow user:", error);
        }
    }

    // --- DM Actions ---
    async function fetchConversations() {
        isLoadingConversations.value = true;
        try {
            const response = await apiClient.get('/api/dm/conversations');
            conversations.value = response.data;
        } catch (error) {
            console.error("Failed to fetch conversations:", error);
        } finally {
            isLoadingConversations.value = false;
        }
    }

    async function openConversation(otherUser) {
        const otherUserId = otherUser.id;
        if (!activeConversations.value[otherUserId]) {
            activeConversations.value[otherUserId] = {
                partner: otherUser,
                messages: [],
                isLoading: false,
                fullyLoaded: false,
            };
        }
        
        const convo = activeConversations.value[otherUserId];
        if (convo.messages.length > 0) return; // Already loaded some messages

        convo.isLoading = true;
        try {
            const response = await apiClient.get(`/api/dm/conversation/${otherUserId}`);
            convo.messages = response.data;
            if (response.data.length < 50) { // Assuming default limit is 50
                convo.fullyLoaded = true;
            }
        } catch(error) {
            console.error(`Failed to fetch messages for user ${otherUserId}:`, error);
        } finally {
            convo.isLoading = false;
        }
    }
    
    function closeConversation(otherUserId) {
        delete activeConversations.value[otherUserId];
    }

    async function sendDirectMessage({ receiverUserId, content }) {
        if (!content.trim()) return;

        const convo = activeConversations.value[receiverUserId];
        if (!convo) return;
        
        const authStore = useAuthStore();
        const tempMessage = {
            id: `temp-${Date.now()}`,
            sender_id: authStore.user.id,
            sender_username: authStore.user.username,
            receiver_id: receiverUserId,
            receiver_username: convo.partner.username,
            content: content,
            sent_at: new Date().toISOString(),
            isTemporary: true,
        };
        convo.messages.push(tempMessage);

        try {
            const response = await apiClient.post('/api/dm/send', {
                receiver_user_id: receiverUserId,
                content: content,
            });
            // Replace temporary message with the real one from the server
            const index = convo.messages.findIndex(m => m.id === tempMessage.id);
            if (index !== -1) {
                convo.messages.splice(index, 1, response.data);
            }
        } catch (error) {
            console.error("Failed to send direct message:", error);
            const index = convo.messages.findIndex(m => m.id === tempMessage.id);
            if (index !== -1) {
                 convo.messages[index].error = true;
            }
            useUiStore().addNotification('Failed to send message.', 'error');
        }
    }


    return {
        // State
        feedPosts,
        profiles,
        userPosts,
        isLoadingFeed,
        isLoadingProfile,
        conversations,
        activeConversations,
        isLoadingConversations,
        isLoadingMessages,
        
        // Getters
        getProfileByUsername,
        getPostsByUsername,
        getActiveConversation,
        
        // Actions
        fetchFeed,
        fetchUserPosts,
        createPost,
        deletePost,
        followUser,
        unfollowUser,
        fetchConversations,
        openConversation,
        closeConversation,
        sendDirectMessage,
    };
});