
/**
 * Central configuration describing every binding modality the admin panel manages.
 *
 * Keeping this metadata in one module means the generic <BindingSettingsPanel>
 * can render any modality with a single `<BindingSettingsPanel binding-type="llm" />`
 * tag. All per-type naming, store action prefixes, icon keys and alias shape live
 * here — never duplicated inside the Vue components.
 *
 * The store action names follow the exact convention exposed by useAdminStore:
 *   llm  -> fetchBindings / addBinding / ...
 *   tti  -> fetchTtiBindings / addTtiBinding / ...
 *   rag  -> fetchRagBindings / addRagBinding / ...
 */

// The alias "shape" tells ModelProfilesGrid how to render the editable fields.
// Every profile carries a common core (title, description, model_name); the
// modality-specific extras are layered on top.
const CORE_ALIAS_FIELDS = [
    { key: 'title', label: 'Title', type: 'text', placeholder: 'Human friendly name' },
    { key: 'description', label: 'Description', type: 'textarea', placeholder: 'What this model profile is for' },
];

const LLM_ONLY_FIELDS = [
    { key: 'vision_enabled', label: 'Vision capable', type: 'boolean' },
    { key: 'forced_context_size', label: 'Context size (tokens)', type: 'number', placeholder: 'e.g. 32768' },
    { key: 'temperature', label: 'Temperature', type: 'number', step: 0.1 },
    { key: 'top_p', label: 'Top P', type: 'number', step: 0.05 },
    { key: 'top_k', label: 'Top K', type: 'number' },
    { key: 'repeat_penalty', label: 'Repeat penalty', type: 'number', step: 0.05 },
    { key: 'allow_parameters_override', label: 'Allow user parameter overrides', type: 'boolean' },
];

const REASONING_FIELDS = [
    { key: 'reasoning_activation', label: 'Reasoning default ON', type: 'boolean' },
    { key: 'reasoning_effort', label: 'Reasoning effort', type: 'select', options: ['', 'low', 'medium', 'high', 'max'] },
    { key: 'reasoning_summary', label: 'Reasoning summary', type: 'boolean' },
];

export const BINDING_TYPES = {
    llm: {
        key: 'llm',
        label: 'LLM',
        longLabel: 'Large Language Models',
        icon: 'IconCpuChip',
        description: 'Text generation models used for chat, completion and agent workflows.',
        apiPrefix: '/api/admin/bindings',
        storePrefix: '',            // fetchBindings, addBinding ...
        aliasFields: [...CORE_ALIAS_FIELDS, ...LLM_ONLY_FIELDS, ...REASONING_FIELDS],
        supportsVision: true,
        supportsCommands: true,
        supportsZoo: true,
    },
    tti: {
        key: 'tti',
        label: 'TTI',
        longLabel: 'Text-to-Image',
        icon: 'IconPhoto',
        description: 'Image generation and editing models (diffusers, SDXL, Flux...).',
        apiPrefix: '/api/admin/tti-bindings',
        storePrefix: 'Tti',
        aliasFields: [...CORE_ALIAS_FIELDS],
        supportsVision: false,
        supportsCommands: true,
        supportsZoo: true,
    },
    tts: {
        key: 'tts',
        label: 'TTS',
        longLabel: 'Text-to-Speech',
        icon: 'IconSpeakerWave',
        description: 'Speech synthesis and voice-cloning models.',
        apiPrefix: '/api/admin/tts-bindings',
        storePrefix: 'Tts',
        aliasFields: [...CORE_ALIAS_FIELDS],
        supportsVision: false,
        supportsCommands: true,
        supportsZoo: true,
    },
    stt: {
        key: 'stt',
        label: 'STT',
        longLabel: 'Speech-to-Text',
        icon: 'IconMicrophone',
        description: 'Transcription models (Whisper and friends).',
        apiPrefix: '/api/admin/stt-bindings',
        storePrefix: 'Stt',
        aliasFields: [...CORE_ALIAS_FIELDS],
        supportsVision: false,
        supportsCommands: true,
        supportsZoo: true,
    },
    ttv: {
        key: 'ttv',
        label: 'TTV',
        longLabel: 'Text-to-Video',
        icon: 'IconVideoCamera',
        description: 'Video generation models (SVD, AnimateDiff, Wan...).',
        apiPrefix: '/api/admin/ttv-bindings',
        storePrefix: 'Ttv',
        aliasFields: [...CORE_ALIAS_FIELDS],
        supportsVision: false,
        supportsCommands: true,
        supportsZoo: true,
    },
    ttm: {
        key: 'ttm',
        label: 'TTM',
        longLabel: 'Text-to-Music',
        icon: 'IconMusicalNote',
        description: 'Music and audio track generation models.',
        apiPrefix: '/api/admin/ttm-bindings',
        storePrefix: 'Ttm',
        aliasFields: [...CORE_ALIAS_FIELDS],
        supportsVision: false,
        supportsCommands: true,
        supportsZoo: true,
    },
    rag: {
        key: 'rag',
        label: 'RAG',
        longLabel: 'Retrieval / Vectorizers',
        icon: 'IconDatabase',
        description: 'Embedding / vectorizer models powering the knowledge stores.',
        apiPrefix: '/api/admin/rag-bindings',
        storePrefix: 'Rag',
        aliasFields: [...CORE_ALIAS_FIELDS],
        supportsVision: false,
        // RAG vectorizers expose no command executor and no install zoo through the
        // bindings API, so the generic panel must not render those tabs for RAG.
        supportsCommands: false,
        supportsZoo: false,
    },
};

/**
 * Builds the exact useAdminStore action names for a modality.
 * e.g. for 'tti' -> { fetch: 'fetchTtiBindings', add: 'addTtiBinding', ... }
 */
