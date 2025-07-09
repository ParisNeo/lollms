<script setup>
import { computed, ref, onMounted, watch, nextTick } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import { marked } from 'marked';
import CodeBlock from './CodeBlock.vue';
import StepDetail from './StepDetail.vue';
import { Codemirror } from 'vue-codemirror';
import { markdown } from '@codemirror/lang-markdown';
import { oneDark } from '@codemirror/theme-one-dark';
import { EditorView, keymap } from '@codemirror/view';
import UserAvatar from '../ui/UserAvatar.vue';

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
});

const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const isStepsCollapsed = ref(!props.message.isStreaming);
const isEditing = ref(false);
const editedContent = ref('');
const codeMirrorView = ref(null);
const messageContentRef = ref(null);
const isFormattingMenuOpen = ref(false);

const areActionsDisabled = computed(() => discussionsStore.generationInProgress);

function renderMath() {
  if (messageContentRef.value && window.renderMathInElement) {
    window.renderMathInElement(messageContentRef.value, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '\\[', right: '\\]', display: true },
        { left: '\\(', right: '\\)', display: false },
        { left: '$', right: '$', display: false }
      ],
      throwOnError: false
    });
  }
}

watch(() => props.message.content, async () => {
    if (isEditing.value) {
        isEditing.value = false;
    }
    await nextTick();
    renderMath();
}, { flush: 'post' });

onMounted(() => {
    isStepsCollapsed.value = !props.message.isStreaming;
    renderMath();
});

const imagesToRender = computed(() => {
    if (props.message.localImageUrls && props.message.localImageUrls.length > 0) {
        return props.message.localImageUrls;
    }
    if (props.message.image_references && props.message.image_references.length > 0) {
        return props.message.image_references;
    }
    return [];
});

const parsedStreamingContent = computed(() => {
    if (!props.message.content) return '';
    return marked.parse(props.message.content, { gfm: true, breaks: true });
});

const isUser = computed(() => props.message.sender_type === 'user');
const isAi = computed(() => props.message.sender_type === 'assistant');
const isSystem = computed(() => props.message.sender_type === 'system');

const bubbleClass = computed(() => ({
  'user-bubble': isUser.value,
  'ai-bubble': isAi.value,
  'system-bubble': isSystem.value,
}));

const containerClass = computed(() => ({
    'justify-end': isUser.value,
    'justify-start': isAi.value,
    'justify-center': isSystem.value,
}));

const senderName = computed(() => {
    if (isUser.value) return authStore.user?.username || 'You';
    return props.message.sender || 'Unknown';
});

const messageParts = computed(() => {
    if (!props.message.content || props.message.isStreaming) return [];
    const parts = [];
    const content = props.message.content;
    const thinkRegex = /<think>([\s\S]*?)(?:<\/think>|$)/g;
    let lastIndex = 0, match;
    while ((match = thinkRegex.exec(content)) !== null) {
        if (match.index > lastIndex) parts.push({ type: 'content', content: content.substring(lastIndex, match.index) });
        if (match[1] && match[1].trim()) parts.push({ type: 'think', content: match[1].trim() });
        lastIndex = thinkRegex.lastIndex;
    }
    if (lastIndex < content.length) parts.push({ type: 'content', content: content.substring(lastIndex) });
    return parts.length > 0 ? parts : [{ type: 'content', content: '' }];
});

const getContentTokens = (text) => text ? Array.from(marked.lexer(text)) : [];

