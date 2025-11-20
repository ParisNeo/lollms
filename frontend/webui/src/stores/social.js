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
    const activeConversationUserId = ref(null);
    const isLoadingConversations = ref(false);
    const isLoadingMessages = ref(false);

    // --- GETTERS ---
    const getPostsByUsername = computed(() => (username) => userPosts.value[username] || []);
    const getActiveConversation = computed(() => (userId) => activeConversations.value[userId]);
    const getCommentsForPost = computed(() => (postId) => {
        if (comments.value[postId]) return comments.value[postId];
        const postInFeed = feedPosts.value.find(p => p.id === postId);
        if (postInFeed && postInFeed.comments) return postInFeed.comments;
        for (const username in userPosts.value) {
             const postInProfile = userPosts.value[username].find(p => p.id === postId);
             if (postInProfile && postInProfile.comments) return postInProfile.comments;
        }
        return null;
    });
    const friendRequestCount = computed(() => pendingFriendRequests.value.length);
    const totalUnreadDms = computed(() => {
        return conversations.value.reduce((total, convo) => total + (convo.unread_count || 0), 0);
    });

    // --- ACTIONS ---
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
            friends.value = response.data || [];
        } catch (error) {
            console.error("Failed to fetch friends:", error);
            friends.value = [];
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

    function handleNewComment(data) {
        const { post_id, comment } = data;
        const uiStore = useUiStore();
        const authStore = useAuthStore();

        if (comments.value[post_id]) {
            const existing = comments.value[post_id].find(c => c.id === comment.id);
            if (!existing) {
                comments.value[post_id].push(comment);
            }
        }
        const postInFeed = feedPosts.value.find(p => p.id === post_id);
        if (postInFeed) {
            if (!postInFeed.comments) postInFeed.comments = [];
            const existingComment = postInFeed.comments.find(c => c.id === comment.id);
            if(!existingComment) {
                postInFeed.comments.push(comment);
            }
        }
        for (const username in userPosts.value) {
            const postInProfile = userPosts.value[username].find(p => p.id === post_id);
             if (postInProfile) {
                if (!postInProfile.comments) postInProfile.comments = [];
                const existingComment = postInProfile.comments.find(c => c.id === comment.id);
                if(!existingComment) {
                    postInProfile.comments.push(comment);
                }
            }
        }
        if(comment.author.id !== authStore.user?.id) {
            uiStore.addNotification(`New comment from ${comment.author.username}`, 'info');
        }
    }

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
        const otherIcon = message.sender_id === currentUser.id ? null : message.sender_icon;

        if (activeConversations.value[otherUserId]) {
            const exists = activeConversations.value[otherUserId].messages.some(m => m.id === message.id);
            if (!exists) {
                if (message.sender_id === currentUser.id) {
                    const tempIndex = activeConversations.value[otherUserId].messages.findIndex(m => m.isTemporary && m.content === message.content);
                    if (tempIndex !== -1) {
                         activeConversations.value[otherUserId].messages.splice(tempIndex, 1);
                    }
                }
                activeConversations.value[otherUserId].messages.push(message);
            }
        }

        const convoIndex = conversations.value.findIndex(c => c.partner_user_id === otherUserId);
        if (convoIndex > -1) {
            const convo = conversations.value[convoIndex];
            convo.last_message = message.content;
            convo.last_message_at = message.sent_at;
            if (message.sender_id !== currentUser.id) {
                convo.unread_count = (convo.unread_count || 0) + 1;
            }
            conversations.value.splice(convoIndex, 1);
            conversations.value.unshift(convo);
        } else {
            conversations.value.unshift({
                partner_user_id: otherUserId,
                partner_username: otherUsername,
                partner_icon: otherIcon,
                last_message: message.content,
                last_message_at: message.sent_at,
                unread_count: message.sender_id !== currentUser.id ? 1 : 0
            });
        }
        
        if (message.sender_id !== currentUser.id) {
             if (!activeConversations.value[otherUserId]) {
                 uiStore.addNotification(`New message from ${message.sender_username}`, 'info');
             }
        }
    }

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
            handleNewComment({ post_id: postId, comment: response.data });
        } catch (error) {
            throw error;
        }
    }
    async function deleteComment({ commentId, postId }) {
        try {
            await apiClient.delete(`/api/social/comments/${commentId}`);
            if (comments.value[postId]) {
                const index = comments.value[postId].findIndex(c => c.id === commentId);
                if (index > -1) comments.value[postId].splice(index, 1);
            }
             const postInFeed = feedPosts.value.find(p => p.id === postId);
             if(postInFeed && postInFeed.comments) {
                 postInFeed.comments = postInFeed.comments.filter(c => c.id !== commentId);
             }
            useUiStore().addNotification('Comment deleted.', 'success');
        } catch (error) {
            throw error;
        }
    }
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
    async function toggleLike(postId) {
        const post = feedPosts.value.find(p => p.id === postId) || Object.values(userPosts.value).flat().find(p => p.id === postId);
        if (!post) return;
        const originalHasLiked = post.has_liked;
        post.has_liked = !originalHasLiked;
        post.like_count += originalHasLiked ? -1 : 1;
        try {
            if (originalHasLiked) await apiClient.delete(`/api/social/posts/${postId}/like`);
            else await apiClient.post(`/api/social/posts/${postId}/like`);
        } catch (error) {
            post.has_liked = originalHasLiked;
            post.like_count += originalHasLiked ? 1 : -1;
            console.error("Failed to toggle like:", error);
            useUiStore().addNotification("Couldn't update like status.", "error");
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
        
    function openConversation(partner) {
        if (!activeConversations.value[partner.id]) {
            activeConversations.value[partner.id] = {
                partner: { id: partner.id, username: partner.username, icon: partner.icon },
                messages: [],
                isLoading: false,
                fullyLoaded: false,
                error: null,
                page: 1
            };
            fetchMoreMessages(partner.id);
        }
        
        // Also ensure the Chat Sidebar opens
        const uiStore = useUiStore();
        uiStore.isChatSidebarOpen = true;
        
        activeConversationUserId.value = partner.id;
    }

    async function fetchMoreMessages(otherUserId) {
        const convo = activeConversations.value[otherUserId];
        if (!convo || convo.isLoading || convo.fullyLoaded) return;
        
        convo.isLoading = true;
        convo.error = null;
        isLoadingMessages.value = true;
        try {
            const response = await apiClient.get(`/api/dm/conversation/${otherUserId}`, { params: { skip: (convo.page - 1) * 50, limit: 50 } });
            const newMessages = response.data;
            const uniqueNewMessages = newMessages.filter(nm => !convo.messages.some(existing => existing.id === nm.id));
            if (uniqueNewMessages.length > 0) {
                convo.messages.unshift(...uniqueNewMessages);
                convo.page += 1;
            }
            if (newMessages.length < 50) {
                convo.fullyLoaded = true;
            }
        } catch (error) {
            console.error(`Failed to fetch messages for user ${otherUserId}:`, error);
            convo.error = 'Failed to load messages.';
        } finally {
            convo.isLoading = false;
            isLoadingMessages.value = false;
        }
    }

    function closeConversation(otherUserId) { 
        if (activeConversationUserId.value === otherUserId) {
            activeConversationUserId.value = null;
        }
        delete activeConversations.value[otherUserId]; 
    }

    // [UPDATED] use FormData for file uploads
    async function sendDirectMessage({ receiverUserId, content, files }) {
        if (!content.trim() && (!files || files.length === 0)) return;
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
            const formData = new FormData();
            formData.append('receiverUserId', receiverUserId);
            formData.append('content', content);
            if (files && files.length > 0) {
                files.forEach(file => formData.append('files', file));
            }

            const response = await apiClient.post('/api/dm/send', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
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
        if (convo) convo.unread_count = 0;
        try {
            await apiClient.post(`/api/dm/conversation/${userId}/read`);
        } catch (error) {
            console.error("Failed to mark conversation as read:", error);
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
        activeConversationUserId.value = null;
        isLoadingConversations.value = false;
        isLoadingMessages.value = false;
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
        activeConversationUserId,
        isLoadingConversations,
        isLoadingMessages,
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
        handleIncomingFriendRequest,
        markConversationAsRead,
        $reset
    };
});
