<!-- [UPDATE] frontend/webui/src/components/chat/MessageBubble.vue -->
<script setup>
import { computed, ref, onMounted, onUnmounted, watch, markRaw, nextTick } from 'vue';
import { marked } from 'marked';
import { useAuthStore } from '../../stores/auth';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';
import StepDetail from './StepDetail.vue';
import WaitingIndicator from './WaitingIndicator.vue';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import { oneDark } from '@codemirror/theme-one-dark';
import { EditorView, keymap } from '@codemirror/view';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconThumbUp from '../../assets/icons/IconThumbUp.vue';
import IconThumbDown from '../../assets/icons/IconThumbDown.vue';
import IconToken from '../../assets/icons/IconToken.vue';
import IconThinking from '../../assets/icons/IconThinking.vue';
import IconTool from '../../assets/icons/IconTool.vue';
import IconObservation from '../../assets/icons/IconObservation.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconError from '../../assets/icons/IconError.vue';
import IconScratchpad from '../../assets/icons/IconScratchpad.vue';
import IconEventDefault from '../../assets/icons/IconEventDefault.vue';
import IconCog from '../../assets/icons/IconCog.vue';
import IconStepEnd from '../../assets/icons/IconStepEnd.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import IconDocumentText from '../../assets/icons/IconDocumentText.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconSpeakerWave from '../../assets/icons/IconSpeakerWave.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconGitBranch from '../../assets/icons/ui/IconGitBranch.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconCircle from '../../assets/icons/IconCircle.vue';
import IconClock from '../../assets/icons/IconClock.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue'; 
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue';
import IconGather from '../../assets/icons/IconGather.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconWrenchScrewdriver from '../../assets/icons/IconWrenchScrewdriver.vue';

const props = defineProps({
  message: { type: Object, required: true },
});

// Helper to determine if timeline content should be collapsed and rendered as markdown
const isComplexContent = (event) => {
    const type = event.type?.toLowerCase() || '';
    const content = String(event.content || '');
    
    // Types that usually contain code or massive data
    const complexTypes = ['artefact_done', 'tool_output', 'tool_call', 'exception', 'code_exec'];
    if (complexTypes.includes(type)) return true;
    
    // Content-based check (looks like HTML, JSON, or is very long)
    if (content.startsWith('<') || content.startsWith('{') || content.startsWith('[') || content.length > 150) return true;
    
    return false;
};

