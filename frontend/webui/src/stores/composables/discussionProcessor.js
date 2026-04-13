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
    const username = authStore.user?.username;
    
    // Consolidate metadata access - Handle both Object and String (from DB) formats
    let metadata = msg.metadata || {};
    if (typeof metadata === 'string') {
        try {
            metadata = JSON.parse(metadata);
        } catch (e) {
            metadata = {};
        }
    }

    const binding_name = msg.binding_name || metadata.binding;
    const model_name = msg.model_name || metadata.model;
    
    const modelUsedId = `${binding_name}/${model_name}`;
    const modelInfo = dataStore.availableLollmsModels.find(m => m.id === modelUsedId);
    
    // Default to true if model info is not found (e.g., for older messages)
    const visionSupport = modelInfo?.alias?.has_vision ?? true;
    
    // --- Sender Type Correction Logic ---
    let senderType = msg.sender_type;
    if (!senderType) {
        const allPersonalityNames = new Set(dataStore.allPersonalities.map(p => p.name));
        if (msg.sender === username) senderType = 'user';
        else if (allPersonalityNames.has(msg.sender)) senderType = 'assistant';
        else senderType = 'user';
    }

    // Consolidate Widgets with deep copy to avoid reference issues
    const rawWidgets = metadata.inline_widgets || metadata.INLINE_WIDGETS || [];
    let normalizedWidgets = Array.isArray(rawWidgets) ? rawWidgets.map(w => ({...w})) : [];

    // --- BULK MODEL PROCESSING ---
    // We do NOT strip tags here because the renderer needs them as anchors for components.
    // The markdownParser handles the sanitization of the raw HTML content if it's outside components.
    let cleanContent = msg.content || "";

    // Improved resolution order for events and sources
    const events = msg.events || metadata.events || metadata.EVENTS || [];
    
    // [FIX] Robust Widget Recovery: Scans the event log for 'widget_done' entries.
    // This handles bulk models where metadata.inline_widgets might be empty.
    if (Array.isArray(events)) {
        events.forEach(e => {
            if (e.type === 'widget_done' && e.content) {
                const title = e.content.title || 'Interactive Widget';
                const source = e.content.content || e.content.chunk || '';
                
                // If this widget isn't already in our normalized list, add it.
                if (!normalizedWidgets.find(w => w.title === title || w.source === source)) {
                    normalizedWidgets.push({
                        id: title, // Use title as ID for easier lookup in anchor tags
                        title: title,
                        source: source,
                        type: e.content.widget_type || 'html',
                        is_loading: false
                    });
                }
            }
        });
    }
    let sources = Array.isArray(msg.sources) && msg.sources.length > 0 
                 ? [...msg.sources] 
                 : (metadata.sources || metadata.SOURCES || []);

    // [FIX] Source Promotion: If top-level sources are empty, scan events for an embedded 'sources' block
    if (Array.isArray(sources) && sources.length === 0 && Array.isArray(events)) {
        const embeddedSourcesEvent = events.find(e => e.type === 'sources');
        if (embeddedSourcesEvent && Array.isArray(embeddedSourcesEvent.content)) {
            sources = embeddedSourcesEvent.content;
        }
    }

    return {
        ...msg,
        content: cleanContent,
        binding_name,
        model_name,
        sender_type: senderType,
        events,
        sources,
        image_references: msg.image_references || [],
        active_images: msg.active_images || [],
        inline_widgets: normalizedWidgets,
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