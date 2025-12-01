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
    
    // Chat State
    const conversations = ref([]); // List of summary objects (groups + DMs)
    const activeConversations = ref({}); // Cache of detailed conversation objects { [id]: { ...details, messages: [] } }
    const activeConversationId = ref(null); // ID of the conversation (group ID or partner ID for legacy)
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
        return conversations.value.reduce((total, c) => total + (c.unread_count || 0), 0);
    });

    // --- ACTIONS ---
    async function searchForMentions(query) {
        if (!query) return [];
        try {
            // Using the specialized social mentions endpoint for better context (friends, bot, etc.)
            const response = await apiClient.get('/api/social/mentions/search', { params: { q: query } });
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
                if (index > -1) {
                    comments.value[postId].splice(index, 1);
                }
            }
            // Also update feed posts if present
             const postInFeed = feedPosts.value.find(p => p.id === postId);
             if(postInFeed && postInFeed.comments) {
                 postInFeed.comments = postInFeed.comments.filter(c => c.id !== commentId);
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

    async function toggleLike(postId) {
        const post = feedPosts.value.find(p => p.id === postId) || Object.values(userPosts.value).flat().find(p => p.id === postId);
        if (!post) return;

        const originalHasLiked = post.has_liked;
        // Optimistic update
        post.has_liked = !originalHasLiked;
        post.like_count += originalHasLiked ? -1 : 1;

        try {
            if (originalHasLiked) {
                await apiClient.delete(`/api/social/posts/${postId}/like`);
            } else {
                await apiClient.post(`/api/social/posts/${postId}/like`);
            }
        } catch (error) {
            // Revert
            post.has_liked = originalHasLiked;
            post.like_count += originalHasLiked ? 1 : -1;
            console.error("Failed to toggle like:", error);
            useUiStore().addNotification("Couldn't update like status.", "error");
        }
    }

    // --- CHAT / DM ACTIONS ---

    async function fetchConversations() {
        isLoadingConversations.value = true;
        try {
            const res = await apiClient.get('/api/dm/conversations');
            conversations.value = res.data;
        } catch (e) { 
            console.error(e); 
        } finally {
            isLoadingConversations.value = false;
        }
    }

    async function createGroupConversation(name, participantIds) {
        try {
            const res = await apiClient.post('/api/dm/conversations/group', { name, participant_ids: participantIds });
            const newConvo = res.data;
            conversations.value.unshift(newConvo);
            openConversation(newConvo); 
            return newConvo;
        } catch(e) {
            console.error(e);
        }
    }

    async function addMemberToGroup(conversationId, userId) {
         try {
            await apiClient.post(`/api/dm/conversations/${conversationId}/members`, { user_id: userId });
         } catch(e) { console.error(e); }
    }

    // Logic to open a conversation from list or friend
    function openConversation(item) {
        let convoId = null;
        let isGroup = false;
        let partner = null;
        let name = null;

        if (item.is_group) {
            convoId = item.id;
            isGroup = true;
            name = item.name;
        } else if (item.partner_user_id) {
            convoId = item.partner_user_id; 
            isGroup = false;
            partner = {
                id: item.partner_user_id,
                username: item.partner_username,
                icon: item.partner_icon
            };
        } else {
            convoId = item.id;
            isGroup = false;
            partner = {
                id: item.id,
                username: item.username,
                icon: item.icon
            };
        }
        
        if (!activeConversations.value[convoId]) {
            activeConversations.value[convoId] = {
                id: convoId,
                isGroup: isGroup,
                partner: partner, 
                name: name || partner?.username,
                messages: [],
                isLoading: false,
                page: 1,
                fullyLoaded: false,
                members: item.members || []
            };
            fetchMessages(convoId, isGroup);
        }
        
        activeConversationId.value = convoId;
        useUiStore().isChatSidebarOpen = true;
    }

    async function fetchMessages(targetId, isGroup) {
        const convo = activeConversations.value[targetId];
        if (!convo) return;
        
        convo.isLoading = true;
        try {
            const res = await apiClient.get(`/api/dm/conversation/${targetId}`, { 
                params: { is_group: isGroup, skip: (convo.page - 1) * 50 } 
            });
            const newMsgs = res.data;
            
            // Deduplicate based on ID
            const ids = new Set(convo.messages.map(m => m.id));
            const unique = newMsgs.filter(m => !ids.has(m.id));
            
            // Prepend old messages
            convo.messages.unshift(...unique);
            
            if (unique.length > 0) convo.page++;
            if (newMsgs.length < 50) convo.fullyLoaded = true;

        } finally {
            convo.isLoading = false;
        }
    }

    async function sendDirectMessage({ targetId, isGroup, content, files }) {
        const formData = new FormData();
        formData.append('content', content);
        
        if (isGroup) {
            formData.append('conversationId', targetId);
        } else {
            formData.append('receiverUserId', targetId);
        }
        
        if (files && files.length > 0) {
            files.forEach(f => formData.append('files', f));
        }
        
        try {
            const res = await apiClient.post('/api/dm/send', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            const msg = res.data;
            
            // We manually push here for immediate UI update, but the WebSocket might also arrive.
            // Duplicate ID check is handled in handleNewDm, but we should do it here too just in case.
            if (activeConversations.value[targetId]) {
                const exists = activeConversations.value[targetId].messages.some(m => m.id === msg.id);
                if (!exists) activeConversations.value[targetId].messages.push(msg);
            }
            
            const listIndex = conversations.value.findIndex(c => isGroup ? c.id === targetId : c.partner_user_id === targetId);
            if (listIndex !== -1) {
                const item = conversations.value.splice(listIndex, 1)[0];
                item.last_message = content;
                item.last_message_at = new Date().toISOString();
                conversations.value.unshift(item);
            }

        } catch(e) { console.error(e); }
    }

    async function deleteMessage(messageId) {
        try {
            await apiClient.delete(`/api/dm/messages/${messageId}`);
            for (const cid in activeConversations.value) {
                const c = activeConversations.value[cid];
                c.messages = c.messages.filter(m => m.id !== messageId);
            }
            useUiStore().addNotification('Message deleted.', 'success');
        } catch(e) { useUiStore().addNotification('Failed to delete message.', 'error'); }
    }

    async function deleteConversation(id, isGroup) {
        try {
            await apiClient.delete(`/api/dm/conversations/${id}`, { params: { is_group: isGroup } });
            delete activeConversations.value[id];
            conversations.value = conversations.value.filter(c => isGroup ? c.id !== id : c.partner_user_id !== id);
            useUiStore().addNotification(isGroup ? 'Left group' : 'History cleared', 'success');
        } catch(e) { useUiStore().addNotification('Failed to delete conversation', 'error'); }
    }

    async function exportConversation(id, isGroup, title) {
        try {
            const res = await apiClient.get(`/api/dm/conversations/${id}/export`, { params: { is_group: isGroup }, responseType: 'blob' });
            const url = URL.createObjectURL(new Blob([res.data]));
            const a = document.createElement('a'); a.href = url; a.download = `${title}_export.json`; a.click();
        } catch(e) { useUiStore().addNotification('Export failed', 'error'); }
    }

    async function importConversation(id, isGroup, file) {
        const fd = new FormData(); fd.append('file', file);
        try {
            const res = await apiClient.post(`/api/dm/conversations/${id}/import`, fd, { params: { is_group: isGroup }, headers: {'Content-Type': 'multipart/form-data'} });
            useUiStore().addNotification(res.data.message, 'success');
            if (activeConversations.value[id]) {
                activeConversations.value[id].page = 1;
                activeConversations.value[id].messages = [];
                fetchMessages(id, isGroup);
            }
        } catch(e) { useUiStore().addNotification('Import failed', 'error'); }
    }
    
    async function markConversationAsRead(targetId) {
        const convo = conversations.value.find(c => c.id === targetId || c.partner_user_id === targetId);
        if (convo) convo.unread_count = 0;
        
        if (!convo?.is_group && convo?.partner_user_id) {
             try {
                await apiClient.post(`/api/dm/conversation/${convo.partner_user_id}/read`);
            } catch (e) { console.error(e); }
        }
    }
    
    // -- Event Handlers --

    function handleNewDm(message) {
        const authStore = useAuthStore();
        const uiStore = useUiStore();
        const currentUser = authStore.user;
        if (!currentUser) return;

        let convoKey = message.conversation_id || (message.sender_id === currentUser.id ? message.receiver_id : message.sender_id);
        let isGroup = !!message.conversation_id;

        // Push message to active conversation cache if exists (De-duplication critical here)
        if (activeConversations.value[convoKey]) {
            const exists = activeConversations.value[convoKey].messages.some(m => m.id === message.id);
            if (!exists) activeConversations.value[convoKey].messages.push(message);
        }

        // Update conversation list summary
        let listIndex = isGroup ? conversations.value.findIndex(c => c.id === convoKey && c.is_group) : conversations.value.findIndex(c => !c.is_group && c.partner_user_id === convoKey);
        
        if (listIndex > -1) {
            const convo = conversations.value.splice(listIndex, 1)[0];
            convo.last_message = message.content;
            convo.last_message_at = message.sent_at;
            if (message.sender_id !== currentUser.id) convo.unread_count = (convo.unread_count || 0) + 1;
            conversations.value.unshift(convo);
        } else {
            // New conversation discovered via websocket
            fetchConversations();
        }
        
        // Notification for new message if not in active view
        if (message.sender_id !== currentUser.id && activeConversationId.value !== convoKey) {
             uiStore.addNotification(`New message from ${message.sender_username}`, 'info');
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
        activeConversationId.value = null;
        isLoadingConversations.value = false;
        isLoadingMessages.value = false;
    }

    return {
        // STATE EXPORTS
        friends, 
        pendingFriendRequests, 
        blockedUsers, 
        feedPosts, // EXPORTED
        profiles, // EXPORTED
        userPosts, // EXPORTED
        comments, // EXPORTED
        conversations, 
        activeConversations, 
        activeConversationId,
        
        // LOADING STATES
        isLoadingFriends, 
        isLoadingFeed, // EXPORTED
        isLoadingProfile, // EXPORTED
        isLoadingRequests, // EXPORTED
        isLoadingBlocked, // EXPORTED
        isLoadingComments, // EXPORTED
        isLoadingConversations, 
        isLoadingMessages, // EXPORTED

        // COMPUTED / GETTERS
        totalUnreadDms, 
        friendRequestCount,
        getPostsByUsername, // EXPORTED
        getActiveConversation,
        getCommentsForPost,

        // ACTIONS
        fetchFriends, fetchConversations, openConversation, sendDirectMessage,
        deleteMessage, deleteConversation, exportConversation, importConversation, createGroupConversation, addMemberToGroup,
        fetchPendingRequests, fetchBlockedUsers, fetchUserProfile, sendFriendRequest, acceptFriendRequest, rejectFriendRequest, removeFriend, blockUser, unblockUser,
        handleNewDm, handleNewComment, handleIncomingFriendRequest, markConversationAsRead,
        fetchFeed, fetchUserPosts, createPost, deletePost, fetchComments, createComment, deleteComment,
        followUser, unfollowUser, toggleLike, searchForMentions,
        $reset
    };
});