// ── Execution-timeline helpers ───────────────────────────────────────────
// Drop purely decorative separator/punctuation lines ("----", "====", "…").
const isNoiseLine = (content) => {
    const s = String(content ?? '').trim();
    if (!s) return true;
    return /^[-=_*~.#\s]+$/.test(s) || /^[\u2500-\u257F\s]+$/.test(s);
};

// Tokens that indicate a line is the *actual* failure message inside a noisy
// multi-line payload (traceback, pip output, subprocess stderr, ...).
const ERROR_HINT_PATTERN = /\b(error|exception|traceback|failed|failure|fatal|critical|cannot|can't|unable|refused|denied|not found|invalid|timed out|timeout|terminated with error|exit code|nonzero|errno|raise\b)/i;

// Keys (in priority order) that carry the human-meaningful failure text when an
// event payload is a JSON object/envelope.
const ERROR_KEYS = ['error', 'message', 'detail', 'reason', 'stderr', 'traceback', 'exception', 'output', 'result'];

// Keys that carry a tool/event label.
const NAME_KEYS = ['tool_name', 'toolName', 'tool', 'name', 'label', 'operation', 'action'];

// Keys that carry tool arguments.
const ARGS_KEYS = ['arguments', 'args', 'parameters', 'params', 'input', 'kwargs'];

// Keys that carry the successful result body.
const RESULT_KEYS = ['result', 'output', 'response', 'data', 'return', 'value', 'content'];

// Keys that carry timing information.
const TIMING_KEYS = ['timing', 'duration', 'duration_ms', 'latency', 'elapsed', 'elapsed_ms', 'time', 'took', 'took_ms'];

// Pretty-print any value for display: objects become indented JSON, strings
// pass through, and null/undefined become empty strings.
const prettyValue = (value) => {
    if (value === null || value === undefined) return '';
    if (typeof value === 'string') return value;
    try {
        return JSON.stringify(value, null, 2);
    } catch {
        return String(value);
    }
};

// Does the multi-line text contain at least one line that looks like a real
// error? Used both for status detection and to pick the right line to surface.
const findMeaningfulErrorLine = (text) => {
    const lines = String(text || '').split('\n').map((l) => l.trim()).filter(Boolean);
    if (!lines.length) return '';
    // Prefer the last line that looks like an error (tracebacks put the most
    // specific message last), ignoring pure separator noise.
    for (let i = lines.length - 1; i >= 0; i--) {
        if (isNoiseLine(lines[i])) continue;
        if (ERROR_HINT_PATTERN.test(lines[i])) return lines[i];
    }
    // Fall back to the last non-noise line.
    for (let i = lines.length - 1; i >= 0; i--) {
        if (!isNoiseLine(lines[i])) return lines[i];
    }
    return '';
};

// Recursively probe an object/array for the most specific error text. Handles
// nested envelopes like { error: { message: '...' } } or { detail: {...} }.
const probeErrorFromObject = (obj, depth = 0) => {
    if (!obj || typeof obj !== 'object' || depth > 4) return null;
    for (const key of ERROR_KEYS) {
        const v = obj[key];
        if (typeof v === 'string' && v.trim()) {
            const line = findMeaningfulErrorLine(v) || v.trim();
            return line;
        }
        if (v && typeof v === 'object') {
            const nested = probeErrorFromObject(v, depth + 1);
            if (nested) return nested;
        }
    }
    return null;
};

// Pull a value by trying a list of candidate keys on an object.
const pickField = (obj, keys) => {
    if (!obj || typeof obj !== 'object') return undefined;
    for (const key of keys) {
        if (obj[key] !== undefined && obj[key] !== null && obj[key] !== '') return obj[key];
    }
    return undefined;
};


// Visual identity per event type: human label, icon and colour tone.
const EVENT_TYPE_META = {
    thought:          { label: 'Thinking',          icon: IconThinking,          tone: 'thought' },
    tool_call:        { label: 'Tool call',         icon: IconWrenchScrewdriver, tone: 'tool' },
    tool_output:      { label: 'Tool output',       icon: IconCheckCircle,       tone: 'tool' },
    observation:      { label: 'Observation',       icon: IconObservation,       tone: 'info' },
    scratchpad:       { label: 'Scratchpad',        icon: IconScratchpad,        tone: 'info' },
    code_exec:        { label: 'Code execution',    icon: IconCode,              tone: 'tool' },
    search:           { label: 'Search',            icon: IconMagnifyingGlass,   tone: 'info' },
    step_start:       { label: 'Step started',      icon: IconCog,               tone: 'step' },
    step_end:         { label: 'Step finished',     icon: IconStepEnd,           tone: 'step' },
    artefact_create:  { label: 'Building artefact', icon: IconCode,              tone: 'artefact' },
    artefact_update:  { label: 'Updating artefact', icon: IconCode,              tone: 'artefact' },
    info:             { label: 'Info',              icon: IconInfo,              tone: 'info' },
    warning:          { label: 'Warning',           icon: IconInfo,              tone: 'warning' },
    error:            { label: 'Error',             icon: IconError,             tone: 'error' },
    exception:        { label: 'Exception',         icon: IconError,             tone: 'error' },
};
const DEFAULT_EVENT_META = { label: 'Event', icon: IconEventDefault, tone: 'info' };

const eventMeta = (event) => {
    const type = String(event?.type || '').toLowerCase();
    if (EVENT_TYPE_META[type]) return EVENT_TYPE_META[type];
    if (type.startsWith('artefact')) return EVENT_TYPE_META.artefact_create;
    if (type.startsWith('tool')) return EVENT_TYPE_META.tool_output;
    if (type.includes('error') || type.includes('exception') || type.includes('fail')) return EVENT_TYPE_META.error;
    if (type.includes('warning')) return EVENT_TYPE_META.warning;
    return DEFAULT_EVENT_META;
};

// ── Artefact operation identity ──────────────────────────────────────────
// Artefact writes come in two very different flavours and must NEVER look the
// same in the timeline:
//   * FULL REWRITE  — the whole file is (re)generated from scratch. Risky,
//     wholesale replacement. Distinct icon (document), violet tone, "REWRITE"
//     badge.
//   * PATCH / EDIT  — only a targeted portion is modified (search/replace,
//     surgical edit). Amber tone, wrench icon, "PATCH" badge.
// Detection is best-effort across the many shapes the backend / LLM tool
// emits: an explicit ``operation`` field, a nested envelope, or an
// "operation: full_rewrite" fragment embedded in the textual content.
const ARTEFACT_OPERATION_META = {
    rewrite: {
        kind: 'rewrite',
        label: 'Full rewrite',
        badge: 'REWRITE',
        icon: IconDocumentText,
        tone: 'artefact-rewrite',
    },
    patch: {
        kind: 'patch',
        label: 'Patch',
        badge: 'PATCH',
        icon: IconWrenchScrewdriver,
        tone: 'artefact-patch',
    },
};

// Normalise a raw operation token ("full_rewrite", "apply_patch", "patch",
// "rewrite", "overwrite", "edit", ...) into 'rewrite' | 'patch' | ''.
const classifyOperation = (raw) => {
    const token = String(raw ?? '').toLowerCase().trim();
    if (!token) return '';
    if (/full[_ -]?rewrite|rewrite|overwrite|regenerate|create/.test(token)) return 'rewrite';
    if (/patch|apply[_ -]?patch|search[_ -]?replace|edit|surgical|diff|modify|update/.test(token)) return 'patch';
    return '';
};

// Extract the operation kind for an artefact event from every plausible source:
// explicit event/envelope fields first, then a textual "operation: X" fragment.
const deriveArtefactOperation = (event, envelope) => {
    const explicit =
        pickField(envelope, ['operation', 'op', 'mode', 'edit_mode']) ??
        pickField(event, ['operation', 'op', 'mode', 'edit_mode']);
    let kind = classifyOperation(explicit);
    if (!kind && envelope && typeof envelope.tool_input === 'object') {
        kind = classifyOperation(envelope.tool_input?.operation || envelope.tool_input?.mode);
    }
    if (!kind) {
        const blob = typeof event?.content === 'string' ? event.content : prettyValue(event?.content);
        const m = blob.match(/\b(?:operation|action|mode)\s*[:=]\s*([a-z_ -]+)/i);
        if (m) kind = classifyOperation(m[1]);
    }
    // Fallback: the raw textual blobs that the artefact builder prints.
    if (!kind) {
        const blob = (typeof event?.content === 'string' ? event.content : prettyValue(event?.content)).toLowerCase();
        if (/\bfull[_ -]?rewrite\b|\boverwrit/.test(blob)) kind = 'rewrite';
        else if (/\bpatch(?:ing|ed)?\b|\bsearch[ _-]?replace\b|\bappl(?:y|ied) patch/.test(blob)) kind = 'patch';
    }
    return kind ? ARTEFACT_OPERATION_META[kind] : null;
};

// Try to JSON-parse an event payload (string or object) into a plain object,
// returning null when it is not a structured value.
const parsePayload = (raw) => {
    if (raw && typeof raw === 'object') return raw;
    const str = String(raw || '').trim();
    if (str.startsWith('{') || str.startsWith('[')) {
        try { return JSON.parse(str); } catch { /* not JSON */ }
    }
    return null;
};

// Does the event represent a failure (status field, tone, or text heuristic)?
const isFailureEvent = (event) => normalizeEvent(event).status === 'error';

// Extract the real, human-meaningful error message from a string/JSON payload.
const extractErrorMessage = (raw) => {
    if (raw == null) return '';
    const parsed = parsePayload(raw);
    if (parsed) {
        const fromObj = probeErrorFromObject(parsed);
        if (fromObj) return fromObj;
    }
    const str = typeof raw === 'string' ? raw : prettyValue(raw);
    const meaningful = findMeaningfulErrorLine(str);
    return meaningful || str.trim();
};

// Short single-line summary used for the collapsed/failure banner.
const eventSummary = (event) => {
    const normalized = normalizeEvent(event);
    if (normalized.summary) return normalized.summary;
    const str = normalized.error || normalized.result || prettyValue(event?.content);
    const first = String(str).split('\n').find((l) => l.trim() && !isNoiseLine(l)) || '';
    return first.length > 200 ? first.slice(0, 200) + '…' : first;
};

// Core: turn a raw timeline event into a fully-structured, render-ready card.
// Expected raw shape (all optional):
//   { type, content, status?, tool_name?, arguments?, result?, error?,
//     duration?, timestamp?, ... }
// ``content`` may itself be a JSON envelope carrying any of those fields.
const normalizeEvent = (event) => {
    const parsed = parsePayload(event?.content) || {};
    const envelope = (parsed && typeof parsed === 'object') ? parsed : {};

    // Resolve the base visual identity, then refine it for artefact events so
    // a full rewrite and a patch never look alike.
    const baseMeta = eventMeta(event);
    const eventTypeLower = String(event?.type || '').toLowerCase();
    const isArtefactEvent =
        eventTypeLower.startsWith('artefact') || baseMeta.tone === 'artefact';
    const artefactOp = isArtefactEvent ? deriveArtefactOperation(event, envelope) : null;

    // Operation-aware meta: same shape as eventMeta (label/icon/tone) so every
    // existing consumer (status tone checks, dot colour, icon, label) keeps
    // working unchanged. The badge text and operation kind are read from
    // ``artefactOp`` directly in the template.
    const meta = artefactOp
        ? { label: artefactOp.label, icon: artefactOp.icon, tone: artefactOp.tone }
        : baseMeta;

    // ── Status ────────────────────────────────────────────────────────
    const rawStatus = String(
        event?.status || envelope.status || ''
    ).toLowerCase();
    const textBlob = typeof event?.content === 'string'
        ? event.content
        : prettyValue(event?.content);
    const textLooksLikeError =
        /\b(failed|failure|terminated with errors|traceback|exception)\b/i.test(textBlob);
    const hasErrorField = Boolean(
        event?.error || envelope.error
    );
    let status = 'ok';
    if (['failed', 'failure', 'error', 'errored', 'cancelled', 'canceled'].includes(rawStatus)) {
        status = 'error';
    } else if (meta.tone === 'error') {
        status = 'error';
    } else if (meta.tone === 'warning' || rawStatus === 'warning') {
        status = 'warning';
    } else if (
        hasErrorField ||
        (textLooksLikeError && (event?.error || envelope.error ||
            findMeaningfulErrorLine(textBlob)))
    ) {
        status = 'error';
    }

    // ── Identity / tool name ─────────────────────────────────────────
    const toolName =
        pickField(envelope, NAME_KEYS) ||
        pickField(event, NAME_KEYS) ||
        (typeof envelope.operation === 'string' ? envelope.operation : undefined) ||
        '';

    // ── Arguments ────────────────────────────────────────────────────
    const argsRaw =
        pickField(envelope, ARGS_KEYS) ||
        pickField(event, ARGS_KEYS);
    const args = argsRaw !== undefined ? prettyValue(argsRaw) : '';

    // ── Result & error ───────────────────────────────────────────────
    const explicitError =
        (event?.error !== undefined ? event.error : undefined) ??
        (envelope.error !== undefined ? envelope.error : undefined);
    let error = '';
    if (explicitError !== undefined && explicitError !== null) {
        const parsedErr = parsePayload(explicitError);
        error = parsedErr ? (probeErrorFromObject(parsedErr) || prettyValue(parsedErr)) : prettyValue(explicitError);
    }
    if (!error && status === 'error') {
        error = extractErrorMessage(event?.content);
    }

    let result = '';
    if (status !== 'error') {
        const resultRaw =
            pickField(envelope, RESULT_KEYS) ??
            pickField(event, RESULT_KEYS);
        if (resultRaw !== undefined) result = prettyValue(resultRaw);
        else if (typeof event?.content === 'string') result = event.content;
        else result = prettyValue(event?.content);
    }

    // ── Timing ───────────────────────────────────────────────────────
    let timing = '';
    const timingRaw =
        pickField(envelope, TIMING_KEYS) ??
        pickField(event, TIMING_KEYS) ??
        event?.timing ?? event?.duration ?? event?.elapsed;
    if (timingRaw !== undefined && timingRaw !== null && timingRaw !== '') {
        if (typeof timingRaw === 'number') {
            timing = timingRaw < 1000 ? `${timingRaw} ms` : `${(timingRaw / 1000).toFixed(2)} s`;
        } else {
            timing = String(timingRaw);
        }
    } else if (event?.timestamp) {
        timing = String(event.timestamp);
    }

    // ── Summary line for the card header ─────────────────────────────
    let summary = '';
    if (toolName) {
        summary = toolName;
    } else if (status === 'error' && error) {
        summary = findMeaningfulErrorLine(error) || error;
    } else if (result) {
        summary = String(result).split('\n').find((l) => l.trim() && !isNoiseLine(l)) || '';
    } else if (typeof event?.content === 'string') {
        summary = event.content.split('\n').find((l) => l.trim() && !isNoiseLine(l)) || '';
    }
    if (summary.length > 240) summary = summary.slice(0, 240) + '…';

    return {
        meta,
        status,
        toolName: String(toolName || ''),
        args,
        result,
        error,
        timing,
        summary,
        artefactOp,
        raw: typeof event?.content === 'string' ? event.content : prettyValue(event?.content),
    };
};


const uniqueEvents = computed(() => {
    if (!props.message.events?.length) return [];
    const seen = new Set();
    const result = [];
    for (const event of props.message.events) {
        // Drop decorative-only events, but never drop a real failure even if its
        // content is terse (e.g. an error event whose payload is just "timeout").
        const normalized = normalizeEvent(event);
        const isFailure = normalized.status === 'error' || normalized.status === 'warning';
        if (!isFailure && isNoiseLine(event.content)) continue;
        const key = `${event.type}-${String(event.content || '').trim()}`;
        if (seen.has(key)) continue;
        seen.add(key);
        result.push({
            ...event,
            norm: normalized,
            contentLineCount: String(event.content || '').split('\n').length,
            multilineRaw: normalized.raw.split('\n').length > 1,
        });
    }
    return result;
});



const mathPlaceholders = new Map();
let mathCounter = 0;

function protectMath(text) {
    if (!text) return text;
    mathCounter = 0;
    mathPlaceholders.clear();

    return text.replace(/(\$\$[\s\S]*?\$$|\$[\s\S]*?\$)/g, (match) => {
        const placeholder = `<!--MATH_PLACEHOLDER_${mathCounter}-->`;
        mathPlaceholders.set(placeholder, match);
        mathCounter++;
        return placeholder;
    });
}

function unprotectHtml(html) {
    if (!html || mathPlaceholders.size === 0) return html;
    let result = html;
    for (const [placeholder, original] of mathPlaceholders.entries()) {
        const regex = new RegExp(placeholder.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&'), 'g');
        result = result.replace(regex, original);
    }
    return result;
}

const parsedMarkdown = (content) => {
    if (typeof content !== 'string') return '';
    const protectedContent = protectMath(content);
    const rawHtml = marked.parse(protectedContent, { gfm: true, breaks: true, mangle: false, smartypants: false });
    return unprotectHtml(rawHtml);
};


const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const dataStore = useDataStore();
const tasksStore = useTasksStore();
const { currentModelVisionSupport, ttsState } = storeToRefs(discussionsStore);
const { imageGenerationTasks } = storeToRefs(tasksStore);

// Execution timeline is strictly collapsed by default
const isEventsCollapsed = ref(true);
const isEditing = ref(false);
const editedContent = ref('');
const codeMirrorView = ref(null);
const isFormattingMenuOpen = ref(false);
const isSourcesVisible = ref(false);
const editedImages = ref([]);
const newImageFiles = ref([]);
const editImageInput = ref(null);
const audioPlayerRef = ref(null);
const previewMap = ref({});
const sourceRefs = ref({}); // To store refs to source items for scrolling

const selectedViewIndices = ref({});

const areActionsDisabled = computed(() => discussionsStore.generationInProgress);
const user = computed(() => authStore.user);
const isTtsActive = computed(() => {
    return !!user.value?.tts_binding_model_name && 
           user.value.tts_binding_model_name.includes('/') && 
           dataStore.availableTtsModels.length > 0;
});
const messageTtsState = computed(() => ttsState.value[props.message.id] || {});

const isCurrentUser = computed(() => props.message.sender_type === 'user' && props.message.sender === authStore.user?.username);
const isOtherUser = computed(() => props.message.sender_type === 'user' && props.message.sender !== authStore.user?.username);
const isAi = computed(() => props.message.sender_type === 'assistant');
const isSystem = computed(() => props.message.sender_type === 'system');
const isNewManualMessage = computed(() => props.message.id.startsWith('temp-manual-'));

const otherUserIcon = computed(() => {
    if (!isOtherUser.value) return null;
    return discussionsStore.activeDiscussionParticipants[props.message.sender]?.icon;
});

const senderPersonalityIcon = computed(() => {
    if (!isAi.value || !props.message.sender) return null;
    const personality = dataStore.allPersonalities.find(p => p.name === props.message.sender);
    return personality ? personality.icon_base64 : null;
});

const lastUserImage = computed(() => {
    if (props.message.sender_type !== 'assistant' || !props.message.content.includes('<annotate>')) {
        return null;
    }
    const allMessages = discussionsStore.activeMessages;
    const currentMessageIndex = allMessages.findIndex(m => m.id === props.message.id);
    if (currentMessageIndex === -1) return null;
    for (let i = currentMessageIndex - 1; i >= 0; i--) {
        const msg = allMessages[i];
        if (msg.image_references && msg.image_references.length > 0) {
            return msg.image_references[msg.image_references.length - 1];
        }
    }
    return null;
});

const exportFormats = computed(() => {
    const formats = [];
    if (authStore.export_to_txt_enabled) formats.push({ label: 'Text (.txt)', value: 'txt' });
    if (authStore.export_to_markdown_enabled) formats.push({ label: 'Markdown (.md)', value: 'md' });
    if (authStore.export_to_html_enabled) formats.push({ label: 'HTML (.html)', value: 'html' });
    if (authStore.export_to_pdf_enabled) formats.push({ label: 'PDF (.pdf)', value: 'pdf' });
    if (authStore.export_to_docx_enabled) formats.push({ label: 'Word (.docx)', value: 'docx' });
    if (authStore.export_to_xlsx_enabled) formats.push({ label: 'Excel (.xlsx)', value: 'xlsx' });
    if (authStore.export_to_pptx_enabled) formats.push({ label: 'PowerPoint (.pptx)', value: 'pptx' });
    return formats;
});

function handleExport(format) {
    discussionsStore.exportMessage({
        discussionId: discussionsStore.currentDiscussionId,
        messageId: props.message.id,
        format: format,
    });
}

function handleSpeak() {
    // If we already have a URL, the player is shown. 
    // If a task is running, don't trigger again.
    if (props.message.metadata?.audio_url || props.message.isGeneratingAudio) return;
    
    discussionsStore.generateTTSForMessage(props.message.id);
}

function isUrl(str) {
    if (typeof str !== 'string') return false;
    return str.startsWith('http://') || str.startsWith('https://');
}

function togglePreview(index) {
    if (previewMap.value[index]) {
        delete previewMap.value[index];
    } else {
        previewMap.value[index] = true;
    }
}

// Function to handle clicking citation buttons in the content
function handleCitationClick(index) {
    isSourcesVisible.value = true;

    const targetSource = sortedSources.value.find(s => s.index === index) || sortedSources.value[index - 1];

    nextTick(() => {
        const targetSourceIndex = sortedSources.value.findIndex(s => s.index === index);
        const refIndex = targetSourceIndex !== -1 ? targetSourceIndex : (index - 1);
        const el = sourceRefs.value[refIndex];

        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.classList.add('ring-4', 'ring-blue-400', 'bg-blue-50', 'dark:bg-blue-900/30');
            setTimeout(() => {
                el.classList.remove('ring-4', 'ring-blue-400', 'bg-blue-50', 'dark:bg-blue-900/30');
            }, 2500);
        }

        if (targetSource) {
            showSourceDetails(targetSource);
        }
    });
}

onMounted(() => {
    if (props.message.sources && props.message.sources.length > 3) {
        isSourcesVisible.value = false;
    } else {
        isSourcesVisible.value = true;
    }

    if (props.message.startInEditMode) {
        toggleEdit();
        delete props.message.startInEditMode;
    }
    
    // Initialize selected indices for each group
    if (imageGroups.value.length > 0) {
        imageGroups.value.forEach(group => {
            if (!selectedViewIndices.value[group.id]) {
                const activeIdx = group.indices.find(idx => isImageActive(idx));
                selectedViewIndices.value[group.id] = activeIdx !== undefined ? activeIdx : group.indices[group.indices.length - 1];
            }
        });
    }
});

const allImages = computed(() => {
    if (props.message.localImageUrls?.length > 0) return props.message.localImageUrls;
    if (props.message.image_references?.length > 0) return props.message.image_references;
    return [];
});

const imageGroups = computed(() => {
    const images = allImages.value;
    if (images.length === 0) return [];

    const metadata = props.message.metadata || {};
    const metaGroups = (metadata.image_generation_groups || []).concat(metadata.image_groups || []);
    
    const handledIndices = new Set();
    const resultGroups = [];

    // Temporary storage for slide items to group them
    let currentSlideGroup = null;

    // 1. Process defined groups
    metaGroups.forEach((g, idx) => {
        const groupIndices = g.indices.filter(i => i < images.length);
        if (groupIndices.length > 0) {
            groupIndices.forEach(i => handledIndices.add(i));

            if (g.type === 'slide_item') {
                if (!currentSlideGroup) {
                    currentSlideGroup = {
                        id: `slideshow_${idx}`,
                        title: "Generated Slideshow",
                        type: 'slideshow',
                        indices: [],
                        images: []
                    };
                    resultGroups.push(currentSlideGroup);
                }
                currentSlideGroup.indices.push(...groupIndices);
                currentSlideGroup.images.push(...groupIndices.map(i => images[i]));
            } else {
                // If we encounter a non-slide group, close the slide group sequence (if order matters in array)
                // However, logic here pushes to resultGroups immediately if new, so just resetting ref works.
                currentSlideGroup = null;

                resultGroups.push({
                    id: g.id || `gen_group_${idx}`,
                    title: g.prompt || g.title || (g.type === 'upload' ? `Image Pack ${idx + 1}` : `Image Generation ${idx + 1}`),
                    type: g.type || 'generated',
                    indices: groupIndices,
                    images: groupIndices.map(i => images[i])
                });
            }
        }
    });

    // 2. Collect leftover images as distinct "User Upload" packs if they aren't grouped
    const leftoverIndices = images.map((_, i) => i).filter(i => !handledIndices.has(i));
    if (leftoverIndices.length > 0) {
        // Create a SEPARATE group for each leftover image so they stack vertically
        leftoverIndices.forEach((imgIndex, i) => {
            resultGroups.push({
                id: `upload_${imgIndex}`,
                title: `Attachment ${i + 1}`,
                type: 'upload',
                indices: [imgIndex],
                images: [images[imgIndex]]
            });
        });
    }

    return resultGroups;
});

const isImageActive = (index) => {
    // If array doesn't exist or is too short, default to active
    if (!props.message.active_images || !Array.isArray(props.message.active_images) || props.message.active_images.length <= index) {
        return true; 
    }
    const val = props.message.active_images[index];
    // Handle potential string boolean from backend serialization
    if (typeof val === 'string') {
        return val.toLowerCase() === 'true';
    }
    return !!val;
};

const toggleImage = (index) => {
    if (areActionsDisabled.value) {
        return;
    }
    
    const currentState = isImageActive(index);
    const desiredState = !currentState;
    
    discussionsStore.toggleImageActivation({
        messageId: props.message.id,
        imageIndex: index,
        active: desiredState
    });
};

function openImageViewer(index) {
    uiStore.openImageViewer({
        imageList: allImages.value.map(src => ({ src, prompt: 'Image from message' })),
        startIndex: index
    });
}

function openSlideshow(group) {
    // NEW: Open specific slideshow modal
    const slides = group.images.map((src, i) => ({ 
        src, 
        prompt: `Slide ${i + 1}`,
        id: `slide_${i}`
    }));
    
    uiStore.openSlideshow({
        slides: slides,
        startIndex: 0,
        title: group.title,
        messageId: props.message.id
    });
}

function handleImageClick(group, index) {
    if (group.type === 'slideshow' || group.type === 'slide_item') {
        openSlideshow(group);
    } else {
        openImageViewer(index);
    }
}

function canRegenerateImage(index, groupType) {
    // [UPDATED] Allow regeneration for slides too
    if (groupType === 'slideshow' || groupType === 'slide_item') return true;
    
    const infos = props.message.metadata?.generated_image_infos || [];
    return infos.some(info => info.index === index);
}

const isRegenerating = (groupId) => {
    const group = imageGroups.value.find(g => g.id === groupId);
    if (!group) return false;
    return group.indices.some(idx => 
        imageGenerationTasks.value.some(t => t.name.includes(`Regenerate Image ${idx}`))
    );
};

function handleRegenerateImage(index) {
    if (areActionsDisabled.value) return;
    discussionsStore.regenerateMessageImage(props.message.id, index);
}

const transformingImageKeys = ref(new Set());

function isTransformingImage(key) {
    return transformingImageKeys.value.has(key);
}

async function handleTransformImageToArtefact(group, index) {
    const key = `${group.id}-${index}`;
    if (transformingImageKeys.value.has(key)) return;

    transformingImageKeys.value = new Set(transformingImageKeys.value).add(key);
    try {
        const imageUrl = allImages.value[index];
        const { title: artefactTitle } = await discussionsStore.createArtefactFromImage({
            discussionId: discussionsStore.currentDiscussionId,
            title: `image_${_generateImageArtefactId()}`,
            imageUrl
        });

        // De-duplicate: remove the image from the message and replace it with an
        // inline artefact call so it is stored/rendered only once (as an artefact).
        await _replaceMessageImageWithInlineCall(index, imageUrl, artefactTitle);
    } catch (e) {
        // Error notification already surfaced by the store action
    } finally {
        const next = new Set(transformingImageKeys.value);
        next.delete(key);
        transformingImageKeys.value = next;
    }
}

function _generateImageArtefactId() {
    return (crypto.randomUUID) ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

async function _replaceMessageImageWithInlineCall(index, imageUrl, artefactTitle) {
    if (isNewManualMessage.value) return; // Manual messages have no persisted images to detach

    const message = discussionsStore.activeMessages.find(m => m.id === props.message.id);
    if (!message) return;

    const inlineCall = `\n[!](${artefactTitle})`;
    const updatedImages = (message.image_references || []).filter(
        (img, i) => i !== index && img !== imageUrl
    );

    try {
        // Persist through the exact contract used by handleSaveEdit (saveMessageChanges)
        await discussionsStore.saveMessageChanges({
            messageId: props.message.id,
            newContent: (message.content || '') + inlineCall,
            keptImagesB64: updatedImages,
            newImageFiles: []
        });
    } catch (e) {
        console.error('Failed to update message after artefact transformation:', e);
        uiStore.addNotification('Artefact created, but the message could not be updated.', 'warning');
    }
}

function selectView(groupId, index) {
    selectedViewIndices.value[groupId] = index;
}

watch(() => props.message.image_references, (newRefs, oldRefs) => {
    if (newRefs && oldRefs && newRefs.length > oldRefs.length) {
        imageGroups.value.forEach(group => {
            const lastIndex = group.indices[group.indices.length - 1];
            if (lastIndex >= oldRefs.length) {
                selectedViewIndices.value[group.id] = lastIndex;
            }
        });
    }
}, { deep: true });

const containsCode = computed(() => {
    return props.message.content && props.message.content.includes('```');
});

const senderName = computed(() => {
    if (isCurrentUser.value) return authStore.user?.username || 'You';
    if (isOtherUser.value) return props.message.sender;
    if (isAi.value) return props.message.sender || 'Assistant';
    return props.message.sender || 'System';
});

const hasEvents = computed(() => (props.message.events && props.message.events.length > 0) || (props.message.metadata?.events && props.message.metadata.events.length > 0));

const timelineFailureCount = computed(() =>
    uniqueEvents.value.filter(evt => isFailureEvent(evt)).length
);

const failureEvents = computed(() =>
    uniqueEvents.value
        .filter(evt => isFailureEvent(evt))
        .map(evt => {
            const normalized = normalizeEvent(evt);
            return {
                label: normalized.toolName || normalized.meta.label,
                message: normalized.error || normalized.summary || 'Execution failed.',
            };
        })
);


const sortedSources = computed(() => {
    let raw = props.message.sources || props.message.metadata?.sources;
    if ((!raw || !raw.length) && Array.isArray(props.message.events)) {
        const srcEvt = props.message.events.find(e => e.type === 'sources');
        if (srcEvt && Array.isArray(srcEvt.content)) {
            raw = srcEvt.content;
        }
    }
    if (!Array.isArray(raw) || !raw.length) return [];
    
    return [...raw].map((s, idx) => {
        const content = s.content || s.chunk_text || s.text || s.full_text || s.body || s.chunk_content || s.snippet || s.text_snippet || s.preview || s.passage || s.excerpt || s.body_text || '';
        const title = s.title || s.source || 'Source Reference';

        return {
            ...s,
            content,
            title,
            index: s.index || (idx + 1)
        };
    }).sort((a, b) => {
        if (a.index && b.index) return a.index - b.index;
        return (b.score || 0) - (a.score || 0);
    });
});;

const hasSources = computed(() => sortedSources.value.length > 0);

watch(hasSources, (has) => {
    if (has) isSourcesVisible.value = true;
}, { immediate: true });

// ── Human-readable activity label for the waiting indicator ─────────────────
// Instead of exposing technical noise ("ttft: 9729ms"), we tell the user WHAT is
// happening right now. The label is derived ONLY from data this message already
// carries (events, content markup, streaming flag), so it needs no cross-store
// plumbing. Priority order reflects how far the generation has progressed:
//   1. A concrete running tool/step event.
//   2. Structural markup currently open in `content` (artefact/processing/etc).
//   3. The model is
// ── Human-readable activity label for the waiting indicator ─────────────────
// Instead of exposing raw technical noise ("ttft: 9729ms"), we tell the user
// WHAT is happening right now. The label is derived ONLY from data this message
// already carries (events, content markup, streaming flag) so it needs no
// cross-store plumbing. Priority reflects how far the generation has progressed.
const ARTEFACT_TAG_RE = /<lollms_(?:building|working)\b([^>]*)>/i;
const classifyPendingArtefactOp = (attrs) => {
    const a = String(attrs || '').toLowerCase();
    if (/\b(?:patch|edit|update|modif|search[ _-]?replace|apply)/.test(a)) return 'patch';
    if (/\b(?:build|create|rewrite|regenerat|overwrit|new)/.test(a)) return 'create';
    return 'build';
};

// Convert a raw millisecond TTFT into a short, readable duration
// ("0.8s", "8.0s", "1m 12s"). Returns '' for missing/invalid values so the
// template can skip the whole chip cleanly.
function formatTtft(ms) {
    const v = Number(ms);
    if (!Number.isFinite(v) || v <= 0) return '';
    if (v < 1000) return `${Math.round(v)}ms`;
    const s = v / 1000;
    if (s < 60) return `${s.toFixed(1)}s`;
    const m = Math.floor(s / 60);
    const rem = Math.round(s - m * 60);
    return `${m}m ${rem}s`;
}

const isWaitingDetail = computed(() => {
    const events = Array.isArray(props.message.events) ? props.message.events : [];

    // 1. A concrete RUNNING tool/step event (most specific, most useful).
    for (let i = events.length - 1; i >= 0; i--) {
        const evt = events[i];
        const type = String(evt?.type || '').toLowerCase();
        if (!type) continue;
        if (type === 'step_end' || type === 'tool_output') continue; // completed, keep looking back
        if (type === 'tool_call') {
            const name = normalizeEvent(evt).toolName;
            return name ? `Executing tool: ${name}` : 'Summoning the demon… 😈🔥';
        }
        if (type === 'search') return 'Scouring the seven seas… 🌊🔍';
        if (type === 'code_exec') return 'Firing up the engine… 🏎️💨';
        if (type === 'step_start') {
            const name = normalizeEvent(evt).summary;
            return name ? `Working: ${name}` : 'Waking the dragon… 🐉';
        }
        if (type.startsWith('artefact')) {
            const op = normalizeEvent(evt).artefactOp;
            if (op?.kind === 'patch') return 'Stitching the patchwork… 🧵';
            if (op?.kind === 'rewrite') return 'Forging the artefact… 🔨';
            return 'Forging a new artefact… 🔨';
        }
    }


    // 2. Structural markup currently open in the streamed content.
    const raw = String(props.message.content || '');
    const artefactMatch = raw.match(ARTEFACT_TAG_RE);
    if (artefactMatch) {
        const op = classifyPendingArtefactOp(artefactMatch[1]);
        if (op === 'patch') return 'Stitching the patchwork… 🧵';
        if (op === 'create') return 'Forging an artefact… 🔨';
        return 'Forging an artefact… 🔨';
    }
    if (/<processing\b[^>]*type=["'](?:tool|tool_execution|code_execution)/i.test(raw)) {
        return 'Priming the mainframe… 🖥️⚡';
    }
    if (/<processing\b/i.test(raw)) return 'Aligning the ley lines… ✨';

    // 3. Reasoning present, no answer yet.
    if (hasThoughtContent.value) return 'Untangling the neural spaghetti… 🍝';

    // 4. Plain streaming with nothing else to report.
    if (props.message.isStreaming) return 'Warming up the engine… 🏎️💨';

    // 5. Fallback.
    return 'Summoning the demon… 😈🔥';

});

// ── Waiting-for-first-token visibility ───────────────────────────────────────
// The WaitingIndicator must cover the exact window the user described: from
// send-click until the first ACTUAL answer text paints. Streaming "scaffolding"
// produced along the way — <processing>…</processing> blocks, HTML status
// comments, streaming reasoning (thoughts), and tool-call cards — is feedback
// in its own right. But the <processing> tags also land in `content`, so a plain
// `!message.content` check dismissed the indicator while the user still had no
// readable answer, which is exactly the unsettling gap we're fixing.
// True only when there is REAL, user-readable prose to look at — NOT just
// streaming scaffolding (processing blocks, tool/artefact/building tags, HTML
// comments, code fences markers). This keeps the waiting indicator visible
// across the gap between "bytes started arriving" and "something is painted",
// which is exactly the empty interval the user reported. Once genuine prose
// lands, the indicator dismisses (with the short grace delay below).
const hasAnswerContent = computed(() => {
    const raw = String(props.message.content || '');
    if (!raw) return false;

    // Remove every structural block the renderer turns into a card/indicator,
    // not into prose — including *unclosed* tags (mid-stream).
    const stripped = raw
        .replace(/<processing\b[^>]*>[\s\S]*?<\/processing>/gi, '')
        .replace(/<processing\b[^>]*>[\s\S]*$/i, '')          // open, unclosed
        .replace(/<\/?processing\b[^>]*>/gi, '')
        .replace(/<lollms_(?:working|building)\b[^>]*>/gi, '')
        .replace(/<lollms_form\b[^>]*>[\s\S]*?<\/lollms_form>/gi, '')
        .replace(/<lollms_inline\b[^>]*>[\s\S]*?<\/lollms_inline>/gi, '')
        .replace(/<lollms_widget\b[^>]*\/?>/gi, '')
        .replace(/<tool_call\b[^>]*>[\s\S]*?<\/tool_call>/gi, '')
        .replace(/<tool_call\b[^>]*>[\s\S]*$/i, '')           // open, unclosed
        .replace(/<round\b[^>]*>[\s\S]*?<\/round>/gi, '')
        .replace(/```[\s\S]*?```/g, '')                        // fenced code has its own block
        .replace(/<!--[\s\S]*?-->/g, '')
        .replace(/<\/?(?:note|skill|annotate|generate_image|edit_image|schedule_task)\b[^>]*>/gi, '')
        .replace(/\[!\]\(\s*[^)\s]+\s*\)/g, '')                // inline artefact image calls
        .trim();

    return stripped.length > 0;
});

const hasThoughtContent = computed(() => {
    const t = props.message.thoughts || props.message.metadata?.thoughts || props.message.metadata?.reasoning_content;
    return !!(t && String(t).trim());
});

const shouldShowWaitingAnimation = computed(() => {
    if (!props.message.isStreaming) return false;
    if (allImages.value.length > 0) return false;
    if (hasAnswerContent.value) return false;
    if (hasThoughtContent.value) return false;
    return true;
});

// Delay the hide by ~200 ms after content arrives so we do not flash an empty
// region between the indicator unmounting and the first chunk hitting the DOM.
const showWaiting = ref(false);
let _hideWaitingTimer = null;

watch(shouldShowWaitingAnimation, (shouldShow) => {
    if (shouldShow) {
        if (_hideWaitingTimer) { clearTimeout(_hideWaitingTimer); _hideWaitingTimer = null; }
        showWaiting.value = true;
    } else if (showWaiting.value) {
        if (_hideWaitingTimer) clearTimeout(_hideWaitingTimer);
        _hideWaitingTimer = setTimeout(() => {
            showWaiting.value = false;
            _hideWaitingTimer = null;
        }, 200);
    }
}, { immediate: true });

onUnmounted(() => {
    if (_hideWaitingTimer) { clearTimeout(_hideWaitingTimer); _hideWaitingTimer = null; }
});

const lastEventSummary = computed(() => {
    if (!hasEvents.value) return '';

    // Filter for descriptive events that signify progress to a user
    const displayEvents = props.message.events.filter(e => {
        const type = e.type?.toLowerCase();
        const content = String(e.content || '');
        // Ignore technical plumbing and empty steps
        return type !== 'new_message_id' && 
               !content.includes('0 personality tool') &&
               content.trim().length > 0;
    });

    if (displayEvents.length === 0) {
        return props.message.isStreaming ? 'Generating response...' : 'Task completed';
    }

    const lastEvent = displayEvents[displayEvents.length - 1];
    
    // Prioritize specific 'content' (like "Searching Arxiv...") over the event type label
    if (typeof lastEvent.content === 'string' && lastEvent.content.length > 2) {
        // Suppress UUIDs in the summary bar
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        if (!uuidRegex.test(lastEvent.content)) {
            return lastEvent.content.substring(0, 50) + (lastEvent.content.length > 50 ? '...' : '');
        }
    }

    // Fallback to stylized event type
    return lastEvent.type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
});
const eventIconMap = {
  'thought': IconThinking,
  'tool_call': IconWrenchScrewdriver,
  'tool_output': IconCheckCircle,
  'observation': IconObservation,
  'info': IconInfo,
  'exception': IconError,
  'error': IconError,
  'warning': IconInfo, // Added warning
  'scratchpad': IconScratchpad,
  'default': IconEventDefault,
  'step_start': IconCog,
  'step_end': IconStepEnd,
  'code_exec': IconCode, // Added code execution
  'search': IconMagnifyingGlass, // Added search event
};

const groupedEvents = computed(() => {
    if (!hasEvents.value) return [];
    const result =[];
    const stack =[];

    // EXCLUDE: Technical UI-management events that are already visualized by inline components or sidebars.
    const REDUNDANT_EVENT_TYPES = [
        'sources', 
        'ui_update', 
        'new_message_id',
        'processing_open',
        'processing_status',
        'processing_close',
        'artefact_done',
        'note_done',
        'skill_done',
        'widget_done',
        'artefact_update_done'
    ];

    const filteredEvents = props.message.events.filter(event => 
        !REDUNDANT_EVENT_TYPES.includes(event.type)
    );
    
    for (let i = 0; i < filteredEvents.length; i++) {
        const event = filteredEvents[i];
        const lowerType = event.type?.toLowerCase() || '';
        const stableId = event.id || `${event.type}-${i}`;
        
        if (lowerType.includes('step_start')) {
            const newGroup = { 
                id: `group-${stableId}`,
                type: 'step_group', 
                startEvent: event, 
                children:[], 
                endEvent: null, 
                isInitiallyOpen: true // Steps usually contain important context
            };
            if (stack.length > 0) stack[stack.length - 1].children.push(newGroup);
            else result.push(newGroup);
            stack.push(newGroup);
        } else if (lowerType.includes('step_end')) {
            if (stack.length > 0) {
                const currentGroup = stack.pop();
                currentGroup.endEvent = event;
            } else { 
                event._stableId = stableId;
                result.push(event); 
            }
        } else {
            event._stableId = stableId;
            if (stack.length > 0) stack[stack.length - 1].children.push(event);
            else result.push(event);
        }
    }
    return result;
});

const branchInfo = computed(() => {
    const hasMultipleBranches = props.message.branches && props.message.branches.length > 1;
    if (!hasMultipleBranches) return null;
    
    let activeBranchIndex = -1;
    if (props.message.sender_type === 'user') {
        const currentMessages = discussionsStore.activeMessages;
        const currentMessageIndex = currentMessages.findIndex(m => m.id === props.message.id);
        const nextMessage = currentMessages[currentMessageIndex + 1];
        if (nextMessage && nextMessage.parent_message_id === props.message.id) {
            activeBranchIndex = props.message.branches.findIndex(id => id === nextMessage.id);
        }
    } else {
        // For assistant messages, we find our own message id in the sibling list
        activeBranchIndex = props.message.branches.findIndex(id => id === props.message.id);
    }
    
    if (activeBranchIndex === -1) activeBranchIndex = 0;
    return { 
        isBranchPoint: true, 
        current: activeBranchIndex + 1, 
        total: props.message.branches.length, 
        branchIds: props.message.branches, 
        currentIndex: activeBranchIndex 
    };
});

function navigateBranch(direction) {
    if (!branchInfo.value) return;
    const { branchIds, currentIndex } = branchInfo.value;
    const newIndex = (currentIndex + direction + branchIds.length) % branchIds.length;
    discussionsStore.switchBranch(branchIds[newIndex]);
}

const editorExtensions = computed(() => {
    const extensions = [EditorView.lineWrapping, keymap.of([{ key: "Mod-Enter", run: () => { handleSaveEdit(); return true; } }, { key: "Escape", run: () => { handleCancelEdit(); return true; } }])];
    if (uiStore.currentTheme === 'dark' || isCurrentUser.value) extensions.push(oneDark);
    return extensions;
});

function toggleEdit() {
    isEditing.value = !isEditing.value;
    if (isEditing.value) {
        editedContent.value = props.message.content;
        editedImages.value = (props.message.image_references || []).map(url => ({ url, isNew: false, file: null }));
        newImageFiles.value = [];
        isFormattingMenuOpen.value = false;
    }
}

async function handleSaveEdit() {
    try {
        if (isNewManualMessage.value) {
            await discussionsStore.saveManualMessage({ tempId: props.message.id, content: editedContent.value });
            // Manual message logic handles its own closure or transition
        } else {
            const keptImagesB64 = editedImages.value.filter(img => !img.isNew).map(img => img.url);

            // Wait for store to finish successfully
            await discussionsStore.saveMessageChanges({ 
                messageId: props.message.id, 
                newContent: editedContent.value, 
                keptImagesB64: keptImagesB64, 
                newImageFiles: newImageFiles.value 
            });

            // Only close UI if no error was thrown
            isEditing.value = false;
        }
    } catch (e) {
        // UI stays in edit mode if save fails
        console.error("Edit UI handled error:", e);
    }
}

function removeEditedImage(index) {
    const removed = editedImages.value.splice(index, 1);
    if (removed.isNew) {
        const fileIndex = newImageFiles.value.findIndex(f => f === removed.file);
        if (fileIndex > -1) newImageFiles.value.splice(index, 1);
    }
}

function triggerEditImageUpload() { editImageInput.value.click(); }
function handleEditImageSelected(event) {
    const files = Array.from(event.target.files);
    for (const file of files) {
        const localUrl = URL.createObjectURL(file);
        editedImages.value.push({ url: localUrl, isNew: true, file: file });
        newImageFiles.value.push(file);
    }
    event.target.value = '';
}
function handleCancelEdit() {
    if (isNewManualMessage.value) {
        const index = discussionsStore.activeMessages.findIndex(m => m.id === props.message.id);
        if (index !== -1) discussionsStore.activeMessages.splice(index, 1);
    } else {
        isEditing.value = false;
    }
}
function handleEditorReady(payload) { codeMirrorView.value = payload.view; }
function copyContent() { uiStore.copyToClipboard(props.message.content); }
async function handleDelete() { const confirmed = await uiStore.showConfirmation({ title: 'Delete Message', message: 'This will delete the message and its entire branch.', confirmText: 'Delete' }); if (confirmed.confirmed) discussionsStore.deleteMessage({ messageId: props.message.id}); }
function handleGrade(change) { discussionsStore.gradeMessage({ messageId: props.message.id, change }); }
function handleExportCode() { discussionsStore.exportMessageCodeToZip({ content: props.message.content, title: discussionsStore.activeDiscussion?.title || 'discussion' }); }
function handleBuildNewDiscussion(event) { event.stopPropagation(); discussionsStore.createDiscussionFromMessage({ discussionId: discussionsStore.currentDiscussionId, messageId: props.message.id }); }

function getFavicon(url) {
    if (!url) return null;
    try {
        const domain = new URL(url).hostname;
        return `https://www.google.com/s2/favicons?sz=64&domain=${domain}`;
    } catch (e) {
        return null;
    }
}

function handleBranchOrRegenerate() {
    discussionsStore.initiateBranch(props.message);
}

async function handleSaveAndSend() {
    if (isNewManualMessage.value) return;
    
    try {
        const keptImagesB64 = editedImages.value.filter(img => !img.isNew).map(img => img.url);
        
        // Save the message first
        await discussionsStore.saveMessageChanges({ 
            messageId: props.message.id, 
            newContent: editedContent.value, 
            keptImagesB64: keptImagesB64, 
            newImageFiles: newImageFiles.value 
        });
        
        // Close edit mode after successful save
        isEditing.value = false;
        
        // Wait a tick for state to settle, then branch with the updated message
        await nextTick();
        
        // Trigger branch generation - this treats the edited message as new input
        const savedMessage = discussionsStore.activeMessages.find(m => m.id === props.message.id);
        if (savedMessage) {
            discussionsStore.initiateBranch(savedMessage);
        }
    } catch (e) {
        console.error("Save & Send failed:", e);
        // Stay in edit mode on error
    }
}

// NEW: Function to handle regeneration requests from the renderer tags
function handleTagRegeneration(part) {
    if (areActionsDisabled.value) return;
    
    discussionsStore.triggerTagGeneration({
        messageId: props.message.id,
        tagContent: part.prompt,
        tagType: part.mode, 
        rawTag: part.raw
    });
}

function showSourceDetails(source) { 
    const data = {
        title: source.title || source.name || 'Source Details',
        content: source.content || source.chunk_text || source.text || source.full_text || source.body || source.chunk_content || source.snippet || source.text_snippet || source.preview || source.passage || source.excerpt || source.body_text || '',
        source: source.source || source.url || '',
        score: source.relevance_score || source.score || 0,
        metadata: source.metadata || {}
    };
    uiStore.openModal('sourceViewer', data); 
}

function handleImportSource(source) {
    discussionsStore.importSourceToArtefacts(source);
}

function openAllSourcesSearch() { uiStore.openModal('allSourcesSearch', { sources: props.message.sources }); }
function getSimilarityColor(score) { if (score === undefined || score === null) return 'bg-gray-400 dark:bg-gray-600'; if (score >= 80) return 'bg-green-500'; if (score >= 50) return 'bg-yellow-500'; return 'bg-red-500'; }

</script>
<template>
    <div v-if="isSystem" class="w-full flex justify-center my-2" :data-message-id="message.id">
        <div class="system-bubble" v-html="parsedMarkdown(message.content)"></div>
    </div>
    <div v-else class="message-row group" :class="{ 'is-ai': isAi || isOtherUser, 'dark-mode': uiStore.currentTheme === 'dark' }" :style="{
  backgroundColor: isAi || isOtherUser ? 'var(--brand-bg-card)' : 'var(--brand-primary-light, #3b82f620)',
  borderTop: '1px solid var(--brand-border-muted)'
}">
        <div class="message-content-container">
            <!-- Avatar -->
            <div class="shrink-0 pt-1">
                <UserAvatar :icon="isCurrentUser ? user.icon : (isAi ? senderPersonalityIcon : otherUserIcon)" :username="senderName" size-class="h-8 w-8" />
            </div>

            <!-- Main Content -->
            <div class="flex-1 min-w-0">
                <div class="mb-4 flex items-center justify-between">
                    <div class="flex items-center flex-wrap gap-x-3 gap-y-1">
                        <span class="font-bold text-sm text-primary">{{ senderName }}</span>
                        
                        <!-- Editorial Metadata Breadcrumbs -->
                        <div v-if="isAi && message.model_name" class="flex items-center gap-2">
                            <span class="modal-tag !mb-0 opacity-60">{{ message.model_name }}</span>
                            
                            <!-- Human-friendly activity / performance chip.
                                 While the response is still streaming we show the
                                 current activity (e.g. "Streaming…", "Executing a
                                 tool") instead of a raw "ttft: 8021ms" code that
                                 reads like an error. Once complete we surface a
                                 softly-worded latency + throughput summary. -->
                            <span
                                v-if="message.isStreaming"
                                class="activity-chip"
                                title="What the model is doing right now"
                            >
                                <span class="activity-pulse"></span>
                                {{ isWaitingDetail }}
                            </span>
                            <template v-else-if="message.metadata && (message.metadata.ttft !== undefined || message.metadata.tps !== undefined)">
                                <span class="text-[9px] font-mono text-gray-400 italic">
                                    <span v-if="formatTtft(message.metadata.ttft)">First token in {{ formatTtft(message.metadata.ttft) }}</span>
                                    <span v-if="formatTtft(message.metadata.ttft) && message.metadata.tps" class="mx-1">·</span>
                                    <span v-if="message.metadata.tps">{{ message.metadata.tps.toFixed(1) }} tok/s</span>
                                </span>
                            </template>
                        </div>
                    </div>

                    <!-- Editorial Branch Navigation (Top Right) -->
                    <div v-if="branchInfo" class="flex items-center gap-2">
                        <span class="text-[9px] font-black uppercase tracking-widest text-secondary">{{ branchInfo.current }} / {{ branchInfo.total }} versions</span>
                        <div class="flex items-center surface-1 rounded-lg p-0.5">
                            <button @click="navigateBranch(-1)" class="p-1 hover:text-blue-500 transition-colors"><IconChevronRight class="w-3 h-3 rotate-180" /></button>
                            <button @click="navigateBranch(1)" class="p-1 hover:text-blue-500 transition-colors"><IconChevronRight class="w-3 h-3" /></button>
                        </div>
                    </div>
                </div>
                
                <!-- Content Wrapper -->
                <div class="message-content-wrapper">
                    <div v-if="!isEditing">
                        <!-- ── Always-visible failure summary ────────────────────────
                             Tool runs and artefact builds fail deep inside collapsed
                             processing blocks. This surfaces every error event in one
                             clear banner so the user immediately sees WHAT failed and
                             WHY, without opening any log dump. -->
                        <div v-if="failureEvents.length > 0" class="failure-summary">
                            <div class="failure-summary-head">
                                <IconError class="w-4 h-4 shrink-0" />
                                <span>
                                    {{ failureEvents.length }} error{{ failureEvents.length > 1 ? 's' : '' }} during execution
                                </span>
                            </div>
                            <ul class="failure-list">
                                <li v-for="(f, i) in failureEvents" :key="i" class="failure-item">
                                    <span class="failure-tag">{{ f.label }}</span>
                                    <span class="failure-msg">{{ f.message }}</span>
                                </li>
                            </ul>
                        </div>

                        <!-- Text Content -->
                        <MessageContentRenderer
                            :content="message.content"
                            :discussion-id="discussionsStore.currentDiscussionId"
                            :thoughts="message.thoughts || message.metadata?.thoughts || message.metadata?.reasoning_content"
                            :sources="message.sources"
                            :forms="message.forms"
                            :events="message.events"
                            :inline-widgets="message.inline_widgets"
                            :is-streaming="message.isStreaming"
                            :is-user="isCurrentUser"
                            :has-images="allImages.length > 0"
                            :last-user-image="lastUserImage"
                            :message-id="message.id"
                            :metadata="message.metadata"
                            @regenerate="handleTagRegeneration"
                            @citation-click="handleCitationClick"
                        />

                        <!-- ── Execution Timeline ───────────────────────────────
                             Redesigned so tool runs and artefact builds are legible:
                             each event is a colour-coded, icon-labelled card, errors
                             surface in a red banner with the real message, and noisy
                             log fragments are cleaned / summarised. -->
                        <div v-if="hasEvents" class="mt-8">
                            <button
                                @click="isEventsCollapsed = !isEventsCollapsed"
                                class="utility-link group/link mb-4"
                            >
                                <IconCog class="w-3 h-3" :class="{'animate-spin': message.isStreaming}" />
                                <span>Execution Timeline</span>
                                <span v-if="timelineFailureCount > 0" class="chip-failure">{{ timelineFailureCount }} error{{ timelineFailureCount > 1 ? 's' : '' }}</span>
                                <IconChevronRight class="w-2.5 h-2.5 transition-transform" :class="{'rotate-90': !isEventsCollapsed}" />
                            </button>

                            <Transition
                                enter-active-class="transition-all duration-500 ease-out"
                                enter-from-class="max-h-0 opacity-0 -translate-y-2"
                                enter-to-class="max-h-[2400px] opacity-100 translate-y-0"
                            >
                                <div v-if="!isEventsCollapsed" class="ml-1.5 pl-4 border-l border-secondary space-y-3">
                                    <div
                                        v-for="(event, idx) in uniqueEvents"
                                        :key="idx"
                                        class="timeline-card"
                                        :class="[
                                            event.norm.artefactOp ? `op-${event.norm.artefactOp.kind}` : `tone-${event.norm.status}`,
                                            event.norm.status === 'error' ? 'is-error' : '',
                                            event.norm.status === 'warning' ? 'is-warning' : ''
                                        ]"
                                    >
                                        <!-- Timeline Dot -->
                                        <div
                                            class="timeline-dot"
                                            :class="[
                                                `dot-${event.norm.meta.tone}`,
                                                idx === uniqueEvents.length - 1 && message.isStreaming ? 'animate-pulse' : ''
                                            ]"
                                        ></div>

                                        <!-- ── Card header: status icon + label + tool name + timing ── -->
                                        <div class="timeline-card-head">
                                            <div class="timeline-card-title">
                                                <component :is="event.norm.meta.icon" class="w-3.5 h-3.5 shrink-0" />
                                                <span class="timeline-card-label">{{ event.norm.meta.label }}</span>
                                                <!-- Artefact operation badge: visually distinguishes a
                                                     full rewrite (whole-file) from a surgical patch. -->
                                                <span
                                                    v-if="event.norm.artefactOp"
                                                    class="timeline-card-op"
                                                    :class="`op-badge-${event.norm.artefactOp.kind}`"
                                                >{{ event.norm.artefactOp.badge }}</span>
                                                <span
                                                    v-if="event.norm.toolName"
                                                    class="timeline-card-tool"
                                                >{{ event.norm.toolName }}</span>
                                                <span
                                                    class="timeline-card-status"
                                                    :class="`status-${event.norm.status}`"
                                                >{{ event.norm.status === 'error' ? 'FAILED' : (event.norm.status === 'warning' ? 'WARNING' : 'OK') }}</span>
                                            </div>
                                            <span v-if="event.norm.timing" class="timeline-card-timing">
                                                <IconClock class="w-3 h-3" />
                                                {{ event.norm.timing }}
                                            </span>
                                        </div>

                                        <!-- ── Error: the real, prominent failure message ── -->
                                        <div v-if="event.norm.status === 'error' && event.norm.error" class="timeline-card-error">
                                            <IconError class="w-3.5 h-3.5 shrink-0 mt-0.5" />
                                            <pre class="timeline-card-error-text">{{ event.norm.error }}</pre>
                                        </div>

                                        <!-- ── Arguments ── -->
                                        <div v-if="event.norm.args" class="timeline-card-field">
                                            <span class="timeline-field-label">Arguments</span>
                                            <pre class="timeline-field-value">{{ event.norm.args }}</pre>
                                        </div>

                                        <!-- ── Result (only when not an error) ── -->
                                        <div v-if="event.norm.status !== 'error' && event.norm.result && !isNoiseLine(event.norm.result)" class="timeline-card-field">
                                            <span class="timeline-field-label">Result</span>
                                            <pre class="timeline-field-value result">{{ event.norm.result }}</pre>
                                        </div>

                                        <!-- ── Raw payload: collapsible, for full context ── -->
                                        <details class="timeline-card-raw" :open="event.norm.status === 'error' && event.multilineRaw">
                                            <summary class="timeline-raw-summary">
                                                <IconChevronRight class="w-2.5 h-2.5 transition-transform" />
                                                <span>Raw payload · {{ event.contentLineCount }} line{{ event.contentLineCount === 1 ? '' : 's' }}</span>
                                            </summary>
                                            <pre class="timeline-raw-pre">{{ event.norm.raw }}</pre>
                                        </details>
                                    </div>

                                    <div v-if="message.isStreaming" class="flex items-center gap-2 text-[10px] text-accent/60 font-mono italic animate-pulse pl-1">
                                        <span class="h-1.5 w-1.5 rounded-full bg-current"></span>
                                        Working…
                                    </div>
                                </div>
                            </Transition>
                        </div>

                        <!-- Centralized Image Zone with Gallery Underneath -->
                        <!-- MOVED BELOW TEXT CONTENT -->
                        <div v-if="imageGroups.length > 0" class="my-4 space-y-6">
                            
                            <!-- Iterate over Groups -->
                            <div v-for="group in imageGroups" :key="group.id" class="image-group-container">
                                <!-- Group Header (for generated series or uploaded packs) -->
                                <div class="text-xs font-semibold text-secondary mb-1 flex justify-between">
                                    <span class="truncate" :title="group.title">{{ group.title }}</span>
                                    <span class="text-[10px] bg-gray-200 dark:bg-gray-700 px-1.5 rounded">{{ group.images.length }} version(s)</span>
                                </div>
                                
                                <!-- Export Actions (NEW) -->
                                <div class="flex gap-2 my-1" v-if="group.type === 'slideshow' || group.type === 'slide_item'">
                                     <button @click="handleExport('pptx')" class="btn btn-secondary btn-xs flex items-center gap-1">
                                        <IconArrowDownTray class="w-3 h-3"/> Download PPTX
                                     </button>
                                     <button @click="handleExport('pdf')" class="btn btn-secondary btn-xs flex items-center gap-1">
                                        <IconArrowDownTray class="w-3 h-3"/> Download PDF
                                     </button>
                                     <button @click.stop="openSlideshow(group)" class="btn btn-primary btn-xs flex items-center gap-1">
                                        <IconPlayCircle class="w-3 h-3"/> Play Slideshow
                                     </button>
                                </div>

                                <!-- Main Image Display for this Group -->
                                <div v-if="group.images.length > 0" 
                                     class="main-image-viewport relative aspect-video sm:aspect-square max-h-[500px] w-full rounded-[2rem] overflow-hidden border shadow-xl group/viewport transition-all duration-300"
                                     style="background-color: var(--input-bg); border-color: var(--border-muted);"
                                     :class="!isImageActive(selectedViewIndices[group.id] ?? group.indices[0]) ? 'border-red-500' : ''"
                                >
                                    
                                    <!-- Spinner Overlay for Regenerating -->
                                    <div v-if="isRegenerating(group.id)" class="absolute inset-0 z-20 backdrop-blur-md flex flex-col items-center justify-center transition-all" style="background-color: color-mix(in srgb, var(--bg-app) 60%, transparent);">
                                        <IconAnimateSpin class="w-10 h-10 animate-spin mb-2" style="color: var(--primary);"/>
                                        <span class="text-sm font-bold" style="color: var(--text-main);">Generating variation...</span>
                                    </div>

                                    <!-- Handle click on image -->
                                    <div @click.stop="handleImageClick(group, selectedViewIndices[group.id] ?? group.indices[0])" class="w-full h-full cursor-pointer">
                                        <AuthenticatedImage 
                                            :src="allImages[selectedViewIndices[group.id] ?? group.indices[0]]" 
                                            class="w-full h-full object-contain"
                                        />
                                    </div>

                                    <!-- Viewport Controls Overlay -->
                                    <div class="absolute inset-0 bg-black/40 opacity-0 group-hover/viewport:opacity-100 transition-opacity flex items-center justify-center gap-3 z-10 pointer-events-none">
                                        <!-- Need pointer-events-auto on buttons to ensure they are clickable over the container -->
                                        <button @click.stop="handleImageClick(group, selectedViewIndices[group.id] ?? group.indices[0])" class="pointer-events-auto p-3 bg-white/20 hover:bg-white/40 text-white rounded-full backdrop-blur-md shadow-xl transition-all active:scale-90" title="Full Screen">
                                            <IconMaximize class="w-6 h-6" />
                                        </button>
                                        
                                        <!-- Visibility Toggle -->
                                        <button @click.stop="toggleImage(selectedViewIndices[group.id] ?? group.indices[0])" 
                                                :disabled="areActionsDisabled"
                                                class="pointer-events-auto p-3 bg-white/20 hover:bg-white/40 text-white rounded-full backdrop-blur-md shadow-xl transition-all active:scale-90 disabled:opacity-50 disabled:cursor-not-allowed" 
                                                :title="isImageActive(selectedViewIndices[group.id] ?? group.indices[0]) ? 'Deactivate (Hide from LLM)' : 'Activate (Show to LLM)'">
                                            <IconEye v-if="isImageActive(selectedViewIndices[group.id] ?? group.indices[0])" class="w-6 h-6" />
                                            <IconEyeOff v-else class="w-6 h-6 text-red-300" />
                                        </button>
                                        
                                        <!-- Transform into Artefact -->
                                        <button @click.stop="handleTransformImageToArtefact(group, selectedViewIndices[group.id] ?? group.indices[0])" 
                                                :disabled="isTransformingImage(`${group.id}-${selectedViewIndices[group.id] ?? group.indices[0]}`)"
                                                class="pointer-events-auto p-3 bg-white/20 hover:bg-white/40 text-white rounded-full backdrop-blur-md shadow-xl transition-all active:scale-90 disabled:opacity-50 disabled:cursor-not-allowed" 
                                                title="Transform into artefact">
                                            <IconAnimateSpin v-if="isTransformingImage(`${group.id}-${selectedViewIndices[group.id] ?? group.indices[0]}`)" class="w-6 h-6 animate-spin" />
                                            <IconPhoto v-else class="w-6 h-6" />
                                        </button>
                                    </div>

                                    <!-- Visibility Status Badge (Discrete) -->
                                    <div v-if="!isImageActive(selectedViewIndices[group.id] ?? group.indices[0])" class="absolute top-3 right-3 z-10 pointer-events-none">
                                         <div class="px-2 py-1 bg-red-500/90 text-white rounded flex items-center gap-1.5 shadow-sm backdrop-blur-md">
                                             <IconEyeOff class="w-3 h-3" />
                                             <span class="font-bold uppercase tracking-widest text-[9px]">Inactive</span>
                                         </div>
                                    </div>
                                </div>

                                <!-- Gallery Thumbnails -->
                                <div v-if="group.images.length > 1" class="gallery-thumb-row flex items-center gap-3 overflow-x-auto py-4 custom-scrollbar">
                                    <div v-for="(imgSrc, idx) in group.images" 
                                         :key="`${group.id}-thumb-${idx}`"
                                         class="relative w-16 h-16 sm:w-24 sm:h-24 shrink-0 rounded-2xl overflow-hidden border-2 transition-all duration-300 cursor-pointer shadow-sm"
                                         :class="[
                                            (selectedViewIndices[group.id] ?? group.indices[0]) === group.indices[idx] ? 'border-blue-500 scale-105 shadow-md' : 'border-transparent hover:border-gray-300 dark:hover:border-gray-600',
                                            !isImageActive(group.indices[idx]) ? 'border-red-500' : ''
                                         ]"
                                         @click.stop="selectView(group.id, group.indices[idx])"
                                    >
                                        <AuthenticatedImage :src="allImages[group.indices[idx]]" class="w-full h-full object-cover" />
                                        
                                        <!-- Mini Status Indicators -->
                                        <div v-if="!isImageActive(group.indices[idx])" class="absolute top-0 right-0 p-1 bg-red-500/90 rounded-bl-lg">
                                            <IconEyeOff class="w-3 h-3 text-white" />
                                        </div>
                                        <div v-else-if="isImageActive(group.indices[idx])" class="absolute top-0.5 right-0.5 bg-green-500 text-white rounded-full p-0.5 shadow-sm">
                                            <IconCheckCircle class="w-3 h-3" />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Waiting-for-first-token indicator: a green→amber→red
                             progress bar + rotating status. Driven by `showWaiting`
                             (not `!content`) so `<processing>`/thought scaffolding
                             does not prematurely dismiss it while the user still
                             has no readable answer, and the un-mount is delayed
                             ~200 ms so the first chunk paints before the animation
                             disappears (no flash). -->
                        <div
                            v-if="showWaiting"
                            class="my-2"
                        >
                            <WaitingIndicator
                                :detail="isWaitingDetail"
                            />
                        </div>
                    </div>
                    <!-- Editing Mode -->
                    <div v-else class="w-full">
                        <input type="file" ref="editImageInput" @change="handleEditImageSelected" multiple accept="image/*" class="hidden">
                        <div v-if="editedImages.length > 0" class="mb-2 p-2 border-dashed rounded-md" style="border-color: var(--border-strong); background-color: var(--bg-card);">
                            <div class="flex flex-wrap gap-2">
                                <div v-for="(image, index) in editedImages" :key="image.url" class="relative w-16 h-16">
                                    <img :src="image.url" class="w-full h-full object-cover rounded-md" alt="Image preview" />
                                    <button @click="removeEditedImage(index)" type="button" class="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold leading-none">×</button>
                                </div>
                            </div>
                        </div>
                        <CodeMirrorEditor
                            v-model="editedContent"
                            placeholder="Enter your message..."
                            :autofocus="true"
                            :extensions="editorExtensions"
                            editorClass="max-h-[500px]"
                            @ready="handleEditorReady"
                        />
                        <div class="flex justify-between items-center mt-2">
                             <button v-if="currentModelVisionSupport" @click="triggerEditImageUpload" class="btn btn-secondary !p-2" title="Add Images">
                                <IconPhoto class="w-5 h-5" />
                            </button>
                            <div class="flex justify-end space-x-2">
                                <button @click="handleCancelEdit" class="btn btn-secondary !py-1 !px-3">Cancel</button>
                                <button v-if="isCurrentUser && !isNewManualMessage" @click="handleSaveAndSend" :disabled="areActionsDisabled" class="btn btn-primary !py-1 !px-3 flex items-center gap-1.5" title="Save changes and create a new branch with regenerated response">
                                    <IconGitBranch class="w-3.5 h-3.5" />
                                    <span>Save & Send</span>
                                </button>
                                <button @click="handleSaveEdit" class="btn btn-primary !py-1 !px-3">Save</button>
                            </div>
                        </div>
                    </div>
                </div>

                 <!-- TTS Player (Background Task Driven) -->
                 <div v-if="isAi && isTtsActive" class="mt-4 animate-in fade-in slide-in-from-top-1">
                    <!-- Task Running State -->
                    <div v-if="message.isGeneratingAudio && !message.metadata?.audio_url" class="flex items-center gap-3 p-3 card">
                        <IconAnimateSpin class="w-4 h-4 text-accent animate-spin" />
                        <span class="text-xs font-bold text-secondary">Synthesizing Voice...</span>
                    </div>

                    <!-- Completed State: Player -->
                    <div v-else-if="message.metadata?.audio_url" class="flex flex-col gap-2">
                        <div class="flex items-center gap-2 mb-1">
                            <IconSpeakerWave class="w-3 h-3 text-blue-500" />
                            <span class="text-[9px] font-black uppercase tracking-widest text-gray-400">Audio Response</span>
                        </div>
                        <audio
                            ref="audioPlayerRef"
                            :src="message.metadata.audio_url"
                            controls
                            class="w-full h-10 rounded-xl"
                            @play="discussionsStore.playAudio(message.id, $event.target)"
                            @pause="discussionsStore.onAudioPausedOrEnded(message.id)"
                            @ended="discussionsStore.onAudioPausedOrEnded(message.id)"
                        ></audio>
                    </div>
                </div>

                <!-- Unified Editorial Sources Grid -->
                <div v-if="hasSources" class="mt-8 border-t border-primary pt-8 animate-in fade-in slide-in-from-bottom-2">
                    <div class="flex items-center justify-between mb-6">
                        <button @click="isSourcesVisible = !isSourcesVisible" class="utility-link">
                            <IconGather class="w-4 h-4" />
                            <span>Sources & References ({{ sortedSources.length }})</span>
                            <IconChevronRight class="w-2.5 h-2.5 transition-transform" :class="{'rotate-90': isSourcesVisible}" />
                        </button>
                        <button @click="openAllSourcesSearch" class="modal-close-btn" title="Filter sources">
                            <IconMagnifyingGlass class="w-3.5 h-3.5" />
                        </button>
                    </div>

                    <div v-if="isSourcesVisible" class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div v-for="(source, index) in sortedSources" :key="index" 
                                :ref="(el) => { if (el) sourceRefs[index] = el; }"
                                class="flex flex-col gap-2 group/source transition-all duration-300 rounded-2xl">

                            <div @click="showSourceDetails(source)" 
                                    class="p-4 card cursor-pointer transition-all relative overflow-hidden">

                                <div class="flex items-start justify-between gap-3 mb-2 relative z-10" :style="{ color: 'var(--brand-text-main)' }">
                                    <div class="flex items-center gap-2.5 min-w-0">
                                        <!-- Favicon for Web / Index for RAG -->
                                        <img v-if="isUrl(source.source)" :src="getFavicon(source.source)" class="w-6 h-6 rounded-lg surface-0 p-0.5 shadow-sm shrink-0 border border-primary" alt="" />
                                        <div v-else class="shrink-0 w-6 h-6 flex items-center justify-center surface-2 text-accent rounded-lg text-[10px] font-black">
                                            {{ source.index || index + 1 }}
                                        </div>

                                        <span class="font-bold text-sm truncate text-primary group-hover/source:text-accent transition-colors">{{ source.title || 'Untitled Source' }}</span>
                                    </div>

                                    <div v-if="source.score" class="shrink-0 chip-success">
                                        {{ Math.round(source.score > 1 ? source.score : source.score * 100) }}%
                                    </div>
                                </div>

                                <!-- Hint / Snippet Preview -->
                                <p v-if="source.content" class="mt-2 text-[11px] text-secondary line-clamp-2 leading-relaxed italic relative z-10">
                                    "{{ source.content }}"
                                </p>

                                <div class="mt-3 flex items-center justify-between relative z-10">
                                    <span class="text-[8px] font-mono text-secondary truncate max-w-[70%] opacity-60">{{ source.source }}</span>
                                    <div class="flex items-center gap-1">
                                        <button v-if="isUrl(source.source)" @click.stop="togglePreview(index)" class="p-1 text-secondary hover:text-accent transition-colors" title="Instant Preview">
                                            <IconEye class="w-3.5 h-3.5" />
                                        </button>
                                        <span class="text-[9px] font-black text-accent uppercase tracking-widest opacity-0 group-hover/source:opacity-100 transform translate-x-2 group-hover/source:translate-x-0 transition-all">Details &rarr;</span>
                                    </div>
                                </div>

                                <!-- Decorative subtle bg blur -->
                                <div class="absolute -right-4 -bottom-4 w-20 h-20 bg-blue-500/5 rounded-full blur-2xl group-hover/source:bg-blue-500/10 transition-colors"></div>
                            </div>

                            <!-- Integrated Preview iframe -->
                            <Transition 
                                enter-active-class="transition-all duration-500 ease-out"
                                enter-from-class="opacity-0 scale-95 -translate-y-4"
                                enter-to-class="opacity-100 scale-100 translate-y-0"
                                leave-active-class="transition-all duration-300 ease-in"
                                leave-from-class="opacity-100 scale-100"
                                leave-to-class="opacity-0 scale-95"
                            >
                                <div v-if="previewMap[index]" class="w-full h-96 rounded-2xl border-2 border-blue-500/30 bg-white dark:bg-black overflow-hidden relative shadow-2xl z-20">
                                    <iframe :src="source.source" class="w-full h-full" sandbox="allow-scripts allow-same-origin"></iframe>
                                    <div class="absolute top-3 right-3 flex gap-2">
                                        <a :href="source.source" target="_blank" class="p-2 bg-gray-900/80 text-white rounded-full hover:bg-black transition-colors shadow-lg">
                                            <IconGlobeAlt class="w-4 h-4" />
                                        </a>
                                        <button @click="togglePreview(index)" class="p-2 bg-red-600 text-white rounded-full hover:bg-red-700 transition-colors shadow-lg">
                                            <IconXMark class="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>
                            </Transition>
                        </div>
                    </div>
                </div>

                
                <!-- Editorial Footer Interaction Bar -->
                <div class="message-footer mt-10">
                    <div class="grow flex items-center flex-wrap gap-4">
                        <div v-if="isAi && message.token_count" class="utility-link">
                            <IconToken class="w-3 h-3" />
                            <span>{{ message.token_count }} Tokens</span>
                        </div>
                        
                        <!-- Discreet TTS Trigger -->
                        <button v-if="isAi && isTtsActive" @click="handleSpeak" class="modal-close-btn" :class="{'animate-pulse text-blue-500': messageTtsState.isLoading}">
                            <IconSpeakerWave class="w-3.5 h-3.5" />
                        </button>
                    </div>
                    <div v-if="!isEditing" class="shrink-0 flex items-center gap-1">
                        <div class="actions flex items-center space-x-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                            <!-- Debug Metadata Button -->
                            <button v-if="isTtsActive && isAi" @click="handleSpeak" :title="messageTtsState.isLoading ? 'Generating...' : 'Speak'" class="action-btn" :disabled="messageTtsState.isLoading">
                                <IconAnimateSpin v-if="messageTtsState.isLoading" class="w-4 h-4 animate-spin" />
                                <IconSpeakerWave v-else class="w-4 h-4" />
                            </button>
                            <DropdownMenu v-if="exportFormats.length > 0" title="Export" icon="ticket" button-class="action-btn" collection="ui">
                                <button v-for="format in exportFormats" :key="format.value" @click="handleExport(format.value)" class="w-full text-left p-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 text-sm">
                                    {{ format.label }}
                                </button>
                            </DropdownMenu>
                            
                            <button v-if="containsCode" :disabled="areActionsDisabled" @click="handleExportCode" title="Export Code" class="action-btn"><IconCode class="w-4 h-4" /></button>
                            <button :disabled="areActionsDisabled" @click="copyContent" title="Copy" class="action-btn"><IconCopy /></button>
                            <button :disabled="areActionsDisabled" @click="toggleEdit" title="Edit" class="action-btn"><IconPencil /></button>
                            <button :disabled="areActionsDisabled" @click="handleBranchOrRegenerate" :title="isCurrentUser ? 'Resend / Branch' : 'Regenerate'" class="action-btn"><IconRefresh /></button>
                            <button :disabled="areActionsDisabled" @click="handleBuildNewDiscussion" title="Build a new discussion from here" class="action-btn"><IconGitBranch class="w-4 h-4" /></button>
                            <button :disabled="areActionsDisabled" @click="handleDelete" title="Delete" class="action-btn text-red-500 hover:bg-red-200 dark:hover:bg-red-700"><IconTrash /></button>
                        </div>
                        <div v-if="isAi" class="message-rating">
                            <button :disabled="areActionsDisabled" @click="handleGrade(1)" title="Good response" class="rating-btn upvote" :class="{ 'active': message.user_grade > 0 }"><IconThumbUp /></button>
                            <span class="rating-score">{{ message.user_grade || 0 }}</span>
                            <button :disabled="areActionsDisabled" @click="handleGrade(-1)" title="Bad response" class="rating-btn downvote" :class="{ 'active': message.user_grade < 0 }"><IconThumbDown /></button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