function parseStepContent(content) {
    if (typeof content !== 'string') return { isJson: false, data: content };
    let processedContent = content.trim();
    if (!((processedContent.startsWith('{') && processedContent.endsWith('}')) || (processedContent.startsWith('[') && processedContent.endsWith(']')))) {
        return { isJson: false, data: content };
    }
    try { return { isJson: true, data: JSON.parse(processedContent) }; } catch (e) { }
    try {
        const repaired = processedContent.replace(/\bTrue\b/g, 'true').replace(/\bFalse\b/g, 'false').replace(/\bNone\b/g, 'null').replace(/'/g, '"');
        return { isJson: true, data: JSON.parse(repaired) };
    } catch (e) { return { isJson: false, data: content }; }
}

function getStepVisuals(step) {
    if (step.status === 'pending') {
        return {
            icon: `<svg class="w-4 h-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>`,
            colorClass: 'text-blue-500',
            title: 'In Progress...'
        };
    }
    switch (step.type) {
        case 'step_start': return { icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4"><path d="M6.3 2.84A1.5 1.5 0 0 0 4 4.11v11.78a1.5 1.5 0 0 0 2.3 1.27l9.344-5.89a1.5 1.5 0 0 0 0-2.54L6.3 2.84Z" /></svg>', colorClass: 'text-gray-500 dark:text-gray-400', title: 'Step Start' };
        case 'step_end': return { icon: '<svg width="20px" height="20px" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" stroke-width="1.5"><path d="M2 12C2 7.28595 2 4.92893 3.46447 3.46447C4.92893 2 7.28595 2 12 2C16.714 2 19.0711 2 20.5355 3.46447C22 4.92893 22 7.28595 22 12C22 16.714 22 19.0711 20.5355 20.5355C19.0711 22 16.714 22 12 22C7.28595 22 4.92893 22 3.46447 20.5355C2 19.0711 2 16.714 2 12Z"/><path d="M8.5 12.5L10.5 14.5L15.5 9.5" stroke-linecap="round" stroke-linejoin="round"/></svg>', colorClass: 'text-green-500', title: 'Step End' };
        case 'info': return { icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4"><path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-7-4a1 1 0 1 1-2 0 1 1 0 0 1 2 0ZM9 9a.75.75 0 0 0 0 1.5h.253a.25.25 0 0 1 .244.304l-.459 2.066A1.75 1.75 0 0 0 10.747 15H11a.75.75 0 0 0 0-1.5h-.253a.25.25 0 0 1-.244-.304l.459-2.066A1.75 1.75 0 0 0 9.253 9H9Z" clip-rule="evenodd" /></svg>', colorClass: 'text-cyan-500', title: 'Info' };
        case 'observation': return { icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20px" height="20px" viewBox="0 0 512.001 512.001" fill="currentColor"><g><path d="M511.303,250.954C480.154,140.542,378.51,57.869,256,57.869c-122.229,0-224.073,82.395-255.302,193.085 c-0.93,3.299-0.93,6.792,0,10.093C31.848,371.46,133.488,454.132,256,454.132c122.237,0,224.077-82.405,255.302-193.085 C512.233,257.747,512.233,254.253,511.303,250.954z M256,416.963c-104.057,0-189.755-69.125-218.04-160.962 C66.187,164.349,151.751,95.038,256,95.038c104.05,0,189.752,69.117,218.04,160.962C445.785,347.739,360.158,416.963,256,416.963 z"/><path d="M256,124.884c-72.299,0-131.117,58.819-131.117,131.117S183.703,387.117,256,387.117 c72.298,0,131.117-58.819,131.117-131.117S328.299,124.884,256,124.884z M307.826,184.436c10.883,0,19.738,8.854,19.738,19.738 c0,8.835-5.639,15.977-13.263,18.643c-11.657,4.074-24.135-3.55-25.984-15.623C286.469,195.22,295.693,184.436,307.826,184.436z M256,349.948c-51.803,0-93.947-42.145-93.947-93.948c0-56.487,49.916-100.759,106.599-93.099 c-7.439,7.063-13.004,16.172-15.788,26.564c-35.28,1.644-63.477,30.855-63.477,66.535c0,36.732,29.883,66.615,66.615,66.615 c35.675,0,64.884-28.192,66.534-63.466c10.031-2.684,19.317-8.167,26.565-15.798C356.757,300.017,312.501,349.948,256,349.948z M285.441,256.538c-0.287,15.99-13.383,28.908-29.44,28.908c-16.237,0-29.445-13.21-29.445-29.445 c0-16.057,12.917-29.153,28.908-29.44C261.389,240.542,272.48,251.061,285.441,256.538z"/></g></svg>', colorClass: 'text-purple-500', title: 'Observation' };
        case 'tool_call': return { icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20px" height="20px" viewBox="0 0 512 512" fill="currentColor"><g><path d="M360.102,240.012l10.156-10.266c0,0,15.609-13.406,33.406-7.328c30.984,10.578,66.781-0.875,91.609-25.734 c7.063-7.063,15.641-21.234,15.641-21.234c0.984-1.344,1.328-3.047,0.922-4.672l-1.922-7.906c-0.359-1.484-1.313-2.75-2.625-3.531 c-1.313-0.766-2.891-0.969-4.344-0.547l-60.984,16.969c-2.266,0.625-4.688-0.219-6.063-2.109l-28.015-38.594 c-0.859-1.172-1.219-2.641-1.016-4.063l5.641-41c0.297-2.234,1.891-4.047,4.063-4.656l64.406-17.922 c2.906-0.813,4.672-3.813,3.953-6.766l-2.547-10.359c-0.344-1.469-1.281-2.719-2.563-3.5c0,0-5.047-3.344-8.719-5.234 c-36.578-18.891-82.64-13.031-113.312,17.656c-22.656,22.656-31.531,53.688-27.375,83.156c3.203,22.656,1.703,34.703-8.078,45.047 c-0.891,0.922-3.703,3.734-8.047,8L360.102,240.012z"/><path d="M211.383,295.418C143.024,361.652,68.461,433.715,68.461,433.715c-2.547,2.438-4,5.797-4.047,9.313 c-0.047,3.5,1.344,6.891,3.813,9.375l31.938,31.938c2.5,2.484,5.875,3.859,9.391,3.813c3.516-0.031,6.859-1.5,9.281-4.031 l139.328-140.953L211.383,295.418z"/><path d="M501.43,451.371c2.484-2.484,3.859-5.859,3.813-9.375c-0.031-3.516-1.5-6.859-4.031-9.297L227.415,166.246 l-43.953,43.969L450.805,483.09c2.438,2.547,5.781,4,9.297,4.047s6.891-1.344,9.391-3.828L501.43,451.371z"/><path d="M254.196,32.621c-32.969-12.859-86.281-14.719-117.156,16.141c-24.313,24.313-59.875,59.891-59.875,59.891 c-12.672,12.656-0.906,25.219-10.266,34.563c-9.359,9.359-24.313,0-32.734,8.422L3.29,182.527c-4.391,4.375-4.391,11.5,0,15.891 l43.016,43.016c4.391,4.391,11.516,4.391,15.906,0l30.875-30.875c8.438-8.422-0.938-23.375,8.438-32.719 c12.609-12.625,26.375-10.484,34.328-2.547l15.891,15.891l17.219,4.531l43.953-43.953l-5.063-16.688 c-14.016-14.031-16.016-30.266-7.234-39.047c13.594-13.594,36.047-33.234,57.078-41.656 C271.102,49.012,267.055,35.668,254.196,32.621z M194.571,103.48c-0.063,0.047,5.859-7.281,5.969-7.375L194.571,103.48z"/></g></svg>', colorClass: 'text-yellow-500', title: 'Thought' };
        case 'thought': return { icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20px" height="20px" viewBox="0 0 17 17" fill="currentColor"><path d="M11.5 10.116c3.033 0 5.5-2.269 5.5-5.058s-2.467-5.058-5.5-5.058c-1.912 0-3.693 0.938-4.684 2.431-0.705-0.399-1.496-0.608-2.316-0.608-2.481 0-4.5 1.86-4.5 4.147 0 2.286 2.019 4.146 4.5 4.146 0.186 0 0.375-0.013 0.573-0.037 0.652 0.588 1.522 0.921 2.427 0.921 1.002 0 1.929-0.387 2.592-1.070 0.488 0.125 0.951 0.186 1.408 0.186zM9.745 8.785l-0.212 0.268c-0.471 0.593-1.231 0.947-2.033 0.947-0.724 0-1.414-0.29-1.895-0.797l-0.184-0.193-0.264 0.046c-0.214 0.037-0.431 0.060-0.657 0.060-1.93 0-3.5-1.411-3.5-3.145 0-1.735 1.57-3.147 3.5-3.147 0.792 0 1.549 0.246 2.189 0.713l0.472 0.343 0.267-0.52c0.738-1.433 2.336-2.36 4.072-2.36 2.481 0 4.5 1.82 4.5 4.059 0 2.237-2.019 4.058-4.5 4.058-0.453 0-0.921-0.075-1.429-0.231l-0.326-0.101zM11.5 10.5c-1.103 0-2 0.897-2 2s0.897 2 2 2 2-0.897 2-2-0.897-2-2-2zM11.5 13.5c-0.551 0-1-0.448-1-1s0.449-1 1-1 1 0.448 1 1-0.449 1-1 1zM15.25 14c-0.689 0-1.25 0.561-1.25 1.25s0.561 1.25 1.25 1.25 1.25-0.561 1.25-1.25-0.561-1.25-1.25-1.25zM15 15.25c0-0.138 0.112-0.25 0.25-0.25s0.25 0.112 0.25 0.25c0 0.275-0.5 0.275-0.5 0z"/></svg>', colorClass: 'text-yellow-500', title: 'Tool call' };
        case 'scratchpad': return { icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20px" height="20px" viewBox="0 0 72 72" fill="currentColor"><path d="M55.068,9H55V5c0-1.104-0.896-2-2-2s-2,0.896-2,2v4h-7V5c0-1.104-0.896-2-2-2s-2,0.896-2,2v4h-7V5c0-1.104-0.896-2-2-2 s-2,0.896-2,2v4h-7V5c0-1.104-0.896-2-2-2s-2,0.896-2,2v4h-1.068C13.104,9,10,12.104,10,15.932v46.136 C10,65.896,13.104,69,16.932,69h38.136C58.896,69,62,65.896,62,62.068V15.932C62,12.104,58.896,9,55.068,9z M16.932,13H18v5 c0,1.104,0.896,2,2,2s2-0.896,2-2v-5h7v5c0,1.104,0.896,2,2,2s2-0.896,2-2v-5h7v5c0,1.104,0.896,2,2,2s2-0.896,2-2v-5h7v5 c0,1.104,0.896,2,2,2s2-0.896,2-2v-5h0.068C56.688,13,58,14.313,58,15.932V26H14V15.932C14,14.313,15.313,13,16.932,13z M55.068,65 H16.932C15.313,65,14,63.688,14,62.068V28h44v34.068C58,63.688,56.688,65,55.068,65z"/><path d="M54,51c-0.553,0-1,0.447-1,1v3.184C53,58.109,52.1,60,50.521,60H34.119c-0.553,0-1,0.447-1,1s0.447,1,1,1h16.402 C53.314,62,55,59.325,55,55.184V52C55,51.447,54.552,51,54,51z"/><path d="M53.527,46.251c-0.18,0.179-0.289,0.438-0.289,0.699c0,0.271,0.109,0.528,0.289,0.711c0.19,0.188,0.451,0.289,0.711,0.289 c0.261,0,0.521-0.101,0.71-0.289c0.181-0.19,0.29-0.451,0.29-0.711c0-0.261-0.109-0.521-0.29-0.709 C54.568,45.87,53.909,45.88,53.527,46.251z"/></svg>', colorClass: 'text-yellow-500', title: 'Scratchpad' };
        case 'step': return { icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20px" height="20px" viewBox="0 0 32 32" fill="currentColor"><path d="M19.168,8.872c-0.788-0.515-1.645-0.928-2.551-1.184c-0.483-0.138-0.987-0.207-1.486-0.263 c-0.466-0.053-0.936-0.093-1.406-0.093c-0.021,0-0.042,0-0.062,0c-0.872,0.008-1.707,0.37-2.42,0.849 c-0.235,0.157-0.453,0.345-0.673,0.521c-0.402,0.326-0.726,0.748-1.01,1.177c-0.265,0.402-0.464,0.849-0.658,1.291 c-0.22,0.5-0.413,1.01-0.586,1.529c-0.297,0.906-0.455,1.874-0.536,2.821c-0.081,0.965-0.104,1.919-0.04,2.884 c0.068,0.989,0.201,1.988,0.413,2.958c0.207,0.946,0.44,1.889,0.767,2.802c0.176,0.489,0.407,0.962,0.631,1.431 c0.18,0.383,0.379,0.756,0.587,1.124c0.462,0.819,0.993,1.626,1.703,2.251c0.406,0.358,0.908,0.604,1.419,0.775 c0.493,0.165,1,0.241,1.52,0.254c0.468,0.011,0.936-0.036,1.397-0.125c0.333-0.064,0.654-0.188,0.961-0.332 c0.148-0.07,0.303-0.191,0.424-0.297c0.127-0.11,0.233-0.226,0.33-0.366c0.227-0.333,0.347-0.714,0.39-1.114 c0.049-0.46,0.002-0.93-0.051-1.389c-0.055-0.477-0.116-0.955-0.172-1.432c-0.085-0.72-0.117-1.442-0.135-2.166 c-0.018-0.698-0.017-1.39,0.059-2.083c0.073-0.469,0.177-0.932,0.291-1.394c0.112-0.448,0.24-0.899,0.409-1.331 c0.018-0.039,0.036-0.078,0.054-0.117c0.113-0.046,0.214-0.117,0.321-0.2c0.904-0.712,1.855-1.506,2.228-2.638 c0.165-0.504,0.267-1.008,0.335-1.533c0.026-0.203,0.04-0.406,0.051-0.608c0.023-0.407-0.07-0.813-0.182-1.201 C21.141,10.455,20.201,9.545,19.168,8.872z M19.907,13.438c-0.07,0.391-0.169,0.775-0.307,1.148 c-0.078,0.159-0.171,0.305-0.274,0.45c-0.447,0.509-0.967,0.926-1.502,1.342c-0.184,0.065-0.347,0.192-0.451,0.371 c-0.364,0.629-0.62,1.317-0.811,2.018c-0.208,0.764-0.352,1.539-0.409,2.329c-0.053,0.739,0.002,1.491,0.04,2.229 c0.04,0.754,0.156,1.501,0.261,2.247c-0.004-0.033-0.009-0.067-0.013-0.1c0.092,0.704,0.228,1.438,0.168,2.151 c-0.008,0.038-0.019,0.075-0.03,0.112c-0.024,0.047-0.05,0.093-0.078,0.137c-0.006,0.006-0.012,0.011-0.017,0.017 c-0.048,0.031-0.096,0.059-0.147,0.086c-0.18,0.06-0.361,0.1-0.548,0.133c-0.436,0.043-0.874,0.039-1.31,0.006 c-0.284-0.053-0.557-0.131-0.828-0.233c-0.188-0.087-0.365-0.185-0.537-0.302c-0.211-0.187-0.402-0.388-0.58-0.607 c-0.179-0.238-0.353-0.478-0.512-0.729c-0.174-0.275-0.33-0.561-0.483-0.847c-0.299-0.556-0.576-1.125-0.83-1.704 c-0.526-1.371-0.863-2.817-1.088-4.264c-0.085-0.706-0.142-1.413-0.144-2.126c0-0.732,0.067-1.452,0.156-2.176 c0.071-0.423,0.144-0.847,0.259-1.261c0.129-0.468,0.285-0.923,0.46-1.375c0.273-0.634,0.57-1.258,0.974-1.818 c0.22-0.259,0.462-0.481,0.724-0.693c0.294-0.213,0.593-0.403,0.919-0.558c0.197-0.066,0.396-0.117,0.599-0.158 c0.359-0.032,0.728-0.024,1.087-0.004c0.325,0.018,0.65,0.045,0.973,0.081c0.535,0.086,1.053,0.212,1.561,0.405 c0.516,0.235,1.004,0.505,1.467,0.833c0.269,0.215,0.53,0.44,0.756,0.701c0.126,0.177,0.236,0.362,0.331,0.561 c0.086,0.229,0.154,0.463,0.203,0.702C19.967,12.843,19.944,13.139,19.907,13.438z M8.153,8.78c0.04-0.055,0.064-0.123,0.093-0.186 C8.371,8.317,8.445,8.035,8.44,7.726c-0.006-0.299-0.117-0.58-0.237-0.849c-0.08-0.184-0.227-0.349-0.375-0.481 c-0.11-0.101-0.233-0.191-0.366-0.26c-0.201-0.102-0.425-0.125-0.627-0.07c-0.092-0.039-0.19-0.061-0.29-0.061 c-0.071,0-0.142,0.011-0.213,0.034c-0.254,0.083-0.5,0.184-0.724,0.332C5.453,6.476,5.355,6.587,5.243,6.735 C5.141,6.87,5.082,7.016,5.017,7.171C4.97,7.283,4.953,7.417,4.938,7.537C4.909,7.734,4.89,7.921,4.909,8.12 c0.03,0.326,0.15,0.631,0.375,0.875C5.43,9.155,5.614,9.278,5.804,9.38C6.06,9.521,6.323,9.596,6.615,9.61 C6.861,9.621,7.096,9.553,7.32,9.46c0.078-0.03,0.154-0.062,0.229-0.097c0.116-0.051,0.208-0.138,0.309-0.216 C7.977,9.054,8.068,8.901,8.153,8.78z M6.86,7.995C6.853,8.007,6.846,8.019,6.839,8.031C6.832,8.039,6.824,8.048,6.816,8.056 C6.8,8.064,6.784,8.072,6.768,8.08C6.73,8.093,6.692,8.105,6.654,8.115c-0.006,0-0.012,0-0.017,0 C6.632,8.114,6.627,8.113,6.622,8.111c-0.061-0.033-0.119-0.07-0.176-0.11C6.446,8,6.445,7.999,6.444,7.997 C6.443,7.921,6.446,7.846,6.452,7.771c0.007-0.031,0.014-0.063,0.022-0.094C6.49,7.668,6.506,7.659,6.523,7.651 c0.076-0.029,0.154-0.055,0.232-0.081c0.004-0.001,0.008-0.003,0.012-0.004c0.003,0.002,0.006,0.004,0.01,0.006 C6.791,7.587,6.806,7.601,6.82,7.615c0.016,0.026,0.031,0.052,0.046,0.078c0.016,0.045,0.029,0.09,0.041,0.136 C6.894,7.886,6.878,7.941,6.86,7.995z M10.253,5.053L10.253,5.053C10.254,5.052,10.254,5.052,10.253,5.053L10.253,5.053 C10.254,5.052,10.253,5.052,10.253,5.053z M9.082,6.583C9.187,6.674,9.3,6.753,9.41,6.835c0.121,0.091,0.279,0.133,0.417,0.188 c0.08,0.027,0.161,0.044,0.246,0.051c0.152,0.025,0.297,0.038,0.449,0.042c0.133,0.004,0.305-0.036,0.434-0.074 c0.14-0.042,0.273-0.11,0.404-0.173c0.078-0.042,0.152-0.091,0.222-0.148c0.123-0.091,0.225-0.178,0.326-0.29 c0.123-0.14,0.222-0.298,0.305-0.462c0.169-0.33,0.26-0.696,0.212-1.065c-0.019-0.159-0.042-0.309-0.097-0.458 C12.29,4.341,12.245,4.24,12.201,4.14c-0.053-0.123-0.155-0.222-0.239-0.324c-0.08-0.076-0.163-0.146-0.254-0.21 c-0.169-0.112-0.356-0.212-0.551-0.275c-0.127-0.042-0.252-0.074-0.383-0.095c-0.076-0.013-0.149-0.021-0.22-0.021 c-0.125,0-0.245,0.026-0.365,0.097c-0.039,0.023-0.076,0.049-0.11,0.079C9.872,3.342,9.65,3.366,9.469,3.492 C9.281,3.623,9.113,3.757,8.971,3.936c-0.106,0.133-0.18,0.237-0.248,0.388c-0.066,0.15-0.117,0.292-0.159,0.451 c-0.108,0.43-0.078,0.851,0.108,1.252C8.77,6.241,8.902,6.429,9.082,6.583z M10.248,5.056c0.002-0.001,0.003-0.002,0.005-0.004 c0.018-0.027,0.038-0.054,0.061-0.078c-0.02,0.026-0.04,0.052-0.06,0.078c0.002-0.001,0.004-0.003,0.005-0.004 c-0.002,0.001-0.004,0.003-0.006,0.004c-0.001,0.001-0.001,0.002-0.002,0.003c0-0.001,0.001-0.001,0.001-0.001 C10.252,5.054,10.25,5.055,10.248,5.056L10.248,5.056z M10.328,4.999c0.005-0.004,0.011-0.008,0.016-0.012 c0.102-0.071,0.191-0.149,0.261-0.241c0.051,0.013,0.102,0.028,0.153,0.046c0.031,0.016,0.06,0.034,0.09,0.053 c0.003,0.003,0.006,0.006,0.009,0.009c0.016,0.05,0.03,0.101,0.042,0.152C10.9,5.031,10.9,5.056,10.9,5.081 c-0.009,0.031-0.018,0.062-0.028,0.092c-0.028,0.052-0.057,0.102-0.088,0.152c-0.028,0.03-0.057,0.059-0.087,0.088 c-0.022,0.014-0.045,0.027-0.068,0.039c-0.037,0.013-0.073,0.025-0.111,0.035c-0.053-0.011-0.104-0.023-0.156-0.04 c-0.046-0.043-0.091-0.086-0.134-0.131c-0.003-0.005-0.005-0.01-0.008-0.015c-0.004-0.013-0.008-0.026-0.012-0.04 c0-0.017,0-0.034,0-0.051c0.01-0.043,0.021-0.085,0.033-0.128C10.269,5.054,10.298,5.026,10.328,4.999z M10.238,5.064L10.238,5.064 c-0.015,0.012-0.029,0.022-0.043,0.033C10.209,5.086,10.223,5.075,10.238,5.064z M13.705,5.756c0.116,0.119,0.244,0.242,0.387,0.33 c0.246,0.154,0.525,0.265,0.811,0.326c0.28,0.059,0.548,0.042,0.828-0.006c0.178-0.029,0.345-0.074,0.513-0.144 c0.133-0.055,0.227-0.099,0.341-0.174c0.104-0.07,0.201-0.152,0.298-0.231c0.481-0.39,0.646-0.993,0.692-1.586 c0.011-0.153-0.009-0.307-0.028-0.46c-0.032-0.258-0.057-0.547-0.199-0.775c-0.178-0.282-0.39-0.54-0.669-0.728 c-0.083-0.059-0.165-0.101-0.258-0.146c-0.222-0.108-0.434-0.136-0.675-0.159C15.732,2,15.717,2,15.702,2 c-0.101,0-0.206,0.03-0.301,0.077c-0.172-0.068-0.347-0.066-0.535-0.031C14.67,2.082,14.48,2.176,14.31,2.275 c-0.216,0.121-0.4,0.297-0.559,0.485c-0.157,0.186-0.261,0.383-0.358,0.604c-0.068,0.159-0.121,0.303-0.159,0.47 c-0.038,0.167-0.049,0.352-0.055,0.523c-0.015,0.354,0.11,0.68,0.243,0.997C13.478,5.489,13.607,5.655,13.705,5.756z M14.912,3.953 c0.022-0.043,0.045-0.085,0.07-0.127c0.019-0.021,0.039-0.042,0.059-0.062c0.046-0.028,0.091-0.054,0.139-0.079 c0.041-0.013,0.084-0.024,0.128-0.033c0.063-0.011,0.126-0.036,0.185-0.07c0.074,0.023,0.153,0.036,0.236,0.044 c0.007,0.002,0.014,0.003,0.022,0.005c0.021,0.011,0.042,0.022,0.063,0.034c0.048,0.044,0.094,0.091,0.138,0.14 c0.006,0.024,0.012,0.048,0.017,0.072c0.015,0.146,0.02,0.289,0.013,0.435c-0.014,0.062-0.03,0.121-0.049,0.181 c-0.018,0.034-0.037,0.067-0.058,0.099c-0.013,0.013-0.026,0.025-0.039,0.038c-0.051,0.037-0.103,0.072-0.157,0.105 c-0.067,0.021-0.135,0.037-0.204,0.051c-0.067,0.004-0.133,0.004-0.2,0.001c-0.069-0.019-0.135-0.041-0.203-0.064 c-0.023-0.012-0.045-0.025-0.067-0.039c-0.019-0.018-0.039-0.037-0.057-0.056c-0.025-0.04-0.047-0.079-0.069-0.12 c-0.01-0.035-0.019-0.071-0.027-0.107c-0.005-0.08-0.005-0.158-0.002-0.239C14.868,4.092,14.888,4.023,14.912,3.953z M22.41,5.302 c0.006-0.207-0.034-0.422-0.085-0.625c-0.055-0.203-0.15-0.404-0.25-0.589c-0.059-0.108-0.142-0.207-0.218-0.303 c-0.119-0.152-0.256-0.26-0.409-0.377c-0.163-0.123-0.434-0.133-0.622-0.08c-0.023,0.006-0.045,0.013-0.067,0.022 c-0.144-0.141-0.339-0.23-0.552-0.23c-0.003,0-0.007,0-0.01,0c-0.271,0.004-0.508,0.078-0.752,0.184 c-0.231,0.1-0.419,0.233-0.61,0.398c-0.165,0.14-0.294,0.333-0.415,0.51c-0.161,0.239-0.267,0.523-0.343,0.8 c-0.152,0.548-0.066,1.209,0.256,1.683c0.309,0.455,0.805,0.718,1.336,0.823c0.335,0.066,0.652,0.055,0.987-0.004 c0.237-0.04,0.462-0.146,0.68-0.243c0.138-0.062,0.256-0.182,0.373-0.275c0.112-0.091,0.222-0.248,0.301-0.366 c0.135-0.199,0.229-0.406,0.307-0.635C22.391,5.779,22.404,5.529,22.41,5.302z M20.099,4.744c0.017-0.002,0.033-0.006,0.05-0.007 C20.132,4.74,20.116,4.742,20.099,4.744L20.099,4.744z M20.098,4.744L20.098,4.744c-0.025,0.003-0.049,0.007-0.074,0.01 C20.049,4.749,20.074,4.747,20.098,4.744z M20.802,5.392c-0.015,0.076-0.033,0.15-0.055,0.224c-0.025,0.045-0.051,0.089-0.079,0.133 c-0.028,0.03-0.056,0.059-0.085,0.086c-0.004,0.002-0.007,0.004-0.011,0.006c-0.084,0.028-0.169,0.051-0.255,0.07 c-0.062,0.003-0.124,0.003-0.187,0c-0.093-0.018-0.183-0.04-0.273-0.071c-0.032-0.017-0.064-0.035-0.095-0.055 c-0.012-0.011-0.023-0.022-0.034-0.034c-0.006-0.01-0.012-0.02-0.017-0.03c-0.017-0.052-0.031-0.105-0.043-0.159 c-0.003-0.072-0.002-0.142,0.002-0.213c0.016-0.073,0.035-0.144,0.058-0.214c0.037-0.074,0.077-0.144,0.122-0.213 c0.029-0.033,0.06-0.064,0.092-0.094c0.021-0.013,0.042-0.025,0.064-0.037c0.06-0.02,0.12-0.039,0.183-0.055 c0.003,0,0.006,0,0.009,0c0.102-0.002,0.2-0.022,0.291-0.058c0.025,0.024,0.052,0.047,0.08,0.07 c0.023,0.022,0.046,0.044,0.067,0.067c0.044,0.066,0.084,0.134,0.12,0.204c0.019,0.055,0.035,0.11,0.049,0.167 C20.807,5.255,20.806,5.323,20.802,5.392z M26.737,7.184c-0.095-0.186-0.26-0.354-0.409-0.496c-0.135-0.127-0.297-0.228-0.464-0.302 c-0.18-0.078-0.351-0.138-0.544-0.178c-0.163-0.036-0.332-0.051-0.498-0.072c-0.028,0-0.056,0.002-0.083,0.005 c-0.082-0.029-0.169-0.045-0.258-0.045c-0.064,0-0.129,0.008-0.194,0.025c-0.354,0.091-0.682,0.231-0.97,0.458 c-0.237,0.189-0.421,0.436-0.595,0.682c-0.341,0.481-0.54,1.025-0.531,1.62c0.006,0.371,0.099,0.743,0.25,1.08 c0.08,0.176,0.176,0.32,0.297,0.472c0.123,0.151,0.277,0.263,0.434,0.379c0.131,0.095,0.303,0.163,0.453,0.216 c0.169,0.061,0.339,0.1,0.517,0.129c0.207,0.032,0.411,0.059,0.62,0.057c0.203,0,0.411-0.038,0.61-0.079 c0.343-0.074,0.658-0.269,0.923-0.491c0.106-0.091,0.191-0.178,0.279-0.288c0.154-0.191,0.233-0.364,0.324-0.591 c0.064-0.161,0.093-0.337,0.121-0.506c0.032-0.195,0.061-0.39,0.074-0.587C27.128,8.151,26.97,7.645,26.737,7.184z M25.424,8.833 c-0.026,0.153-0.062,0.303-0.113,0.45c-0.003,0.005-0.006,0.01-0.009,0.016c-0.035,0.039-0.072,0.075-0.111,0.111 c-0.04,0.027-0.08,0.052-0.122,0.075c-0.054,0.017-0.108,0.032-0.164,0.045c-0.101,0.007-0.201,0.006-0.303-0.002 c-0.138-0.027-0.271-0.06-0.404-0.104c-0.043-0.023-0.084-0.048-0.125-0.075c-0.02-0.019-0.039-0.038-0.057-0.057 c-0.032-0.049-0.061-0.1-0.088-0.152c-0.039-0.116-0.071-0.233-0.095-0.354c-0.006-0.092-0.007-0.183-0.002-0.274 c0.018-0.088,0.04-0.174,0.069-0.259c0.067-0.137,0.145-0.266,0.232-0.39c0.044-0.051,0.09-0.098,0.138-0.143 c0.028-0.016,0.056-0.032,0.084-0.047c0.076,0.054,0.16,0.094,0.246,0.107C24.776,7.81,24.95,7.844,25.12,7.9 c0.031,0.016,0.06,0.034,0.09,0.052c0.019,0.019,0.038,0.038,0.057,0.057c0.028,0.044,0.053,0.088,0.077,0.133 c0.031,0.096,0.059,0.191,0.082,0.29C25.436,8.565,25.437,8.699,25.424,8.833z"/></svg>', colorClass: 'text-yellow-500', title: 'Step' };
        case 'error': return { icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20px" height="20px" viewBox="0 0 16 16" fill="currentColor"><path d="M7.493 0.015 C 7.442 0.021,7.268 0.039,7.107 0.055 C 5.234 0.242,3.347 1.208,2.071 2.634 C 0.660 4.211,-0.057 6.168,0.009 8.253 C 0.124 11.854,2.599 14.903,6.110 15.771 C 8.169 16.280,10.433 15.917,12.227 14.791 C 14.017 13.666,15.270 11.933,15.771 9.887 C 15.943 9.186,15.983 8.829,15.983 8.000 C 15.983 7.171,15.943 6.814,15.771 6.113 C 14.979 2.878,12.315 0.498,9.000 0.064 C 8.716 0.027,7.683 -0.006,7.493 0.015 M8.853 1.563 C 9.967 1.707,11.010 2.136,11.944 2.834 C 12.273 3.080,12.920 3.727,13.166 4.056 C 13.727 4.807,14.142 5.690,14.330 6.535 C 14.544 7.500,14.544 8.500,14.330 9.465 C 13.916 11.326,12.605 12.978,10.867 13.828 C 10.239 14.135,9.591 14.336,8.880 14.444 C 8.456 14.509,7.544 14.509,7.120 14.444 C 5.172 14.148,3.528 13.085,2.493 11.451 C 2.279 11.114,1.999 10.526,1.859 10.119 C 1.618 9.422,1.514 8.781,1.514 8.000 C 1.514 6.961,1.715 6.075,2.160 5.160 C 2.500 4.462,2.846 3.980,3.413 3.413 C 3.980 2.846,4.462 2.500,5.160 2.160 C 6.313 1.599,7.567 1.397,8.853 1.563 M7.706 4.290 C 7.482 4.363,7.355 4.491,7.293 4.705 C 7.257 4.827,7.253 5.106,7.259 6.816 C 7.267 8.786,7.267 8.787,7.325 8.896 C 7.398 9.033,7.538 9.157,7.671 9.204 C 7.803 9.250,8.197 9.250,8.329 9.204 C 8.462 9.157,8.602 9.033,8.675 8.896 C 8.733 8.787,8.733 8.786,8.741 6.816 C 8.749 4.664,8.749 4.662,8.596 4.481 C 8.472 4.333,8.339 4.284,8.040 4.276 C 7.893 4.272,7.743 4.278,7.706 4.290 M7.786 10.530 C 7.597 10.592,7.410 10.753,7.319 10.932 C 7.249 11.072,7.237 11.325,7.294 11.495 C 7.388 11.780,7.697 12.000,8.000 12.000 C 8.303 12.000,8.612 11.780,8.706 11.495 C 8.763 11.325,8.751 11.072,8.681 10.932 C 8.616 10.804,8.460 10.646,8.333 10.580 C 8.217 10.520,7.904 10.491,7.786 10.530 "/></svg>', colorClass: 'text-yellow-500', title: 'Step' };
        
        default: return { icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4"><path fill-rule="evenodd" d="M11.074 2.5a.75.75 0 0 1 .84.316l1.325 2.163a.75.75 0 0 0 .618.37l2.38-.07a.75.75 0 0 1 .81.63l.255 2.338a.75.75 0 0 0 .399.64l2.083 1.2a.75.75 0 0 1 0 1.298l-2.083 1.2a.75.75 0 0 0-.4.64l-.255 2.338a.75.75 0 0 1-.81.63l-2.38-.07a.75.75 0 0 0-.618.37l-1.325 2.163a.75.75 0 0 1-1.33 0l-1.325-2.163a.75.75 0 0 0-.618-.37l-2.38.07a.75.75 0 0 1-.81-.63l-.255-2.338a.75.75 0 0 0-.4-.64l-2.083-1.2a.75.75 0 0 1 0-1.298l2.083-1.2a.75.75 0 0 0 .4-.64l.255-2.338a.75.75 0 0 1 .81-.63l2.38.07a.75.75 0 0 0 .618-.37l1.325-2.163a.75.75 0 0 1 .49-.316Z" clip-rule="evenodd" /></svg>', colorClass: 'text-gray-500 dark:text-gray-400', title: 'Step' };
    }
}


const getStepContent = (content) => content ? marked.parse(content, { gfm: true, breaks: true }) : '';

const latestStep = computed(() => {
    if (props.message.steps && props.message.steps.length > 0) {
        return [...props.message.steps].reverse().find(s => s && s.content) || null;
    }
    return null;
});

const editorExtensions = computed(() => {
    return [
        markdown(),
        EditorView.lineWrapping,
        keymap.of([{
            key: "Mod-Enter",
            run: () => { handleSaveEdit(); return true; },
        }, {
            key: "Escape",
            run: () => { handleCancelEdit(); return true; }
        }])
    ];
});

const branchInfo = computed(() => {
    const hasMultipleBranches = props.message.branches && props.message.branches.length > 0;
    if (!hasMultipleBranches) return null;
    const currentMessages = discussionsStore.activeMessages;
    const currentMessageIndex = currentMessages.findIndex(m => m.id === props.message.id);
    const nextMessage = currentMessages[currentMessageIndex + 1];
    let activeBranchIndex = nextMessage ? props.message.branches.findIndex(id => id === nextMessage.id) : -1;
    if (activeBranchIndex === -1) activeBranchIndex = 0;
    return {
        isBranchPoint: true,
        current: activeBranchIndex + 1,
        total: props.message.branches.length,
        branchIds: props.message.branches,
        currentIndex: activeBranchIndex,
    };
});

function navigateBranch(direction) {
    if (!branchInfo.value) return;
    const { branchIds, currentIndex } = branchInfo.value;
    const newIndex = (currentIndex + direction + branchIds.length) % branchIds.length;
    discussionsStore.switchBranch(branchIds[newIndex]);
}

function toggleEdit() {
    isEditing.value = !isEditing.value;
    if (isEditing.value) {
        editedContent.value = props.message.content;
    }
}

async function handleSaveEdit() {
    await discussionsStore.updateMessageContent({ messageId: props.message.id, newContent: editedContent.value });
    isEditing.value = false;
}

function handleCancelEdit() { isEditing.value = false; }
function handleEditorReady(payload) { codeMirrorView.value = payload.view; }

function insertTextAtCursor(before, after = '', placeholder = '') {
    const view = codeMirrorView.value;
    if (!view) return;
    const { from, to } = view.state.selection.main;
    const selectedText = view.state.doc.sliceString(from, to);
    let textToInsert, selStart, selEnd;
    if (selectedText) {
        textToInsert = `${before}${selectedText}${after}`;
        selStart = from + before.length;
        selEnd = selStart + selectedText.length;
    } else {
        textToInsert = `${before}${placeholder}${after}`;
        selStart = from + before.length;
        selEnd = selStart + placeholder.length;
    }
    view.dispatch({
        changes: { from, to, insert: textToInsert },
        selection: { anchor: selStart, head: selEnd }
    });
    view.focus();
}

function copyContent() {
  navigator.clipboard.writeText(props.message.content);
  uiStore.addNotification('Content copied!', 'success');
}

async function handleDelete() {
  const confirmed = await uiStore.showConfirmation({
      title: 'Delete Message', message: 'This will delete the message and its entire branch.', confirmText: 'Delete'
  });
  if (confirmed) discussionsStore.deleteMessage({ messageId: props.message.id});
}

function handleGrade(change) {
  discussionsStore.gradeMessage({ messageId: props.message.id, change });
}

function handleBranchOrRegenerate() {
    let messageToBranchFrom = null;
    if (props.message.sender_type === 'user') {
        messageToBranchFrom = props.message;
    } else {
        const currentMessages = discussionsStore.activeMessages;
        const currentMessageIndex = currentMessages.findIndex(m => m.id === props.message.id);
        if (currentMessageIndex > -1) {
            for (let i = currentMessageIndex - 1; i >= 0; i--) {
                const prevMsg = currentMessages[i];
                if (prevMsg && prevMsg.sender_type === 'user') {
                    messageToBranchFrom = prevMsg;
                    break;
                }
            }
        }
    }
    if (messageToBranchFrom) {
        discussionsStore.initiateBranch(messageToBranchFrom);
    } else {
        uiStore.addNotification('Could not find a valid user prompt to regenerate from.', 'error');
    }
}

function showSourceDetails(source) { uiStore.openModal('sourceViewer', source); }

function getSimilarityColor(score) {
  if (score === undefined || score === null) return 'bg-gray-400 dark:bg-gray-600';
  if (score >= 85) return 'bg-green-500';
  if (score >= 70) return 'bg-yellow-500';
  return 'bg-red-500';
}
const user = computed(() => authStore.user);
const formattingMenuItems = [
    { type: 'header', label: 'Basic' },
    { label: 'Bold', action: () => insertTextAtCursor('**', '**', 'bold text') },
    { label: 'Italic', action: () => insertTextAtCursor('*', '*', 'italic text') },
    { label: 'Inline Code', action: () => insertTextAtCursor('`', '`', 'code') },
    { type: 'separator' },
    { type: 'header', label: 'Math' },
    { label: 'Inline Formula', action: () => insertTextAtCursor('$', '$', 'E=mc^2') },
    { label: 'Display Formula', action: () => insertTextAtCursor('$$\n', '\n$$', 'x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}') },
    { type: 'separator' },
    { type: 'header', label: 'Elements' },
    { label: 'Link', action: () => insertTextAtCursor('[', '](https://)', 'link text') },
    { label: 'Table', action: () => insertTextAtCursor('| Header 1 | Header 2 |\n|---|---|\n| Cell 1 | Cell 2 |\n| Cell 3 | Cell 4 |', '', '') },
    { type: 'separator' },
    { type: 'header', label: 'Code Blocks' },
    { label: 'Python', action: () => insertTextAtCursor('```python\n', '\n```', '# Your code here') },
    { label: 'JavaScript', action: () => insertTextAtCursor('```javascript\n', '\n```', '// Your code here') },
    { label: 'JSON', action: () => insertTextAtCursor('```json\n', '\n```', '{\n  "key": "value"\n}') },
    { label: 'Markdown', action: () => insertTextAtCursor('```markdown\n', '\n```', '## Example') },
];
</script>

<template>
  <div class="message-container group w-full flex" :class="containerClass" :data-message-id="message.id">
    <div class="message-bubble" :class="bubbleClass">
        <div v-if="!isEditing">
            <div v-if="!isUser && !isSystem" class="flex items-center text-xs mb-2 text-gray-500 dark:text-gray-400">
                <span class="font-semibold text-gray-700 dark:text-gray-300">{{ senderName }}</span>
                <span v-if="isAi && message.model_name" class="ml-2">· {{ message.model_name }}</span>
            </div>

            <div v-if="isUser" class="flex-shrink-0 flex items-center space-x-2">
                <UserAvatar v-if="user" :icon="user.icon" :username="user.username" size-class="h-10 w-10" /><span class="truncate max-w-[120px]">{{ user.username }}</span>
            </div>

            <div v-if="imagesToRender.length > 0" 
                class="my-2 grid gap-2"
                :class="[imagesToRender.length > 1 ? 'grid-cols-2 md:grid-cols-3' : 'grid-cols-1']">
                <div v-for="(imgSrc, index) in imagesToRender" :key="index" class="group/image relative rounded-lg overflow-hidden bg-gray-200 dark:bg-gray-800 cursor-pointer" @click="uiStore.openImageViewer(imgSrc)">
                    <AuthenticatedImage :src="imgSrc" class="w-full h-auto max-h-80 object-contain" />
                </div>
            </div>
            
            <div :key="message.isStreaming ? 'streaming' : 'settled'" ref="messageContentRef">
                <div v-if="message.content || (isUser && !imagesToRender.length)" class="message-content text-sm prose prose-sm dark:prose-invert max-w-none">
                    <div v-if="message.isStreaming" v-html="parsedStreamingContent"></div>
                    <template v-else>
                        <template v-for="(part, index) in messageParts" :key="index">
                            <template v-if="part.type === 'content'">
                                <template v-for="(token, tokenIndex) in getContentTokens(part.content)" :key="tokenIndex">
                                    <CodeBlock v-if="token.type === 'code'" :language="token.lang" :code="token.text" />
                                    <div v-else v-html="marked.parse(token.raw, { gfm: true, breaks: true })"></div>
                                </template>
                            </template>
                            <details v-else-if="part.type === 'think'" class="think-block my-4">
                                <summary class="think-summary">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                    <span>Thinking...</span>
                                </summary>
                                <div class="think-content p-3" v-html="marked.parse(part.content, { gfm: true, breaks: true })"></div>
                            </details>
                        </template>
                    </template>
                </div>
            </div>
            
            <div v-if="message.isStreaming && !message.content && (!imagesToRender || imagesToRender.length === 0)" class="typing-indicator">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
            </div>
        </div>

        <div v-else class="w-full">
            <div class="flex items-center space-x-1 border-b dark:border-gray-600 mb-2 pb-2">
                 <div class="relative">
                    <button @click="isFormattingMenuOpen = !isFormattingMenuOpen" class="p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-600" title="Formatting Options">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12" /></svg>
                    </button>
                    <div v-if="isFormattingMenuOpen" v-on-click-outside="() => isFormattingMenuOpen = false"
                         class="absolute bottom-full left-0 mb-2 w-56 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg shadow-xl z-20 py-1">
                        <template v-for="(item, index) in formattingMenuItems" :key="index">
                            <div v-if="item.type === 'separator'" class="my-1 h-px bg-gray-200 dark:bg-gray-600"></div>
                            <div v-else-if="item.type === 'header'" class="px-3 py-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{{ item.label }}</div>
                            <button v-else @click="item.action(); isFormattingMenuOpen = false" class="w-full text-left flex items-center px-3 py-1.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-blue-500 hover:text-white">
                                {{ item.label }}
                            </button>
                        </template>
                    </div>
                </div>
            </div>
            <codemirror v-model="editedContent" placeholder="Enter your message..." :style="{ maxHeight: '500px' }" :autofocus="true" :indent-with-tab="true" :tab-size="2" :extensions="editorExtensions" @ready="handleEditorReady" class="cm-editor-container"/>
            <div class="flex justify-end space-x-2 mt-2">
                <button @click="handleCancelEdit" class="btn btn-secondary !py-1 !px-3">Cancel</button>
                <button @click="handleSaveEdit" class="btn btn-primary !py-1 !px-3">Save</button>
            </div>
        </div>

      <div v-if="!isEditing">
        <div v-if="message.steps && message.steps.length > 0" class="steps-container mt-4">
            
            <div v-if="isStepsCollapsed">
                <button @click="isStepsCollapsed = !isStepsCollapsed" class="collapsed-steps-summary group/summary">
                    <div class="step-icon flex-shrink-0">
                        <svg v-if="latestStep && latestStep.status !== 'done'" class="w-4 h-4 animate-spin text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                        <svg v-else class="w-4 h-4 text-gray-500 dark:text-gray-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                            <path d="M10 2.5a7.5 7.5 0 00-7.5 7.5c0 2.08.843 3.96 2.21 5.344l-1.078 3.233a.75.75 0 00.945.945l3.233-1.078A7.5 7.5 0 1010 2.5z" />
                            <path d="M4.5 13.5a.5.5 0 01.5.5v.5a.5.5 0 01-1 0v-.5a.5.5 0 01.5-.5z" />
                            <path d="M3 10.5a.5.5 0 01.5.5v.5a.5.5 0 01-1 0v-.5a.5.5 0 01.5-.5z" />
                        </svg>
                    </div>
                    <span v-if="latestStep" class="truncate" v-text="latestStep.content"></span>
                    <span v-else>Show Steps</span>
                </button>
            </div>

            <div v-else>
                 <button @click="isStepsCollapsed = !isStepsCollapsed" class="text-xs font-medium text-gray-500 hover:text-gray-800 dark:hover:text-gray-200 flex items-center w-full text-left mb-2 group/toggle">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2 transition-transform rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
                    <span>Hide Steps</span>
                </button>
                <div class="space-y-2 pl-5 border-l-2 border-gray-200 dark:border-gray-700 ml-2">
                    <template v-for="(step, index) in message.steps" :key="index">
                        <div v-if="step && step.content" class="step-item">
                            <div class="step-icon" :class="getStepVisuals(step).colorClass" :title="getStepVisuals(step).title" v-html="getStepVisuals(step).icon"></div>
                            <div class="step-content-wrapper">
                                <template v-if="parseStepContent(step.content).isJson">
                                    <StepDetail :data="parseStepContent(step.content).data" />
                                </template>
                                <template v-else>
                                    <div class="step-text prose prose-sm dark:prose-invert max-w-none" v-html="getStepContent(step.content)"></div>
                                </template>
                            </div>
                        </div>
                    </template>
                </div>
            </div>
        </div>
        
        <div v-if="!isSystem" class="message-footer mt-2">
            <div class="flex justify-between items-center gap-2">
                <div class="flex items-center flex-wrap gap-2">
                    <div v-if="branchInfo" class="detail-badge branch-badge-nav">
                        <button @click="navigateBranch(-1)" class="p-1 rounded-full hover:bg-black/10 dark:hover:bg-white/10" title="Previous Branch"><svg class="w-3.5 h-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" /></svg></button>
                        <span class="font-mono text-xs">{{ branchInfo.current }}/{{ branchInfo.total }}</span>
                        <button @click="navigateBranch(1)" class="p-1 rounded-full hover:bg-black/10 dark:hover:bg-white/10" title="Next Branch"><svg class="w-3.5 h-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4-4a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg></button>
                    </div>
                    <div v-if="message.token_count && !isEditing" class="detail-badge token-badge">
                        <svg class="w-3.5 h-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M15.988 3.012A2.25 2.25 0 0118 5.25v9.5A2.25 2.25 0 0115.75 17h-3.389a1.5 1.5 0 01-1.49-1.076L9.4 12.5H2.25a.75.75 0 010-1.5h7.15l1.45-3.868A1.5 1.5 0 0112.361 6h3.389A2.25 2.25 0 0115.988 3.012z" clip-rule="evenodd" /></svg>
                        <span>{{ message.token_count }}</span>
                    </div>
                    <button v-if="message.sources && message.sources.length" v-for="source in message.sources" :key="source.document" @click="showSourceDetails(source)" class="detail-badge source-badge" :title="`View source: ${source.document}`">
                        <span class="similarity-chip" :class="getSimilarityColor(source.similarity_percent)"></span>
                        <span class="truncate max-w-[200px]">{{ source.document }}</span>
                    </button>
                </div>
                <div class="flex items-center gap-2 flex-shrink-0">
                    <div class="actions flex items-center space-x-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button :disabled="areActionsDisabled" @click="copyContent" title="Copy" class="p-1.5 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg></button>
                        <button :disabled="areActionsDisabled" @click="toggleEdit" title="Edit" class="p-1.5 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" /><path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" /></svg></button>
                        <button :disabled="areActionsDisabled" @click="handleBranchOrRegenerate" :title="isUser ? 'Resend / Branch' : 'Regenerate'" class="p-1.5 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg></button>
                        <button :disabled="areActionsDisabled" @click="handleDelete" title="Delete" class="p-1.5 rounded-full hover:bg-red-200 dark:hover:bg-red-700 text-red-500 disabled:opacity-50 disabled:cursor-not-allowed"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg></button>
                    </div>
                    <div v-if="isAi" class="message-rating">
                        <button :disabled="areActionsDisabled" @click="handleGrade(1)" title="Good response" class="rating-btn upvote disabled:opacity-50 disabled:cursor-not-allowed" :class="{ 'active': message.user_grade > 0 }"><svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" /></svg></button>
                        <span class="rating-score">{{ message.user_grade || 0 }}</span>
                        <button :disabled="areActionsDisabled" @click="handleGrade(-1)" title="Bad response" class="rating-btn downvote disabled:opacity-50 disabled:cursor-not-allowed" :class="{ 'active': message.user_grade < 0 }"><svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M9.106 17.447a1 1 0 001.788 0l7-14a1 1 0 00-1.169-1.409l-5 1.429A1 1 0 0011 4.429V9a1 1 0 11-2 0V4.429a1 1 0 00-.725-.962l-5-1.428a1 1 0 00-1.17 1.408l7 14z" /></svg></button>
                    </div>
                </div>
            </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-container { animation: messageSlideIn 0.3s ease-out forwards; }
.message-bubble { max-width: 90%; word-break: break-word; min-width: 0; }
.typing-indicator .dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background-color: currentColor; margin: 0 1px; animation: bounce 1.4s infinite ease-in-out both; }
.typing-indicator .dot:nth-of-type(1) { animation-delay: -0.32s; }
.typing-indicator .dot:nth-of-type(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1.0); } }
.think-block { @apply bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800/50 rounded-lg; }
.think-block[open] .think-summary { @apply border-b border-blue-200 dark:border-blue-800/50; }
.think-summary { @apply flex items-center p-2 text-sm font-semibold text-blue-800 dark:text-blue-200 cursor-pointer list-none; -webkit-tap-highlight-color: transparent; }
.think-summary:focus-visible { @apply ring-2 ring-blue-400 outline-none; }
.think-summary::-webkit-details-marker { display: none; }
.think-content { @apply prose-sm max-w-none text-gray-700 dark:text-gray-300; }
.branch-badge, .branch-badge-nav { @apply bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200; }
.branch-badge-nav { @apply flex items-center gap-1; }
.step-item { display: flex; gap: 0.75rem; align-items: flex-start; }
.step-icon { flex-shrink: 0; width: 1rem; height: 1rem; margin-top: 0.25rem; }
.step-content-wrapper {
  flex-grow: 1;
  min-width: 0;
  /* overflow: hidden;  <-- We are replacing this */
}

/* --- Additions for Max Height and Scrolling --- */
.step-content-wrapper {
  /* Set a maximum height. Adjust this value to your needs. */
  max-height: 500px; 

  /* 
    Allow vertical scrolling ONLY when content overflows.
    'auto' is better than 'scroll' because it hides the scrollbar
    if it's not needed.
  */
  overflow-y: auto;

  /* You might want to keep horizontal overflow hidden */
  overflow-x: hidden;

  /* --- "Beautiful Scrollbar" Styling --- */

  /* For Firefox */
  scrollbar-width: thin;
  scrollbar-color: #A9A9A9 #F1F1F1;

}

/* For Webkit browsers (Chrome, Safari, Edge, Opera) */
.step-content-wrapper::-webkit-scrollbar {
  width: 8px; /* Width of the entire scrollbar */
}

.step-content-wrapper::-webkit-scrollbar-track {
  background: #F1F1F1; /* Color of the tracking area */
  border-radius: 10px;
}

.step-content-wrapper::-webkit-scrollbar-thumb {
  background-color: #A9A9A9; /* Color of the scroll thumb */
  border-radius: 10px;       /* Roundness of the scroll thumb */
  border: 2px solid #F1F1F1; /* Creates padding around the thumb */
}

.step-content-wrapper::-webkit-scrollbar-thumb:hover {
  background-color: #555; /* Color of the thumb on hover */
}
.cm-editor-container { border: 1px solid theme('colors.gray.300'); border-radius: theme('borderRadius.lg'); }
.dark .cm-editor-container { border-color: theme('colors.gray.600'); }
.collapsed-steps-summary {
    @apply flex items-center w-full text-left p-2 space-x-2 rounded-lg
           bg-gray-100 dark:bg-gray-700/50
           border border-gray-200 dark:border-gray-700
           text-xs text-gray-600 dark:text-gray-300
           transition-colors duration-200
           hover:bg-gray-200 dark:hover:bg-gray-700;
}
.collapsed-steps-summary .step-icon {
    @apply mt-0;
}
.source-badge .similarity-chip {
    @apply w-2 h-2 rounded-full flex-shrink-0;
}
</style>