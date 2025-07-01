import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useAuthStore } from './auth';

export const useSocialStore = defineStore('social', () => {
    // --- STATE ---
    const feedPosts = ref([]);
    const profiles = ref({}); // { username: { user: {...}, relationship: {...} } }
    const userPosts = ref({});
    const pendingFriendRequests = ref([]);
    const isLoadingFeed = ref(false);
    const isLoadingProfile = ref(false);
    const comments = ref({});
    const isLoadingComments = ref({});
    const conversations = ref([]);
    const activeConversations = ref({});
    const isLoadingConversations = ref(false);
    const isLoadingMessages = ref(false);
    const socket = ref(null);
    const isSocketConnected = ref(false);

    // --- GETTERS ---
    const getPostsByUsername = computed(() => (username) => userPosts.value[username] || []);
    const getActiveConversation = computed(() => (userId) => activeConversations.value[userId]);
    const getCommentsForPost = computed(() => (postId) => comments.value[postId] || null);

    // --- ACTIONS ---

    // -- User Profile & Friendship Actions --
    async function fetchUserProfile(username) {
        isLoadingProfile.value = true;
        try {
            const response = await apiClient.get(`/api/users/${username}`);
            profiles.value[username] = response.data;
        } catch (error) {
            console.error(`Failed to fetch profile for ${username}:`, error);
            profiles.value[username] = null;
        } finally {
            isLoadingProfile.value = false;
        }
    }

    async function sendFriendRequest(targetUsername) {
        const uiStore = useUiStore();
        try {
            await apiClient.post(`/api/friends/request`, { target_username: targetUsername });
            if (profiles.value[targetUsername]) {
                profiles.value[targetUsername].relationship.friendship_status = 'PENDING';
            }
            uiStore.addNotification('Friend request sent!', 'success');
        } catch (error) {
            uiStore.addNotification(error.response?.data?.detail || 'Could not send request.', 'error');
        }
    }

    async function acceptFriendRequest(friendshipId) {
        const uiStore = useUiStore();
        try {
            const response = await apiClient.put(`/api/friends/requests/${friendshipId}`, { action: "accept" });
            const acceptedFriend = response.data;
            pendingFriendRequests.value = pendingFriendRequests.value.filter(req => req.friendship_id !== friendshipId);
            if (profiles.value[acceptedFriend.username]) {
                profiles.value[acceptedFriend.username].relationship.friendship_status = 'ACCEPTED';
            }
            uiStore.addNotification(`You are now friends with ${acceptedFriend.username}!`, 'success');
        } catch (error) {
            uiStore.addNotification(error.response?.data?.detail || 'Could not accept request.', 'error');
        }
    }

    async function removeFriend(otherUserId) {
        const uiStore = useUiStore();
        if (!confirm("Are you sure you want to remove this friend or cancel/decline the request?")) return;
        try {
            await apiClient.delete(`/api/friends/${otherUserId}`);
            for (const key in profiles.value) {
                if (profiles.value[key]?.user?.id === otherUserId) {
                    profiles.value[key].relationship.friendship_status = null;
                }
            }
            uiStore.addNotification('Friendship status updated.', 'info');
        } catch (error) {
            uiStore.addNotification(error.response?.data?.detail || 'Could not perform action.', 'error');
        }
    }

    async function fetchPendingRequests() {
        try {
            const response = await apiClient.get('/api/friends/requests/pending');
            pendingFriendRequests.value = response.data;
        } catch (error) {
            console.error("Failed to fetch pending friend requests:", error);
        }
    }

    // -- WebSocket Actions --
    function connectWebSocket() {
        const authStore = useAuthStore();
        const uiStore = useUiStore();
        if (!authStore.token || (socket.value && isSocketConnected.value)) return;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/dm/${authStore.token}`;
        socket.value = new WebSocket(wsUrl);
        socket.value.onopen = () => { isSocketConnected.value = true; };
        socket.value.onmessage = (event) => {
            const message = JSON.parse(event.data);
            const currentUser = authStore.user;
            if (!currentUser) return;
            const otherUserId = message.sender_id === currentUser.id ? message.receiver_id : message.sender_id;
            if (activeConversations.value[otherUserId]) {
                activeConversations.value[otherUserId].messages.push(message);
            } else {
                uiStore.addNotification(`New message from ${message.sender_username}`, 'info');
            }
        };
        socket.value.onclose = () => { isSocketConnected.value = false; socket.value = null; };
        socket.value.onerror = () => { uiStore.addNotification('Real-time connection error.', 'error'); isSocketConnected.value = false; };
    }
    function disconnectWebSocket() { if (socket.value) socket.value.close(); }

    // -- Post & Comment Actions --
    async function fetchFeed() {
        isLoadingFeed.value = true;
        try {
            const response = await apiClient.get('/api/social/feed');
            feedPosts.value = Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            console.error("Failed to fetch main feed:", error);
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
            throw error;
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
    async function fetchComments(postId) {
        if (isLoadingComments.value[postId]) return;
        isLoadingComments.value[postId] = true;
        try {
            const response = await apiClient.get(`/api/social/posts/${postId}/comments`);
            comments.value[postId] = response.data;
        } catch (error) {
            if (!comments.value[postId]) comments.value[postId] = [];
        } finally {
            isLoadingComments.value[postId] = false;
        }
    }
    async function createComment({ postId, content }) {
        try {
            const response = await apiClient.post(`/api/social/posts/${postId}/comments`, { content });
            if (!comments.value[postId]) comments.value[postId] = [];
            comments.value[postId].push(response.data);
        } catch (error) {
            useUiStore().addNotification(error.response?.data?.detail || 'Failed to post comment.', 'error');
            throw error;
        }
    }
    async function deleteComment(commentId) {
        const uiStore = useUiStore();
        try {
            await apiClient.delete(`/api/social/comments/${commentId}`);
            for (const postId in comments.value) {
                const index = comments.value[postId].findIndex(c => c.id === commentId);
                if (index > -1) {
                    comments.value[postId].splice(index, 1);
                    break;
                }
            }
            uiStore.addNotification('Comment deleted.', 'success');
        } catch (error) {
            uiStore.addNotification(error.response?.data?.detail || 'Failed to delete comment.', 'error');
        }
    }

    // -- Follow Actions --
    async function followUser(targetUserId) {
        try {
            await apiClient.post(`/api/social/users/${targetUserId}/follow`);
            for (const key in profiles.value) {
                if (profiles.value[key]?.user?.id === targetUserId) {
                    profiles.value[key].relationship.is_following = true;
                }
            }
            useUiStore().addNotification('You are now following this user.', 'success');
        } catch (error) {
            console.error("Failed to follow user:", error);
        }
    }
    async function unfollowUser(targetUserId) {
        try {
            await apiClient.delete(`/api/social/users/${targetUserId}/follow`);
            for (const key in profiles.value) {
                if (profiles.value[key]?.user?.id === targetUserId) {
                    profiles.value[key].relationship.is_following = false;
                }
            }
            useUiStore().addNotification('You have unfollowed this user.', 'info');
        } catch (error) {
            console.error("Failed to unfollow user:", error);
        }
    }

    // -- DM Actions --
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
            activeConversations.value[otherUserId] = { partner: otherUser, messages: [], isLoading: false, fullyLoaded: false, page: 0 };
        }
        const convo = activeConversations.value[otherUserId];
        if (convo.messages.length > 0) return;
        await fetchMoreMessages(otherUserId);
    }
    async function fetchMoreMessages(otherUserId) {
        const convo = activeConversations.value[otherUserId];
        if (!convo || convo.isLoading || convo.fullyLoaded) return;
        convo.isLoading = true;
        isLoadingMessages.value = true;
        try {
            const response = await apiClient.get(`/api/dm/conversation/${otherUserId}`, { params: { skip: convo.page * 50, limit: 50, } });
            const newMessages = response.data;
            if (newMessages.length > 0) {
                convo.messages.unshift(...newMessages);
                convo.page += 1;
            }
            if (newMessages.length < 50) {
                convo.fullyLoaded = true;
            }
        } catch (error) {
            console.error(`Failed to fetch more messages for user ${otherUserId}:`, error);
        } finally {
            convo.isLoading = false;
            isLoadingMessages.value = false;
        }
    }
    function closeConversation(otherUserId) { delete activeConversations.value[otherUserId]; }
    async function sendDirectMessage({ receiverUserId, content }) {
        if (!content.trim()) return;
        const convo = activeConversations.value[receiverUserId];
        if (!convo) return;
        const authStore = useAuthStore();
        const tempMessage = { id: `temp-${Date.now()}`, sender_id: authStore.user.id, sender_username: authStore.user.username, receiver_id: receiverUserId, receiver_username: convo.partner.username, content: content, sent_at: new Date().toISOString(), isTemporary: true, };
        convo.messages.push(tempMessage);
        try {
            const response = await apiClient.post('/api/dm/send', { receiver_user_id: receiverUserId, content: content });
            const index = convo.messages.findIndex(m => m.id === tempMessage.id);
            if (index !== -1) convo.messages.splice(index, 1, response.data);
        } catch (error) {
            const index = convo.messages.findIndex(m => m.id === tempMessage.id);
            if (index !== -1) convo.messages[index].error = true;
            useUiStore().addNotification('Failed to send message.', 'error');
        }
    }
    async function toggleLike(postId) {
        // Find the post in the local state
        const post = this.feedPosts.find(p => p.id === postId) || (this.userPosts[this.profiles[authStore.user.username]?.user?.username] || []).find(p => p.id === postId);
        if (!post) return;

        // Optimistic update
        const originalHasLiked = post.has_liked;
        const originalLikeCount = post.like_count;

        if (post.has_liked) {
            post.has_liked = false;
            post.like_count--;
        } else {
            post.has_liked = true;
            post.like_count++;
        }

        try {
            if (originalHasLiked) {
                await apiClient.delete(`/api/social/posts/${postId}/like`);
            } else {
                await apiClient.post(`/api/social/posts/${postId}/like`);
            }
        } catch (error) {
            console.error("Failed to toggle like:", error);
            // Revert on failure
            post.has_liked = originalHasLiked;
            post.like_count = originalLikeCount;
            useUiStore().addNotification("Couldn't update like status.", "error");
        }
    }
    return {
        // State
        feedPosts, profiles, userPosts, pendingFriendRequests, isLoadingFeed, isLoadingProfile,
        conversations, activeConversations, isLoadingConversations, isLoadingMessages,
        comments, isLoadingComments, isSocketConnected,
        
        // Getters
        getPostsByUsername, getActiveConversation, getCommentsForPost,
        
        // Actions
        fetchUserProfile, sendFriendRequest, removeFriend, fetchPendingRequests, acceptFriendRequest,
        fetchFeed, fetchUserPosts, createPost, deletePost,
        followUser, unfollowUser,
        fetchComments, createComment, deleteComment,
        fetchConversations, openConversation, closeConversation, sendDirectMessage, fetchMoreMessages,
        connectWebSocket, disconnectWebSocket, toggleLike,
    };
});