<style scoped>
.message-prose {
    max-width: none;
    overflow-wrap: break-word;
    font-family: Georgia, serif;
    font-size: var(--message-font-size, 1.2rem);
    line-height: 1.7;
}

.custom-scrollbar::-webkit-scrollbar { width: 4px; height: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background-color: #e5e7eb; border-radius: 9999px; }
.dark .custom-scrollbar::-webkit-scrollbar-thumb { background-color: #1f2937; }
.btn-icon-sm {
    padding: 0.375rem;
    border-radius: 0.5rem;
    transition-property: background-color;
    transition-duration: 150ms;
    display: flex;
    align-items: center;
    justify-content: center;
}
.btn-icon-sm:hover { background-color: #e5e7eb; }
.dark .btn-icon-sm:hover { background-color: #374151; }
.events-details-container summary::-webkit-details-marker { display: none; }
.step-card {
    box-shadow: 0 1px 3px rgb(0 0 0 / 0.1), 0 1px 2px rgb(0 0 0 / 0.06);
    transition-property: box-shadow;
    transition-duration: 150ms;
}
.step-card:hover { box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1); }

/* ── Live activity chip (replaces raw "ttft: Nms" breadcrumb) ───────────── */
.activity-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 2px 9px;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.02em;
    color: var(--brand-primary, #6366f1);
    background: var(--brand-primary-light, rgba(99, 102, 241, 0.12));
    border: 1px solid rgba(99, 102, 241, 0.25);
    white-space: nowrap;
    max-width: 260px;
    overflow: hidden;
    text-overflow: ellipsis;
}
.activity-pulse {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
    background: currentColor;
    animation: activity-pulse 1.2s ease-in-out infinite;
}
@keyframes activity-pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.35; transform: scale(0.7); }
}

/* ── Always-visible failure summary banner ─────────────────────────────── */
.failure-summary {
    margin: 12px 0;
    border-radius: 12px;
    border: 1px solid #fca5a5;
    background: #fef2f2;
    overflow: hidden;
}
.dark .failure-summary { border-color: rgba(239,68,68,0.4); background: rgba(239,68,68,0.1); }
.failure-summary-head {
    display: flex; align-items: center; gap: 8px;
    padding: 10px 14px;
    font-size: 12.5px; font-weight: 800;
    color: #b91c1c;
    border-bottom: 1px solid #fca5a5;
}
.dark .failure-summary-head { color: #fca5a5; border-bottom-color: rgba(239,68,68,0.4); }
.failure-list { list-style: none; margin: 0; padding: 8px 14px 12px; display: flex; flex-direction: column; gap: 8px; }
.failure-item { display: flex; flex-direction: column; gap: 3px; }
.failure-tag {
    align-self: flex-start;
    padding: 1px 7px; border-radius: 999px;
    font-size: 9px; font-weight: 900; letter-spacing: 0.05em; text-transform: uppercase;
    background: #ef4444; color: #fff;
}
.failure-msg {
    font-family: ui-monospace, 'SF Mono', Consolas, monospace;
    font-size: 11.5px; line-height: 1.55;
    color: #991b1b;
    white-space: pre-wrap;
    word-break: break-word;
}
.dark .failure-msg { color: #fca5a5; }

/* ── Execution Timeline ────────────────────────────────────────────────── */
.chip-failure {
    display: inline-flex; align-items: center;
    padding: 1px 7px; border-radius: 999px;
    font-size: 9px; font-weight: 800; letter-spacing: 0.04em;
    background: #fee2e2; color: #b91c1c;
}
.dark .chip-failure { background: rgba(239,68,68,0.18); color: #fca5a5; }

/* ── Execution Timeline: structured cards ──────────────────────────────── */
.timeline-card {
    position: relative;
    border-radius: 12px;
    padding: 12px 14px 12px 16px;
    border: 1px solid var(--brand-border-muted, #e2e8f0);
    border-left-width: 4px;
    background: var(--brand-bg-card, #fff);
    transition: box-shadow 0.15s ease;
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.timeline-card:hover { box-shadow: 0 2px 8px rgba(15,23,42,0.06); }

.timeline-card.tone-error { border-left-color: #ef4444; background: #fff5f5; border-color: #fecaca; }
.timeline-card.tone-warning { border-left-color: #f59e0b; background: #fffbeb; border-color: #fde68a; }
.timeline-card.tone-tool { border-left-color: #6366f1; }
.timeline-card.tone-artefact { border-left-color: #0ea5e9; }
.timeline-card.tone-step { border-left-color: #10b981; }
.timeline-card.tone-thought { border-left-color: #a855f7; }
.timeline-card.tone-info { border-left-color: #94a3b8; }
.timeline-card.tone-ok { border-left-color: #10b981; }

.dark .timeline-card.tone-error { background: rgba(239,68,68,0.08); border-color: rgba(239,68,68,0.3); }
.dark .timeline-card.tone-warning { background: rgba(245,158,11,0.08); border-color: rgba(245,158,11,0.3); }

/* ── Artefact operation variants: full rewrite vs patch ─────────────────── */
/* Full rewrite: whole file replaced. Violet identity, document styling. */
.timeline-card.op-rewrite {
    border-left-color: #7c3aed;
    background: #f7f4ff;
    border-color: #ddd6fe;
}
.dark .timeline-card.op-rewrite {
    background: rgba(124,58,237,0.10);
    border-color: rgba(124,58,237,0.35);
}
/* Patch: surgical/targeted edit. Amber identity, tool/wrench styling. */
.timeline-card.op-patch {
    border-left-color: #d97706;
    background: #fffaeb;
    border-color: #fde68a;
}
.dark .timeline-card.op-patch {
    background: rgba(217,119,6,0.10);
    border-color: rgba(217,119,6,0.35);
}

/* Status precedence: a failed patch/rewrite must still read as an error.
   Declared AFTER the op tints so background AND left border flip to the
   error/warning colour, while the operation badge still shows REWRITE/PATCH. */
.timeline-card.is-error { background: #fff5f5; border-color: #fecaca; border-left-color: #ef4444; }
.timeline-card.is-warning { background: #fffbeb; border-color: #fde68a; border-left-color: #f59e0b; }
.dark .timeline-card.is-error { background: rgba(239,68,68,0.10); border-color: rgba(239,68,68,0.35); }
.dark .timeline-card.is-warning { background: rgba(245,158,11,0.10); border-color: rgba(245,158,11,0.35); }

/* Operation badge (REWRITE / PATCH) shown in the card header. */
.timeline-card-op {
    font-size: 9px; font-weight: 900; letter-spacing: 0.06em;
    padding: 1px 8px; border-radius: 6px; text-transform: uppercase;
    border: 1px solid transparent;
}
.op-badge-rewrite { background: #ede9fe; color: #6d28d9; border-color: #c4b5fd; }
.op-badge-patch { background: #fef3c7; color: #b45309; border-color: #fcd34d; }
.dark .op-badge-rewrite { background: rgba(124,58,237,0.2); color: #c4b5fd; border-color: rgba(124,58,237,0.5); }
.dark .op-badge-patch { background: rgba(217,119,6,0.2); color: #fcd34d; border-color: rgba(217,119,6,0.5); }

.timeline-dot {
    position: absolute;
    left: -23px; top: 14px;
    width: 10px; height: 10px;
    border-radius: 50%;
    border: 2px solid var(--brand-bg-card, #fff);
    background: #94a3b8;
}
.timeline-dot.dot-error { background: #ef4444; }
.timeline-dot.dot-warning { background: #f59e0b; }
.timeline-dot.dot-tool { background: #6366f1; }
.timeline-dot.dot-artefact { background: #0ea5e9; }
.timeline-dot.dot-artefact-rewrite { background: #7c3aed; }
.timeline-dot.dot-artefact-patch { background: #d97706; }
.timeline-dot.dot-step { background: #10b981; }
.timeline-dot.dot-thought { background: #a855f7; }
.timeline-dot.dot-info { background: #94a3b8; }

/* Card header row */
.timeline-card-head {
    display: flex; align-items: center; justify-content: space-between;
    gap: 10px; flex-wrap: wrap;
}
.timeline-card-title { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; min-width: 0; }
.timeline-card-label {
    font-size: 10px; font-weight: 800; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--brand-text-dim, #64748b);
}
.timeline-card.tone-error .timeline-card-label { color: #b91c1c; }
.timeline-card.tone-warning .timeline-card-label { color: #b45309; }
.timeline-card-tool {
    font-family: ui-monospace, 'SF Mono', Consolas, monospace;
    font-size: 12px; font-weight: 700; color: var(--brand-text-main, #1e293b);
    background: var(--brand-bg-hover, #f1f5f9);
    padding: 1px 8px; border-radius: 6px;
    max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.timeline-card-status {
    font-size: 9px; font-weight: 900; letter-spacing: 0.05em;
    padding: 1px 8px; border-radius: 999px;
}
.timeline-card-status.status-ok { background: #dcfce7; color: #166534; }
.timeline-card-status.status-warning { background: #fef3c7; color: #b45309; }
.timeline-card-status.status-error { background: #ef4444; color: #fff; }
.dark .timeline-card-status.status-ok { background: rgba(16,185,129,0.18); color: #6ee7b7; }

.timeline-card-timing {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 10.5px; font-family: ui-monospace, 'SF Mono', Consolas, monospace;
    color: var(--brand-text-dim, #94a3b8); flex-shrink: 0;
}

/* Prominent error box */
.timeline-card-error {
    display: flex; align-items: flex-start; gap: 8px;
    padding: 10px 12px; border-radius: 9px;
    background: #fee2e2; border: 1px solid #fca5a5; color: #991b1b;
}
.dark .timeline-card-error { background: rgba(239,68,68,0.16); border-color: rgba(239,68,68,0.4); color: #fca5a5; }
.timeline-card-error-text {
    margin: 0; font-size: 12px; line-height: 1.55;
    font-family: ui-monospace, 'SF Mono', Consolas, monospace;
    white-space: pre-wrap; word-break: break-word;
    max-height: 220px; overflow: auto;
}

/* Labelled fields (Arguments / Result) */
.timeline-card-field { display: flex; flex-direction: column; gap: 3px; }
.timeline-field-label {
    font-size: 9px; font-weight: 800; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--brand-text-dim, #94a3b8);
}
.timeline-field-value {
    margin: 0; font-size: 11.5px; line-height: 1.5;
    font-family: ui-monospace, 'SF Mono', Consolas, monospace;
    color: var(--brand-text-main, #334155);
    background: var(--brand-bg-hover, #f8fafc);
    padding: 8px 10px; border-radius: 8px;
    white-space: pre-wrap; word-break: break-word;
    max-height: 260px; overflow: auto;
}
.timeline-field-value.result { border: 1px solid var(--brand-border-muted, #e2e8f0); }

/* Raw payload disclosure */
.timeline-card-raw { margin-top: 2px; }
.timeline-raw-summary {
    display: inline-flex; align-items: center; gap: 5px;
    cursor: pointer; list-style: none;
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.04em; color: var(--brand-text-dim, #94a3b8);
}
.timeline-raw-summary::-webkit-details-marker { display: none; }
.timeline-card-raw[open] .timeline-raw-summary .w-2\\.5 { transform: rotate(90deg); }
.timeline-raw-summary .transition-transform { transition: transform 0.15s ease; }
.timeline-raw-pre {
    margin: 6px 0 0; padding: 10px 12px;
    font-family: ui-monospace, 'SF Mono', Consolas, monospace;
    font-size: 11px; line-height: 1.5;
    color: #e2e8f0; background: #0f172a;
    border: 1px solid #1e293b; border-radius: 8px;
    white-space: pre-wrap; word-break: break-word;
    max-height: 360px; overflow: auto;
}

</style>
