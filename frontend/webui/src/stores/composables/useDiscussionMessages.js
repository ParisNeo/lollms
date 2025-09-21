// frontend/webui/src/stores/composables/useDiscussionMessages.js
import apiClient from '../../services/api';
import { processSingleMessage, processMessages } from './discussionProcessor';

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result);
        reader.onerror = error => reject(error);
    });
}

export function useDiscussionMessages(state, stores, getActions) {
    const { messages, currentDiscussionId } = state;
    const { uiStore, authStore } = stores;

    async function refreshActiveDiscussionMessages() {
        if (!currentDiscussionId.value) return;
        try {
            const response = await apiClient.get(`/api/discussions/${currentDiscussionId.value}`);
            messages.value = processMessages(response.data);
            state.emit('discussion:refreshed');
            await getActions().fetchContextStatus(currentDiscussionId.value);
        } catch (error) {
            uiStore.addNotification('Could not refresh discussion.', 'error');
        }
    }

    async function toggleImageActivation({ messageId, imageIndex }) {
        if (!currentDiscussionId.value) return;
        try {
            const response = await apiClient.put(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}/images/${imageIndex}/toggle`);
            const updatedMessage = processSingleMessage(response.data);
            const index = messages.value.findIndex(m => m.id === messageId);
            if (index !== -1) messages.value[index] = updatedMessage;
            await getActions().fetchContextStatus(currentDiscussionId.value);
        } catch (error) {
            uiStore.addNotification('Failed to toggle image status.', 'error');
        }
    }

    async function addManualMessage({ sender_type }) {
        if (!currentDiscussionId.value) return;
        const lastMessage = messages.value.length > 0 ? messages.value[messages.value.length - 1] : null;
        let senderName = authStore.user.username;
        if (sender_type === 'assistant') senderName = state.activePersonality.value?.name || 'assistant';
        const newMessage = {
            id: `temp-manual-${Date.now()}`, sender: senderName, sender_type, content: '',
            created_at: new Date().toISOString(), parent_message_id: lastMessage ? lastMessage.id : null,
            startInEditMode: true
        };
        messages.value.push(newMessage);
    }

    async function saveManualMessage({ tempId, content }) {
        if (!currentDiscussionId.value) return;
        const tempMessage = messages.value.find(m => m.id === tempId);
        if (!tempMessage) return;
        try {
            const response = await apiClient.post(`/api/discussions/${currentDiscussionId.value}/messages`, {
                content, sender_type: tempMessage.sender_type, parent_message_id: tempMessage.parent_message_id
            });
            const finalMessage = processSingleMessage(response.data);
            const index = messages.value.findIndex(m => m.id === tempId);
            if (index !== -1) messages.value.splice(index, 1, finalMessage);
            uiStore.addNotification("Message added successfully.", "success");
        } catch (error) {
            const index = messages.value.findIndex(m => m.id === tempId);
            if (index !== -1) messages.value.splice(index, 1);
        }
    }

    async function saveMessageChanges({ messageId, newContent, keptImagesB64, newImageFiles }) {
        if (!currentDiscussionId.value) return;
        const newImagesAsBase64 = await Promise.all(newImageFiles.map(file => fileToBase64(file)));
        const payload = { content: newContent, kept_images_b64: keptImagesB64, new_images_b64: newImagesAsBase64 };
        try {
            const response = await apiClient.put(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}`, payload);
            const updatedMessage = processSingleMessage(response.data);
            const index = messages.value.findIndex(m => m.id === messageId);
            if (index !== -1) messages.value[index] = updatedMessage;
            uiStore.addNotification('Message updated.', 'success');
            await getActions().fetchContextStatus(currentDiscussionId.value);
        } catch (e) {}
    }

    async function deleteMessage({ messageId }) {
        if (!currentDiscussionId.value) return;
        const discussionId = currentDiscussionId.value;
        try {
            await apiClient.delete(`/api/discussions/${discussionId}/messages/${messageId}`);
            await getActions().selectDiscussion(discussionId, null, true); 
            uiStore.addNotification('Message and branch deleted.', 'success');
        } catch (error) {
            uiStore.addNotification('Failed to delete message.', 'error');
        }
    }

    async function gradeMessage({ messageId, change }) {
        if (!currentDiscussionId.value) return;
        try {
            const response = await apiClient.put(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}/grade`, { change });
            const message = messages.value.find(m => m.id === messageId);
            if(message) message.user_grade = response.data.user_grade;
        } catch (e) {}
    }

    async function uploadDiscussionImage(file) {
        if (!currentDiscussionId.value) return;
        try {
            const formData = new FormData();
            formData.append('file', file);
            const response = await apiClient.post(`/api/discussions/${currentDiscussionId.value}/images`, formData);
            if (state.discussions.value[currentDiscussionId.value]) {
                Object.assign(state.discussions.value[currentDiscussionId.value], response.data);
            }
            await getActions().fetchContextStatus(currentDiscussionId.value);
            const message = file.type === 'application/pdf' ? 'PDF pages added as images.' : 'Image added.';
            uiStore.addNotification(message, 'success');
        } catch(error) { uiStore.addNotification('Failed to add file.', 'error'); }
    }

    async function deleteAllDiscussionImages() {
        if (!currentDiscussionId.value) return;
        try {
            const response = await apiClient.delete(`/api/discussions/${currentDiscussionId.value}/images`);
            if (state.discussions.value[currentDiscussionId.value]) {
                Object.assign(state.discussions.value[currentDiscussionId.value], response.data);
            }
            await getActions().fetchContextStatus(currentDiscussionId.value);
            uiStore.addNotification('All images deleted.', 'success');
        } catch (error) { uiStore.addNotification('Failed to delete images.', 'error'); }
    }

    async function deleteDiscussionImage(imageIndex) {
        if (!currentDiscussionId.value) return;
        try {
            const response = await apiClient.delete(`/api/discussions/${currentDiscussionId.value}/images/${imageIndex}`);
            if (state.discussions.value[currentDiscussionId.value]) {
                Object.assign(state.discussions.value[currentDiscussionId.value], response.data);
            }
            await getActions().fetchContextStatus(currentDiscussionId.value);
        } catch(error) {}
    }

    return {
        refreshActiveDiscussionMessages,
        toggleImageActivation, addManualMessage, saveManualMessage,
        saveMessageChanges, deleteMessage, gradeMessage,
        uploadDiscussionImage, deleteAllDiscussionImages, deleteDiscussionImage
    };
}