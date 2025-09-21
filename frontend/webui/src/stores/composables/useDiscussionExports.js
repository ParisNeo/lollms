// frontend/webui/src/stores/composables/useDiscussionExports.js
import apiClient from '../../services/api';

export function useDiscussionExports(state, stores, getActions) {
    const { uiStore, authStore, tasksStore } = stores;

    async function exportDiscussions(discussionIds) {
        uiStore.addNotification('Preparing export...', 'info');
        try {
            const response = await apiClient.post('/api/discussions/export', { discussion_ids: discussionIds.length > 0 ? discussionIds : null }, { responseType: 'blob' });
            const blob = new Blob([response.data], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `lollms_export_${authStore.user?.username}_${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
            document.body.appendChild(a); a.click(); document.body.removeChild(a);
            URL.revokeObjectURL(url);
            uiStore.addNotification('Export successful!', 'success');
        } catch (error) { console.error("Export failed:", error); }
    }

    async function exportCodeToZip(discussionId) {
        if (!discussionId) return;
        uiStore.addNotification('Preparing code export...', 'info');
        try {
            const response = await apiClient.get(`/api/discussions/${discussionId}/export-code`, { responseType: 'blob' });
            const blob = new Blob([response.data], { type: 'application/zip' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const contentDisposition = response.headers['content-disposition'];
            let filename = `code_export_${discussionId.substring(0, 8)}.zip`;
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                if (filenameMatch && filenameMatch[1]) filename = filenameMatch[1];
            }
            a.download = filename;
            document.body.appendChild(a); a.click(); document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (error) {
            // Error handling for blob responses
        }
    }

    async function exportMessageCodeToZip({ content, title }) {
        if (!content || !content.includes('```')) {
            uiStore.addNotification('No code blocks found in this message.', 'info');
            return;
        }
        uiStore.addNotification('Preparing code export...', 'info');
        try {
            const response = await apiClient.post('/api/discussions/export-message-code', { content, discussion_title: title }, { responseType: 'blob' });
            const blob = new Blob([response.data], { type: 'application/zip' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const contentDisposition = response.headers['content-disposition'];
            let filename = `code_export_${title.replace(/\s/g, '_')}.zip`;
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                if (filenameMatch && filenameMatch) filename = filenameMatch;
            }
            a.download = filename;
            document.body.appendChild(a); a.click(); document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (error) {
            // Error handling
        }
    }

    async function exportMessage({ discussionId, messageId, format }) {
        uiStore.addNotification(`Exporting message as ${format.toUpperCase()}...`, 'info');
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/messages/${messageId}/export`, { format }, { responseType: 'blob' });
            const blob = new Blob([response.data], { type: response.headers['content-type'] });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            let filename = `message_export.${format}`;
            const contentDisposition = response.headers['content-disposition'];
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                if (filenameMatch && filenameMatch) filename = filenameMatch;
            }
            a.download = filename;
            document.body.appendChild(a); a.click(); document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error("Message export failed:", error);
            uiStore.addNotification(error.response?.data?.detail || 'Failed to export message.', 'error');
        }
    }

    async function exportRawContent({ content, format }) {
        uiStore.addNotification(`Exporting content as ${format.toUpperCase()}...`, 'info');
        try {
            const response = await apiClient.post(`/api/files/export-content`, { content, format }, { responseType: 'blob' });
            const blob = new Blob([response.data], { type: response.headers['content-type'] });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            let filename = `export.${format}`;
            const contentDisposition = response.headers['content-disposition'];
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                if (filenameMatch && filenameMatch) filename = filenameMatch;
            }
            a.download = filename;
            document.body.appendChild(a); a.click(); document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error("Content export failed:", error);
            uiStore.addNotification(error.response?.data?.detail || 'Failed to export content.', 'error');
        }
    }

    async function compileLatexCode({ code }) {
        if (!state.currentDiscussionId.value) {
            uiStore.addNotification('No active discussion selected.', 'error');
            throw new Error('No active discussion.');
        }
        try {
            const response = await apiClient.post(`/api/discussions/${state.currentDiscussionId.value}/compile-latex`, { code });
            if (response.data.pdf_b64) {
                uiStore.addNotification('LaTeX compiled successfully!', 'success');
            }
            return response.data;
        } catch (error) {
            const errorData = error.response?.data;
            const errorMessage = errorData?.error || 'LaTeX compilation failed.';
            const errorLogs = errorData?.logs || 'No logs available.';
            uiStore.addNotification(errorMessage, 'error');
            throw { message: errorMessage, logs: errorLogs };
        }
    }
    
    async function pruneDiscussions() {
        const confirmed = await uiStore.showConfirmation({
            title: 'Prune Empty Discussions',
            message: 'This will permanently delete all of your discussions that contain one message or fewer. This action cannot be undone.',
            confirmText: 'Prune Discussions',
        });

        if (confirmed) {
            try {
                const response = await apiClient.post('/api/discussions/prune');
                tasksStore.addTask(response.data);
                uiStore.addNotification('Discussion pruning has started.', 'info');
            } catch (error) {
                console.error("Failed to start discussion pruning task:", error);
            }
        }
    }

    return {
        exportDiscussions,
        exportCodeToZip,
        exportMessageCodeToZip,
        exportMessage,
        exportRawContent,
        compileLatexCode,
        pruneDiscussions
    };
}