// frontend/webui/src/stores/composables/discussionProcessor.js
import { useAuthStore } from '../auth';
import { useDataStore } from '../data';

/**
 * Processes a single message object, enriching it with derived data.
 * This function is shared across multiple composables.
 * @param {object} msg - The raw message object from the backend.
 * @returns {object|null} The processed message object or null.
 */
export function processSingleMessage(msg) {
    const authStore = useAuthStore();
    const dataStore = useDataStore();
    if (!msg) return null;
    const username = authStore.user?.username?.toLowerCase();
    
    // Consolidate metadata access
    const metadata = msg.metadata || {};
    const binding_name = msg.binding_name || metadata.binding;
    const model_name = msg.model_name || metadata.model;
    
    const modelUsedId = `${binding_name}/${model_name}`;
    const modelInfo = dataStore.availableLollmsModels.find(m => m.id === modelUsedId);
    
    // Default to true if model info is not found (e.g., for older messages)
    const visionSupport = modelInfo?.alias?.has_vision ?? true;
    
    return {
        ...msg,
        binding_name,
        model_name,
        sender_type: msg.sender_type || (msg.sender?.toLowerCase() === username ? 'user' : 'assistant'),
        events: msg.events || metadata.events || [],
        sources: msg.sources || metadata.sources || [],
        image_references: msg.image_references || [],
        active_images: msg.active_images || [],
        vision_support: visionSupport,
        branches: msg.branches || null,
    };
}

/**
 * Processes an array of raw message objects.
 * @param {Array<object>} rawMessages - The array of messages from the backend.
 * @returns {Array<object>} The array of processed message objects.
 */
export function processMessages(rawMessages) {
    if (!Array.isArray(rawMessages)) return [];
    return rawMessages.map(msg => processSingleMessage(msg));
}