/**
 * Model-name families that are known to be text-only. Anything NOT matching
 * these patterns is assumed to be vision-capable. Kept conservative so we
 * never demote a real multimodal model.
 *
 * Moved here so every profile-creation path (BindingZoo, ModelProfilesGrid,
 * BindingModelsManager) shares a single source of truth.
 */
export const TEXT_ONLY_LLM_PATTERNS = [
    /llama[-_ ]?3(?!.*vision)/i,        // Llama 3 / 3.1 / 3.2 (non-vision)
    /llama[-_ ]?2/i,                     // Llama 2
    /mistral[-_ ]?7b/i,                  // Mistral 7B family
    /mixtral/i,                          // Mixtral (text-only)
    /mistral[-_ ]?nemo/i,                // Mistral NeMo
    /mistral[-_ ]?small/i,               // Mistral Small (text-only)
    /mistral[-_ ]?large(?!.*vision)/i,   // Mistral Large (non-vision)
    /glm[-_ ]?5\.2/i,                    // GLM 5.2
    /glm[-_ ]?5\.3/i,                    // GLM 5.3
];

/**
 * Does this model name represent a text-only model (vision should default OFF)?
 * Returns false when the name looks multimodal, true when it matches a known
 * text-only family.
 */
export function isTextOnlyLlmModel(modelName) {
    const name = String(modelName || '');
    return TEXT_ONLY_LLM_PATTERNS.some((pattern) => pattern.test(name));
}

/**
 * Build a unique profile title following the mandated convention
 * `<binding_alias>_<model_name>` with an increasing suffix `_2`, `_3`, … on
 * collision. `taken` is a mutable Set of names already in use; the returned
 * candidate is added to it so callers can compute several in a row safely.
 */
export function buildUniqueProfileTitle(bindingAlias, modelName, taken) {
    const safeAlias = String(bindingAlias || 'binding').trim().replace(/\s+/g, '_');
    const safeModel = String(modelName || 'model').trim().replace(/\s+/g, '_');
    const base = `${safeAlias}_${safeModel}`;
    let candidate = base;
    let counter = 2;
    while (taken.has(candidate)) {
        candidate = `${base}_${counter}`;
        counter += 1;
    }
    taken.add(candidate);
    return candidate;
}

/**
 * Collect every name currently in use on a binding (alias keys + alias titles)
 * so buildUniqueProfileTitle can avoid collisions on both dimensions.
 */
export function collectTakenProfileNames(binding) {
    const taken = new Set();
    let aliases = binding?.model_aliases || {};
    if (typeof aliases === 'string') {
        try { aliases = JSON.parse(aliases); } catch { aliases = {}; }
    }
    if (!aliases || typeof aliases !== 'object') return taken;
    for (const [key, value] of Object.entries(aliases)) {
        if (key) taken.add(key);
        const title = value && typeof value === 'object' ? (value.title || value.name) : value;
        if (typeof title === 'string' && title.trim()) taken.add(title.trim());
    }
    return taken;
}

/**
 * Build a complete profile payload for one unaliased model, using the unified
 * defaults: ctx 256000 + forced 256000 + vision heuristic for LLM, and the
 * bare mapping for the other modalities. The generated title follows the
 * `<binding_alias>_<model_name>` convention.
 */
export function buildDefaultProfilePayload(binding, bindingType, modelName, taken) {
    const title = buildUniqueProfileTitle(binding?.alias || binding?.name || 'binding', modelName, taken);
    const alias = {
        title,
        name: title,
        model_name: modelName,
        description: '',
    };
    if (bindingType === 'llm') {
        const vision = !isTextOnlyLlmModel(modelName);
        alias.has_vision = vision;
        alias.vision_enabled = vision;
        alias.ctx_size = 256000;
        alias.forced_context_size = 256000;
        alias.allow_parameters_override = true;
        alias.reasoning_activation = false;
    }
    return {
        original_model_name: modelName,
        new_model_name: modelName,
        alias,
    };
}

export function bindingActions(bindingType) {
    const cfg = BINDING_TYPES[bindingType];
    if (!cfg) throw new Error(`Unknown binding type '${bindingType}'`);
    const p = cfg.storePrefix;
    // Command/zoo store actions are only emitted for modalities that actually
    // expose them on the store; for RAG these keys are `null` so the panel's
    // `typeof fn === 'function'` guards skip them cleanly.
    return {
        fetch: `fetch${p}Bindings`,
        fetchAvailableTypes: `fetchAvailable${p}BindingTypes`,
        add: `add${p}Binding`,
        update: `update${p}Binding`,
        remove: `delete${p}Binding`,
        fetchModels: `fetch${p}BindingModels`,
        saveAlias: `save${p}ModelAlias`,
        deleteAlias: `delete${p}ModelAlias`,
        executeCommand: cfg.supportsCommands ? `execute${p}BindingCommand` : null,
        fetchZoo: cfg.supportsZoo ? `fetch${p}BindingZoo` : null,
        installFromZoo: cfg.supportsZoo ? `install${p}FromZoo` : null,
    };
}

/**
 * Resolve the concrete callable for one of the store actions declared by
 * bindingActions against a provided admin store instance. Returns `null` when
 * the action is unavailable on this modality. This is the shared lookup used
 * by every profile-creation / deletion path so nothing re-implements the
 * modality-prefix arithmetic.
 */
export function resolveBindingAction(adminStore, bindingType, actionKey) {
    const names = bindingActions(bindingType);
    const storeName = names[actionKey];
    if (!storeName) return null;
    const fn = adminStore?.[storeName];
    return typeof fn === 'function' ? fn.bind(adminStore) : null;
}


