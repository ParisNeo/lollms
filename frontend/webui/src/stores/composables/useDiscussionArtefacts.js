import { storeToRefs } from 'pinia';
import apiClient from '../../services/api';

export function useDiscussionArtefacts(state, stores, getActions) {
    const {
        activeDiscussionArtefacts,
        isLoadingArtefacts,
        currentDiscussionId,
    } = state;

    const { uiStore } = stores;

    async function fetchArtefacts(discussionId) {
        if (!discussionId) return;
        isLoadingArtefacts.value = true;
        try {
            const response = await apiClient.get(`/api/discussions/${discussionId}/artefacts`);
            if (currentDiscussionId.value === discussionId) {
                activeDiscussionArtefacts.value = response.data;
            }
        } catch (error) {
            // Error is handled by the global error handler in api.js
        } finally {
            isLoadingArtefacts.value = false;
        }
    }

    async function addArtefact({ discussionId, file, extractImages = true }) {
        if (!discussionId) return;
        const formData = new FormData();
        formData.append('file', file);
        formData.append('extract_images', String(extractImages)); // Send as string

        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            if (currentDiscussionId.value === discussionId) {
                activeDiscussionArtefacts.value.push(response.data);
            }
        } catch (error) {
            // Error handled globally
        }
    }

    async function createManualArtefact(payload) {
        const { discussionId, title, content, imagesB64 } = payload;
        await apiClient.post(`/api/discussions/${discussionId}/artefacts/manual`, { title, content, images_b64: imagesB64 });
        await fetchArtefacts(discussionId);
    }

    async function updateArtefact(payload) {
        const { discussionId, artefactTitle, newContent, newImagesB64, keptImagesB64, version, updateInPlace } = payload;
        await apiClient.put(`/api/discussions/${discussionId}/artefacts/${encodeURIComponent(artefactTitle)}`, {
            new_content: newContent,
            new_images_b64: newImagesB64,
            kept_images_b64: keptImagesB64,
            version: version,
            update_in_place: updateInPlace
        });
        await fetchArtefacts(discussionId);
    }
    
    return {
        fetchArtefacts,
        addArtefact,
        createManualArtefact,
        updateArtefact,
    };
}