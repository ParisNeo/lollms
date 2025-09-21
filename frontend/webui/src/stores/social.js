// frontend/webui/src/stores/social.js
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useAuthStore } from './auth';

export const useSocialStore = defineStore('social', () => {
    // --- STATE ---
    const friends = ref([]);
    const pendingFriendRequests = ref([]);
    const blockedUsers = ref([]);
    const isLoadingFriends = ref(false);
    const feedPosts = ref([]);
    const profiles = ref({});
    const userPosts = ref({});
    const isLoadingFeed = ref(false);
    const isLoadingProfile = ref(false);
    const isLoadingRequests = ref(false);
    const isLoadingBlocked = ref(false);
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
    const getCommentsForPost = computed(() => (postId) => {
        if (comments.value[postId]) {
            return comments.value[postId];
        }
        const postInFeed = feedPosts.value.find(p => p.id === postId);
        if (postInFeed && postInFeed.comments) {
            return postInFeed.comments;
        }
        for (const username in userPosts.value) {
             const postInProfile = userPosts.value[username].find(p => p.id === postId);
             if (postInProfile && postInProfile.comments) {
                 return postInProfile.comments;
             }
        }
        return null;
    });
    const friendRequestCount = computed(() => pendingFriendRequests.value.length);
    const totalUnreadDms = computed(() => {
        return conversations.value.reduce((total, convo) => total + (convo.unread_count || 0), 0);
    });

    // --- ACTIONS ---

    // NEW ACTION
    async function searchForMentions(query) {
        if (!query) return [];
        try {
            const response = await apiClient.get('/api/users/mention_search', { params: { q: query } });
            return response.data;
        } catch (error) {
            console.error("Failed to search for mentions:", error);
            return [];
        }
    }


    // -- Friendship, Requests & Blocks --
    async function fetchFriends() {
        isLoadingFriends.value = true;
        try {
            const response = await apiClient.get('/api/friends');
            // Use splice to mutate the array in place, preserving reactivity
            friends.value.splice(0, friends.value.length, ...(response.data || []));
        } catch (error) {
            console.error("Failed to fetch friends:", error);
            friends.value.splice(0, friends.value.length); // Clear on error
        } finally {
            isLoadingFriends.value = false;
        }
    }

    async function fetchPendingRequests() {
        isLoadingRequests.value = true;
        try {
            const response = await apiClient.get('/api/friends/requests/pending');
            pendingFriendRequests.value = response.data;
        } catch (error) {
            console.error("Failed to fetch pending friend requests:", error);
        } finally {
            isLoadingRequests.value = false;
        }
    }
    
    async function fetchBlockedUsers() {
        isLoadingBlocked.value = true;
        try {
            const response = await apiClient.get('/api/friends/blocked');
            blockedUsers.value = response.data;
        } catch (error) {
            console.error("Failed to fetch blocked users:", error);
            blockedUsers.value = [];
        } finally {
            isLoadingBlocked.value = false;
        }
    }
    
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
        try {
            await apiClient.post(`/api/friends/request`, { target_username: targetUsername });
            useUiStore().addNotification('Friend request sent!', 'success');
        } catch (error) {
            throw error;
        }
    }

    async function acceptFriendRequest(friendshipId) {
        try {
            await apiClient.put(`/api/friends/requests/${friendshipId}`, { action: "accept" });
            useUiStore().addNotification(`Friend request accepted!`, 'success');
            await Promise.all([fetchFriends(), fetchPendingRequests()]);
        } catch (error) {
            throw error;
        }
    }
    
    async function rejectFriendRequest(friendshipId) {
        try {
            await apiClient.put(`/api/friends/requests/${friendshipId}`, { action: "reject" });
            useUiStore().addNotification(`Friend request rejected.`, 'info');
            pendingFriendRequests.value = pendingFriendRequests.value.filter(req => req.friendship_id !== friendshipId);
        } catch (error) {
            throw error;
        }
    }
    
    async function removeFriend(friendUserId) {
        try {
            await apiClient.delete(`/api/friends/${friendUserId}`);
            useUiStore().addNotification('Friend removed.', 'info');
            await fetchFriends();
            const profileKey = Object.keys(profiles.value).find(key => profiles.value[key]?.user?.id === friendUserId);
            if(profileKey) {
                await fetchUserProfile(profileKey);
            }
        } catch (error) {
           throw error;
        }
    }

    async function blockUser(userId) {
        try {
            await apiClient.put(`/api/friends/block/${userId}`);
            useUiStore().addNotification('User blocked successfully.', 'success');
            await Promise.all([fetchFriends(), fetchPendingRequests(), fetchBlockedUsers()]);
        } catch (error) {
            throw error;
        }
    }

    async function unblockUser(userId) {
        try {
            await apiClient.put(`/api/friends/unblock/${userId}`);
            useUiStore().addNotification('User unblocked.', 'success');
            await fetchBlockedUsers();
        } catch (error) {
            throw error;
        }
    }

    function handleNewComment({ post_id, comment }) {
        if (comments.value[post_id]) {
            const existing = comments.value[post_id].find(c => c.id === comment.id);
            if (!existing) {
                comments.value[post_id].push(comment);
            }
        }
        
        const postInFeed = feedPosts.value.find(p => p.id === post_id);
        if (postInFeed) {
            if (!postInFeed.comments) {
                postInFeed.comments = [];
            }
            const existingComment = postInFeed.comments.find(c => c.id === comment.id);
            if(!existingComment) {
                postInFeed.comments.push(comment);
            }
        }
        
        for (const username in userPosts.value) {
            const postInProfile = userPosts.value[username].find(p => p.id === post_id);
             if (postInProfile) {
                if (!postInProfile.comments) {
                    postInProfile.comments = [];
                }
                const existingComment = postInProfile.comments.find(c => c.id === comment.id);
                if(!existingComment) {
                    postInProfile.comments.push(comment);
                }
            }
        }

        const uiStore = useUiStore();
        const authStore = useAuthStore();
        if(comment.author.id !== authStore.user?.id) {
            uiStore.addNotification(`New comment from ${comment.author.username}`, 'info');
        }
    }
    
    // -- WebSocket Handling --
    function handleIncomingFriendRequest(requestData) {
        const existing = pendingFriendRequests.value.find(req => req.friendship_id === requestData.friendship_id);
        if (!existing) {
            pendingFriendRequests.value.unshift(requestData);
            useUiStore().addNotification(`New friend request from ${requestData.requesting_username}`, 'info');
        }
    }

    function handleNewDm(message) {
        const authStore = useAuthStore();
        const uiStore = useUiStore();
        const currentUser = authStore.user;
        if (!currentUser) return;

        const otherUserId = message.sender_id === currentUser.id ? message.receiver_id : message.sender_id;
        const otherUsername = message.sender_id === currentUser.id ? message.receiver_username : message.sender_username;

        // If conversation is currently open, just add the message
        if (activeConversations.value[otherUserId]) {
            activeConversations.value[otherUserId].messages.push(message);
        }

        // Update the main conversation list
        const convoIndex = conversations.value.findIndex(c => c.partner_user_id === otherUserId);
        if (convoIndex > -1) {
            const convo = conversations.value[convoIndex];
            convo.last_message = message.content;
            convo.last_message_at = message.sent_at;
            if (message.sender_id !== currentUser.id) {
                convo.unread_count = (convo.unread_count || 0) + 1;
            }
            // Move to top
            conversations.value.splice(convoIndex, 1);
            conversations.value.unshift(convo);
        } else {
            // New conversation
            conversations.value.unshift({
                partner_user_id: otherUserId,
                partner_username: otherUsername,
                partner_icon: message.sender_id === currentUser.id ? null : message.sender_icon, // Assuming icon is sent
                last_message: message.content,
                last_message_at: message.sent_at,
                unread_count: message.sender_id !== currentUser.id ? 1 : 0
            });
        }
        
        // Show notification if it's from someone else and not currently open
        if (message.sender_id !== currentUser.id && !activeConversations.value[otherUserId]) {
            uiStore.addNotification(`New message from ${message.sender_username}`, 'info');
        }
    }
    
    function connectWebSocket() {
        const authStore = useAuthStore();
        const uiStore = useUiStore();
        if (!authStore.token || (socket.value && isSocketConnected.value)) {
            return;
        }
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/dm/${authStore.token}`;
        socket.value = new WebSocket(wsUrl);

        socket.value.onopen = () => { isSocketConnected.value = true; };
        
        socket.value.onmessage = (event) => {
            const message = JSON.parse(event.data);
            
            if (message.type === 'new_friend_request') {
                handleIncomingFriendRequest(message.data);
                return;
            }
            if (message.type === 'new_comment') {
                handleNewComment(message.data);
                return;
            }
            const currentUser = authStore.user;
            if (!currentUser) return;

            if (message.sender_username === 'System Alert') {
                if (currentUser.is_admin) {
                    uiStore.addNotification(message.content, 'warning', 10000);
                }
                return;
            }
            
            const otherUserId = message.sender_id === currentUser.id ? message.receiver_id : message.sender_id;
            if (activeConversations.value[otherUserId]) {
                activeConversations.value[otherUserId].messages.push(message);
            } else {
                 if (message.sender_id !== currentUser.id) {
                    uiStore.addNotification(`New message from ${message.sender_username}`, 'info');
                }
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
            const uiStore = useUiStore();
            uiStore.addNotification(error.response?.data?.detail || 'Could not load the feed. Please try again later.', 'error');
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
        try {
            const response = await apiClient.post('/api/social/posts', postData);
            feedPosts.value.unshift(response.data);
            useUiStore().addNotification('Post created successfully!', 'success');
        } catch (error) {
            throw error;
        }
    }
    
    async function deletePost(postId) {
        try {
            await apiClient.delete(`/api/social/posts/${postId}`);
            feedPosts.value = feedPosts.value.filter(p => p.id !== postId);
            for (const username in userPosts.value) {
                userPosts.value[username] = userPosts.value[username].filter(p => p.id !== postId);
            }
            useUiStore().addNotification('Post deleted.', 'success');
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
            throw error;
        }
    }
    
    async function deleteComment({ commentId, postId }) {
        try {
            await apiClient.delete(`/api/social/comments/${commentId}`);
            if (comments.value[postId]) {
                const index = comments.value[postId].findIndex(c => c.id === commentId);
                if (index > -1) {
                    comments.value[postId].splice(index, 1);
                }
            }
            useUiStore().addNotification('Comment deleted.', 'success');
        } catch (error) {
            throw error;
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
            activeConversations.value[otherUserId] = { 
                partner: otherUser, 
                messages: [], 
                isLoading: false, 
                fullyLoaded: false, 
                page: 0,
                error: null
            };
        }
        const convo = activeConversations.value[otherUserId];
        if (convo.messages.length > 0) return;
        await fetchMoreMessages(otherUserId);
    }
    
    async function fetchMoreMessages(otherUserId) {
        const convo = activeConversations.value[otherUserId];
        if (!convo || convo.isLoading || convo.fullyLoaded) return;
        
        convo.isLoading = true;
        convo.error = null;
        isLoadingMessages.value = true;
        try {
            const response = await apiClient.get(`/api/dm/conversation/${otherUserId}`, { params: { skip: convo.page * 50, limit: 50 } });
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
            convo.error = 'Failed to load older messages.';
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
                receiverUserId: receiverUserId,
                content: content,
            });
            const index = convo.messages.findIndex(m => m.id === tempMessage.id);
            if (index !== -1) {
                convo.messages.splice(index, 1, response.data);
            }
        } catch (error) {
            const index = convo.messages.findIndex(m => m.id === tempMessage.id);
            if (index !== -1) {
                 convo.messages[index].error = true;
            }
            useUiStore().addNotification('Failed to send message.', 'error');
        }
    }
    
    async function markConversationAsRead(userId) {
        const convo = conversations.value.find(c => c.partner_user_id === userId);
        if (!convo || convo.unread_count === 0) return;
        
        const originalCount = convo.unread_count;
        convo.unread_count = 0; // Optimistic update
        try {
            await apiClient.post(`/api/dm/conversation/${userId}/read`);
        } catch (error) {
            convo.unread_count = originalCount; // Revert on failure
            console.error("Failed to mark conversation as read:", error);
        }
    }

    async function toggleLike(postId) {
        const post = feedPosts.value.find(p => p.id === postId) || Object.values(userPosts.value).flat().find(p => p.id === postId);
        if (!post) return;

        const originalHasLiked = post.has_liked;
        const originalLikeCount = post.like_count;

        post.has_liked = !originalHasLiked;
        post.like_count += originalHasLiked ? -1 : 1;

        try {
            if (originalHasLiked) {
                await apiClient.delete(`/api/social/posts/${postId}/like`);
            } else {
                await apiClient.post(`/api/social/posts/${postId}/like`);
            }
        } catch (error) {
            console.error("Failed to toggle like:", error);
            post.has_liked = originalHasLiked;
            post.like_count = originalLikeCount;
            useUiStore().addNotification("Couldn't update like status.", "error");
        }
    }

    function $reset() {
        friends.value = [];
        pendingFriendRequests.value = [];
        blockedUsers.value = [];
        isLoadingFriends.value = false;
        feedPosts.value = [];
        profiles.value = {};
        userPosts.value = {};
        isLoadingFeed.value = false;
        isLoadingProfile.value = false;
        isLoadingRequests.value = false;
        isLoadingBlocked.value = false;
        comments.value = {};
        isLoadingComments.value = {};
        conversations.value = [];
        activeConversations.value = {};
        isLoadingConversations.value = false;
        isLoadingMessages.value = false;
        socket.value = null;
        isSocketConnected.value = false;
    }

    return {
        feedPosts,
        profiles,
        userPosts,
        friends,
        pendingFriendRequests,
        blockedUsers,
        isLoadingFeed,
        isLoadingProfile,
        isLoadingFriends,
        isLoadingRequests,
        isLoadingBlocked,
        comments,
        isLoadingComments,
        conversations,
        activeConversations,
        isLoadingConversations,
        isLoadingMessages,
        socket,
        isSocketConnected,
        totalUnreadDms,
        getPostsByUsername,
        getActiveConversation,
        getCommentsForPost,
        friendRequestCount,
        searchForMentions,
        fetchFriends,
        fetchPendingRequests,
        fetchBlockedUsers,
        fetchUserProfile,
        sendFriendRequest,
        acceptFriendRequest,
        rejectFriendRequest,
        removeFriend,
        blockUser,
        unblockUser,
        connectWebSocket,
        disconnectWebSocket,
        fetchFeed,
        createPost,
        deletePost,
        fetchUserPosts,
        followUser,
        unfollowUser,
        fetchComments,
        createComment,
        deleteComment,
        toggleLike,
        fetchConversations,
        openConversation,
        closeConversation,
        sendDirectMessage,
        fetchMoreMessages,
        handleNewComment,
        handleNewDm,
        markConversationAsRead,
        $reset
    };
});