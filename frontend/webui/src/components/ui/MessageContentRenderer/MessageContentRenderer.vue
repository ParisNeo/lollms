<script setup>
import { ref, computed, watch, onMounted, nextTick, onUnmounted } from 'vue';
import { parsedMarkdown as rawParsedMarkdown, getContentTokensWithMathProtection } from '../../../services/markdownParser';
import CodeBlock from './CodeBlock.vue';
import ProcessingBlock from './ProcessingBlock.vue';
import MermaidViewer from '../../modals/InteractiveMermaid.vue';
import StepDetail from '../../chat/StepDetail.vue';
import InteractiveForm from '../../chat/InteractiveForm.vue';
import IconThinking from '../../../assets/icons/IconThinking.vue';
import IconFileText from '../../../assets/icons/IconFileText.vue';
import AuthenticatedImage from '../AuthenticatedImage.vue';
import IconArrowDownTray from '../../../assets/icons/IconArrowDownTray.vue';
import IconPhoto from '../../../assets/icons/IconPhoto.vue';
import IconPencil from '../../../assets/icons/IconPencil.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconPresentationChartBar from '../../../assets/icons/IconPresentationChartBar.vue';
import IconRefresh from '../../../assets/icons/IconRefresh.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import TaskProgressIndicator from '../TaskProgressIndicator.vue'; 
import IconMap from '../../../assets/icons/IconMap.vue';
import IconClock  from '../../../assets/icons/IconClock.vue';
import IconSave from '../../../assets/icons/IconSave.vue';
import IconWrenchScrewdriver from '../../../assets/icons/IconWrenchScrewdriver.vue';
import IconCog from '../../../assets/icons/IconCog.vue';
import IconChevronRight from '../../../assets/icons/IconChevronRight.vue';
import IconStepStart from '../../../assets/icons/IconStepStart.vue';
import IconStepEnd from '../../../assets/icons/IconStepEnd.vue';
import IconInfo from '../../../assets/icons/IconInfo.vue';
import IconError from '../../../assets/icons/IconError.vue';

import { useTasksStore } from '../../../stores/tasks';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useUiStore } from '../../../stores/ui';
import { storeToRefs } from 'pinia';
import apiClient from '../../../services/api';

const props = defineProps({
  content: { type: String, default: '' },
  sources: { type: Array, default: () => [] },
  forms: { type: Array, default: () => [] },
  events: { type: Array, default: () => [] },
  inlineWidgets: { type: Array, default: () => [] },
  isStreaming: { type: Boolean, default: false },
  isUser: { type: String, default: false },
  hasImages: { type: Boolean, default: false },
  lastUserImage: { type: String, default: null },
  messageId: { type: String, default: null },
});

const emit = defineEmits(['regenerate', 'citation-click']);

const messageContentRef = ref(null);
const tasksStore = useTasksStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const { tasks } = storeToRefs(tasksStore);
const { activeAiTasks, liveArtefactBuffers } = storeToRefs(discussionsStore);

const editingPromptIdx = ref(-1);
const editedPromptText = ref('');


/**
 * Wraps the raw widget source in a sandboxed HTML environment.
 * Includes a resize script that talks to the parent component.
 */
function wrapInIsolatedShell(source, partId) {
    if (!source) return '';
    
    const isDarkMode = uiStore.currentTheme === 'dark';
    
    return `
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            margin: 0; 
            padding: 16px; 
            font-family: system-ui, -apple-system, sans-serif; 
            overflow: hidden;
            background: ${isDarkMode ? 'transparent' : '#ffffff'};
            color: ${isDarkMode ? '#f3f4f6' : '#111827'};
        }
        /* Scoped Reset to prevent leaks */
        * { box-sizing: border-box; }
    </style>
<\/head>
<body>
    <div id="lollms-widget-root">${source}</div>
    
    <script>
        // Auto-resizer
        const sendHeight = () => {
            const height = document.documentElement.scrollHeight;
            window.parent.postMessage({ 
                type: 'lollms-widget-resize', 
                height: height,
                partId: '${partId}'
            }, '*');
        };
        
        // Watch for content changes
        const observer = new ResizeObserver(sendHeight);
        observer.observe(document.body);
        
        // Initial call
        window.onload = sendHeight;
        
        // Security: intercept link clicks to open in new tab
        document.addEventListener('click', (e) => {
            const link = e.target.closest('a');
            if (link && link.href && !link.href.startsWith('javascript:')) {
                e.preventDefault();
                window.open(link.href, '_blank');
            }
        });
    <\/script>
<\/body>
<\/html>`;
}

function handleWidgetMessage(event) {
    if (event.data?.type === 'lollms-widget-resize' && event.data.height && event.data.partId) {
        const frame = messageContentRef.value?.querySelector(`iframe[data-part-id="${event.data.partId}"]`);
        if (frame) {
            frame.style.height = (event.data.height + 10) + 'px';
        }
    }
}
function renderMath() {
  // Critical Fix: Do not mutate DOM with KaTeX while Vue is actively streaming tokens, 
  // otherwise Vue loses track of its virtual nodes and crashes.
  if (props.isStreaming) return; 

  if (messageContentRef.value && messageContentRef.value.isConnected && window.renderMathInElement) {
    // Only target specific text blocks to prevent breaking Vue child components (like CodeBlocks or StepDetails)
    const targets = messageContentRef.value.querySelectorAll('.markdown-text');
    targets.forEach(target => {
        try {
          window.renderMathInElement(target, {
            delimiters:[
              { left: '$$', right: '$$', display: true },
              { left: '\\[', right: '\\]', display: true },
              { left: '\\(', right: '\\)', display: false },
              { left: '$', right: '$', display: false }
            ],
            throwOnError: false
          });
        } catch (e) {
          console.warn("Math rendering failed or was interrupted:", e);
        }
    });
  }
}

watch(() => props.content, async () => {
  await nextTick();
  renderMath();
}, { flush: 'post' });

onMounted(async () => {
  window.addEventListener('message', handleWidgetMessage);
  await nextTick();
  renderMath();
});

onUnmounted(() => {
  window.removeEventListener('message', handleWidgetMessage);
});

const parsedMarkdown = (content) => {
  if (!content) return '';
  const mathBlocks = [];
  const placeholder = 'zZz_MATH_PLACEHOLDER_zZz';
  const sanitizedContent = content.replace(
    /(\$\$[\s\S]*?\$$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|(?<!\$)\$[^\s$](?:[\s\S]*?[^\s$])?\$(?!\$))/g,
    (match) => {
      mathBlocks.push(match);
      return placeholder;
    }
  );
  let html = rawParsedMarkdown(sanitizedContent);
  if (mathBlocks.length > 0) {
    html = html.replace(new RegExp(placeholder, 'g'), () => mathBlocks.shift());
  }
  return html;
};

const parsedStreamingContent = computed(() => {
    if (!props.content) return '';
    let content = props.content;

    // Detect technical unclosed blocks
    const blockTags = ['lollms_inline', 'lollms_widget', 'annotate', 'generate_image', 'edit_image', 'generate_slides', 'artefact'];
    let latestOpenIndex = -1;
    let detectedTag = '';

    for (const tag of blockTags) {
        const lastOpen = content.lastIndexOf(`<${tag}`);
        const lastClose = content.lastIndexOf(`</${tag}>`);
        if (lastOpen > lastClose && lastOpen > latestOpenIndex) {
            latestOpenIndex = lastOpen;
            detectedTag = tag;
        }
    }

    // 1. Technical Tag Cleanup for passive tags - keep inline for clean stream
    content = content.replace(/<(?:tol|tool_call|tool_result|thought|think)[^>]*>|<\/(?:tol|tool_call|tool_result|thought|think)>/gi, '');

    if (latestOpenIndex > -1) {
        const before = content.substring(0, latestOpenIndex);
        let statusMsg = 'Constructing...';
        
        if (detectedTag.includes('lollms')) statusMsg = 'Building Widget...';
        else if (detectedTag === 'generate_image') statusMsg = 'Generating Image...';
        else if (detectedTag === 'edit_image') statusMsg = 'Editing Image...';

        // Simple inline indicator that doesn't break text flow
        const indicator = `\n\n> ⏳ **${statusMsg}**\n\n`;
        
        return parsedMarkdown(before) + indicator;
    }

    return parsedMarkdown(content);
});

    const parseSpecialBlock = (rawBlock, match = null) => {
    if (!match) {
        // [FIX] Standardized capture groups for the monolithic parser
        const regex = /(<think>[\s\S]*?(?:<\/think>|$))|(<annotate>[\s\S]*?(?:<\/annotate>|$))|(<generate_image[^>]*>[\s\S]*?(?:<\/generate_image>|$))|(<edit_image[^>]*>[\s\S]*?(?:<\/edit_image>|$))|(<generate_slides[^>]*>[\s\S]*?(?:<\/generate_slides>|$))|(<street_view>[\s\S]*?(?:<\/street_view>|$))|(<schedule_task[^>]*>[\s\S]*?(?:<\/schedule_task>|$))|(<note[^>]*>[\s\S]*?(?:<\/note>|$))|(<skill[^>]*>[\s\S]*?(?:<\/skill>|$))|(<lollms_widget\s+id=["']([^"']+)["']\s*\/?>)|(<lollms_inline[^>]*>[\s\S]*?(?:<\/lollms_inline>|$))|(<lollms_building[^>]*\/>)|(<lollms_form_anchor\s+id=["']([^"']+)["']\s*\/?>)|(<lollms_working[^>]*\/>)|(<artefact_image\s+id=["']([^"']+)["']\s*\/?>)|(<processing\s+type=["']([^"']+)["']\s+title=["']([^"']+)["']([^>]*?)>([\s\S]*?)(?:<\/processing>|$))|(<lollms_form\s+([^>]*)>([\s\S]*?)<\/lollms_form>)|(<owl>[\s\S]*?(?:<\/owl>|$))/;
        match = regex.exec(rawBlock);
    }
    
    if (!match) return { type: 'content', content: rawBlock };

    if (match[1]) {
        const content = match[1].replace(/<think>|<\/think>/g, '').trim();
        return { type: 'think', content };
    } 
    else if (match[2]) {
        let annotateContent = match[2].replace(/<annotate>|<\/annotate>/g, '').trim();
        const jsonMatch = annotateContent.match(/(\{[\s\S]*\}|\[[\s\S]*\])/);
        if (jsonMatch) annotateContent = jsonMatch[0];
        try {
            return { type: 'annotate', annotations: JSON.parse(annotateContent) };
        } catch (e) {
            return { type: 'content', content: `[Invalid annotation data]` };
        }
    } 
    else if (match[3]) {
        const fullTag = match[3];
        const promptContent = fullTag.replace(/<generate_image[^>]*>|<\/generate_image>/g, '').trim();
        return { type: 'image_tool', mode: 'generate', prompt: promptContent, raw: fullTag };
    } 
    else if (match[4]) {
        const fullTag = match[4];
        const promptContent = fullTag.replace(/<edit_image[^>]*>|<\/edit_image>/g, '').trim();
        return { type: 'image_tool', mode: 'edit', prompt: promptContent, raw: fullTag };
    } 
    else if (match[5]) {
        const fullTag = match[5];
        const innerContent = fullTag.replace(/<generate_slides[^>]*>|<\/generate_slides>/g, '').trim();
        const slideRegex = /<Slide>(.*?)<\/Slide>/gis;
        const slides = [];
        let sMatch;
        while ((sMatch = slideRegex.exec(innerContent)) !== null) {
            slides.push(sMatch[1].trim());
        }
        return { type: 'image_tool', mode: 'slides', prompt: innerContent, slides, raw: fullTag };
    }
    else if (match[6]) {
        const fullTag = match[6];
        const location = fullTag.replace(/<street_view>|<\/street_view>/g, '').trim();
        return { type: 'image_tool', mode: 'street_view', prompt: location, raw: fullTag };
    }
    else if (match[7]) {
        const fullTag = match[7];
        const promptContent = fullTag.replace(/<schedule_task[^>]*>|<\/schedule_task>/g, '').trim();
        let name = "Task";
        const nameMatch = fullTag.match(/name="([^"]*)"/);
        if (nameMatch) name = nameMatch[1];
        return { type: 'scheduler', name, prompt: promptContent, raw: fullTag };
    }
    else if (match[8]) {
        const fullTag = match[8];
        const noteContent = fullTag.replace(/<note[^>]*>|<\/note>/g, '').trim();
        let title = "AI Note";
        const titleMatch = fullTag.match(/title="([^"]*)"/);
        if (titleMatch) title = titleMatch[1];
        return { type: 'note', title, content: noteContent, raw: fullTag };
    }
    else if (match[9]) {
        const fullTag = match[9];
        const skillContent = fullTag.replace(/<skill[^>]*>|<\/skill>/g, '').trim();
        let title = "AI Skill";
        let description = "";
        let category = "General";
        
        const titleMatch = fullTag.match(/title="([^"]*)"/);
        const descMatch = fullTag.match(/description="([^"]*)"/);
        const catMatch = fullTag.match(/category="([^"]*)"/);
        
        if (titleMatch) title = titleMatch[1];
        if (descMatch) description = descMatch[1];
        if (catMatch) category = catMatch[1];
        
        return { type: 'skill', title, description, category, content: skillContent, raw: fullTag };
    }
    else if (match[10]) {
        // --- Render standard widget anchor (id="UUID") ---
        const raw = match[10];
        const widgetId = match[11];
        
        // Look up the full source code from message metadata
        const widgetData = props.inlineWidgets?.find(w => w.id === widgetId);
        
        return { 
            type: 'interactive_widget', 
            widget: widgetData || { id: widgetId, title: 'Widget (Loading...)', is_loading: true }, 
            raw 
        };
    }
    else if (match[12]) {
        // --- Raw Inline Widget (Direct Source Mode) ---
        const fullTag = match[12];
        const matchInline = fullTag.match(/<lollms_inline[^>]*>([\s\S]*?)(?:<\/lollms_inline>|$)/);
        const innerContent = matchInline ? matchInline[1].trim() : '';
        
        const titleMatch = fullTag.match(/title=["']([^"']+)["']/);
        const title = titleMatch ? titleMatch[1] : 'Interactive Widget';
        
        // If it doesn't have a closing tag, it's still streaming
        const isLoading = !fullTag.includes('</lollms_inline>');
        
        const widgetData = { id: title, title: title, source: innerContent, is_loading: isLoading };
        return { type: 'interactive_widget', widget: widgetData, raw: fullTag };
    }
    else if (match[13] || match[16]) {
        // --- Building / Working Indicator (Merged Logic) ---
        const raw = match[13] || match[16];
        const msgMatch = raw.match(/message=["']([^"']+)["']/);
        const lblMatch = raw.match(/label=["']([^"']+)["']/);
        const label = (msgMatch && msgMatch[1]) || (lblMatch && lblMatch[1]) || 'Processing';
        
        const title = raw.match(/title=["']([^"']+)["']/)?.[1] || '';
        const sub_content = raw.match(/sub_content=["']([^"']+)["']/)?.[1] || '';
        const id = raw.match(/id=["']([^"']+)["']/)?.[1];
        
        // Determine if still active (isDone check)
        const isDone = (props.forms?.some(f => f.id === id || f.form_id === id)) || 
                       (props.inlineWidgets?.some(w => w.id === id && !w.is_loading)) ||
                       (title && discussionsStore.activeDiscussionArtefacts?.some(a => a.title === title));
                       
        return { type: 'building_indicator', label, title, sub_content, isDone, id, raw };
    }
    else if (match[14]) {
        // --- Form Anchor (Permanent mount point) ---
        const raw = match[14];
        const id = match[15];
        let formData = props.forms?.find(f => f.id === id);
        
        if (!formData && props.events) {
            const formEvent = props.events.find(e => e.type === 'form_ready' && e.content && (e.content.form_id === id || e.content.id === id || (e.content.form && e.content.form.id === id)));
            if (formEvent) {
                formData = JSON.parse(JSON.stringify(formEvent.content.form || formEvent.content));
            }
        }
        
        if (formData && props.events) {
            const submissionEvent = props.events.find(e => e.type === 'form_submitted' && e.content && e.content.form_id === id);
            if (submissionEvent) {
                formData.submitted = true;
                formData.answers = submissionEvent.content.answers;
            }
        }
        
        return { type: 'form_ready', form: formData, id, raw };
    }
    else if (match[17]) {
        // --- Artefact Image Anchor ---
        const raw = match[17];
        const fullId = match[18];
        const parts = fullId.split('::');
        return { type: 'artefact_image', title: parts[0], index: parseInt(parts[parts.length - 1]), raw };
    }
    else if (match[19]) {
        // --- NEW: Unified Processing UI Logic ---
        const raw = match[19];
        const pType = match[20];
        const title = match[21];
        const inner = match[23] || '';
        
        const isClosed = raw.trim().endsWith('</processing>');

        return { 
            type: 'processing', 
            pType, 
            title, 
            statusContent: inner, 
            isClosed, 
            raw 
        };
    }
    else if (match[27]) {
        // --- NEW: OWL/RDF Semantic Block ---
        const raw = match[27];
        const content = raw.replace(/<owl>|<\/owl>/g, '').trim();
        return { type: 'owl', content, raw };
    }
    else if (match[24]) {
        const raw = match[24];
        const attrs = match[25];
        const body = match[26];
        
        // We import the same parser logic used by the backend or a local implementation
        const parsedForm = _parse_form_xml(attrs, body);
        
        return { 
            type: 'form_ready', 
            form: parsedForm, 
            id: parsedForm.id, 
            raw 
        };
    }
    else if (match[12] || match[27]) { // <lollms_inline>
        const fullTag = match[12] || match[27];
        // Regex to extract inner content without any markdown escaping
        const innerContentMatch = fullTag.match(/<lollms_inline[^>]*>([\s\S]*?)(?:<\/lollms_inline>|$)/i);
        const innerContent = innerContentMatch ? innerContentMatch[1] : '';
        
        const titleMatch = fullTag.match(/title=["']([^"']+)["']/i);
        const title = titleMatch ? titleMatch[1] : 'Interactive Widget';
        
        const isLoading = !fullTag.includes('</lollms_inline>');
        
        return { 
            type: 'interactive_widget', 
            widget: { 
                id: title, 
                title: title, 
                source: innerContent, 
                is_loading: isLoading 
            }, 
            raw: fullTag 
        };
    }

    return { type: 'content', content: rawBlock };
};

// Helper to create a stable hash
const hashString = (str) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = (hash << 5) - hash + str.charCodeAt(i);
        hash |= 0;
    }
    return hash.toString(36);
};

// Form Parser for InteractiveForm
function _parse_form_xml(attrs_str, body) {
    // Robustly extract attributes using a non-greedy regex
    const attrs = {};
    const attrMatch = attrs_str.matchAll(/(\w+)=["']([^"']+)["']/g);
    for (const match of attrMatch) {
        attrs[match[1]] = match[2];
    }

    // Extract fields supporting self-closing and block tags (with children like <option>)
    const fieldRegex = /<field\s+([^>]*?)(?:\/>|>([\s\S]*?)<\/field>)/gi;
    const fields = [...body.matchAll(fieldRegex)].map(m => {
        const fieldAttrsStr = m[1];
        const innerContent = m[2];
        const fAttrs = {};
        const fAttrMatch = fieldAttrsStr.matchAll(/(\w+)=["']([^"']*)["']/g);
        for (const ma of fAttrMatch) {
            fAttrs[ma[1]] = ma[2];
        }
        if (innerContent) {
            const options = [...innerContent.matchAll(/<option[^>]*>([\s\S]*?)<\/option>/gi)].map(om => om[1].trim());
            if (options.length > 0) {
                fAttrs.options = options;
            }
        }
        return fAttrs;
    });

    console.log("[Form Debug] Parsed fields:", fields);
    return { 
        id: (attrs.title || 'form') + Date.now(), 
        title: attrs.title || 'Form', 
        description: attrs.description || '', 
        fields 
    };
}

// Event icon resolver for system events
const getEventIcon = (eventType) => {
    const iconMap = {
        'tool_call': IconWrenchScrewdriver,
        'step_start': IconStepStart,
        'step_end': IconStepEnd,
        'thinking': IconThinking,
        'info': IconInfo,
        'warning': IconCog, // fallback
    };
    return iconMap[eventType] || IconCog;
};

const messageParts = computed(() => {
    if (!props.content) return [];
    
    let content = props.content;
    
    // --- STREAMING SAFETY ---
    // Prevent unclosed raw HTML/SVG tags from bleeding into the parent DOM and breaking CSS.
    // We explicitly DO NOT truncate lollms_* tags here because they are handled
    // by the specialized regex and safely isolated in iframes/components.
    if (props.isStreaming) {
        const unsafeTags = ['svg', 'html', 'style', 'div', 'table'];
        let latestOpenIndex = -1;

        for (const tag of unsafeTags) {
            // Look for an opening tag
            const lastOpen = content.lastIndexOf(`<${tag}`);
            const lastClose = content.lastIndexOf(`</${tag}>`);
            
            if (lastOpen > lastClose && lastOpen > latestOpenIndex) {
                // Make sure this isn't just text inside a safe markdown code block
                const codeBlockCount = (content.substring(0, lastOpen).match(/```/g) || []).length;
                if (codeBlockCount % 2 === 0) { 
                    latestOpenIndex = lastOpen;
                }
            }
        }

        if (latestOpenIndex > -1) {
            // Truncate the content right before the unclosed tag to prevent DOM corruption
            content = content.substring(0, latestOpenIndex) + '\n\n> ⏳ *(Rendering markup...)*';
        }
    }

    const parts = [];

    // 1. Define patterns using specific, non-overlapping tags
    const patterns = [
        { type: 'code', regex: /(^\s*```(?:(\w*)\r?\n)?([\s\S]*?)^\s*```\s*?$)/gm },
        { type: 'lollms_form', regex: /<lollms_form\b([^>]*)>([\s\S]*?)<\/lollms_form>/g },
        { type: 'lollms_inline', regex: /<lollms_inline\b[^>]*\btitle=["']([^"']+)["'][^>]*>([\s\S]*?)<\/lollms_inline>/g },
        { type: 'processing', regex: /(<processing\s+type=["']([^"']*)["']\s+title=["']([^"']*)["']([^>]*?)>([\s\S]*?)(?:<\/processing>|$))/gi },
        { type: 'block_doc', regex: /--- (Document|Skill|Note):[ \t]*(.*?)[ \t]*---\s*([\s\S]*?)\s*--- End \1(?:: .*?)? ---/g },
        { type: 'artefact_image', regex: /<artefact_image\s+id=["']([^"']+)["']\s*\/?>/g }
    ];

    const allElements = [];

    // 2. Extract all elements from text patterns
    patterns.forEach(p => {
        let m;
        // Reset regex state for global searches
        p.regex.lastIndex = 0;
        while ((m = p.regex.exec(content)) !== null) {
            allElements.push({ start: m.index, end: m.index + m[0].length, raw: m[0], match: m, type: p.type });
        }
    });

    // Metadata event injection removed to ensure only tags within content are rendered

    // 4. Sort and Resolve overlaps
    allElements.sort((a, b) => (a.start - b.start) || (b.end - a.end));
    
    const activeElements = [];
    let lastEnd = 0;

    for (const el of allElements) {
        if (el.start >= lastEnd || el.type === 'form_ready') {
            activeElements.push(el);
            lastEnd = Math.max(lastEnd, el.end);
        }
    }

    // 4. Assemble final parts with strictly stable start-index IDs
    let cursor = 0;
    const renderedFormIds = new Set();
    
    // [NEW] Logic to prevent UI duplication when LLM repeats tags
    // We identify the LAST occurrence of each unique ID/Title combo 
    // and only render that one as a block.
    const lastOccurrenceMap = new Map();
    activeElements.forEach((el, index) => {
        let uniqueKey = null;
        if (el.type === 'tool') {
             const parsed = parseSpecialBlock(el.raw, el.match);
             const rawKey = parsed.id || parsed.title || parsed.prompt;
             if (rawKey) uniqueKey = `${parsed.type}-${rawKey}`;
        } else if (el.type === 'form_ready') {
             let actualForm = el.form;
             if (!actualForm && el.event && el.event.content) {
                 actualForm = el.event.content.form || el.event.content;
             }
             const rawKey = actualForm?.id || actualForm?.title || el.id;
             if (rawKey) uniqueKey = `form_ready-${rawKey}`;
        }
        if (uniqueKey) {
            lastOccurrenceMap.set(uniqueKey, index);
        }
    });

    activeElements.forEach((el, index) => {
        // Add preceding text
        if (el.start > cursor) {
            const text = content.substring(cursor, el.start);
            parts.push({ type: 'content', content: text, id: `text-${cursor}` });
        }

        // Determine if this is the chosen occurrence for this element
        let uniqueKey = null;
        if (el.type === 'tool') {
             const p = parseSpecialBlock(el.raw, el.match);
             const rawKey = p.id || p.title || p.prompt;
             if (rawKey) uniqueKey = `${p.type}-${rawKey}`;
        } else if (el.type === 'form_ready') {
             let actualForm = el.form;
             if (!actualForm && el.event && el.event.content) {
                 actualForm = el.event.content.form || el.event.content;
             }
             const rawKey = actualForm?.id || actualForm?.title || el.id;
             if (rawKey) uniqueKey = `form_ready-${rawKey}`;
        }

        const isLastOne = !uniqueKey || lastOccurrenceMap.get(uniqueKey) === index;

        // If it's not the last occurrence, render it as raw text/comment 
        // to avoid multiple big UI blocks for the same thing
        if (!isLastOne) {
            parts.push({ type: 'content', content: `\n> *(Superseded process log ignored)*\n`, id: `ignored-${el.start}` });
            cursor = Math.max(cursor, el.end);
            return;
        }

        if (el.type === 'code') {
            const lang = (el.match[2] || 'plaintext').trim();
            const inner = el.match[3];
            if (lang.toLowerCase() === 'mermaid') {
                parts.push({ type: 'mermaid', code: inner.trim(), id: `mermaid-${el.start}` });
            } else {
                parts.push({ type: 'code', lang, code: inner, id: `code-${el.start}` });
            }
        } else if (el.type === 'tool') {
            // Re-evaluate using parseSpecialBlock which handles all XML tags
            const parsed = parseSpecialBlock(el.raw, el.match);
            if (parsed.type === 'form_ready' && parsed.form) renderedFormIds.add(parsed.form.id);
            parts.push({ ...parsed, id: `${parsed.type}-${el.start}` });
        } else if (el.type === 'processing') {
            // Manually extract from el.match which comes from the simple processing regex
            // Group 1: raw, 2: type, 3: title, 4: attrs, 5: content
            parts.push({ 
                type: 'processing', 
                pType: el.match[2], 
                title: el.match[3], 
                statusContent: el.match[5], 
                isClosed: el.raw.trim().endsWith('</processing>'), 
                id: `proc-${el.start}` 
            });
        } else if (el.type === 'block_doc') {
            const subType = el.match[1].toLowerCase();
            const finalType = subType === 'skill' ? 'skill_block' : (subType === 'note' ? 'note_block' : 'document');
            parts.push({ 
                type: finalType, 
                title: (el.match[2] || 'Untitled').trim(), 
                content: el.match[3]?.trim() || '', 
                raw: el.raw,
                id: `block-${subType}-${el.start}`
            });
        } else if (el.type === 'lollms_form') {
            const parsed = _parse_form_xml(el.match[1], el.match[2]);
            parts.push({ type: 'form_ready', form: parsed, id: parsed.id });
        } else if (el.type === 'lollms_inline') {
            parts.push({ type: 'interactive_widget', widget: { title: el.match[1], source: el.match[2] }, id: `widget-${el.start}` });
        } else if (el.type === 'processing') {
            parts.push({ 
                type: 'processing', 
                pType: el.match[2], 
                title: el.match[3], 
                statusContent: el.match[5], 
                isClosed: el.raw.trim().endsWith('</processing>'), 
                id: `proc-${el.start}` 
            });
        } else if (el.type === 'artefact_image') {
            const fullId = el.match[1];
            const parts_arr = fullId.split('::');
            parts.push({
                type: 'artefact_image',
                title: parts_arr[0],
                index: parseInt(parts_arr[parts_arr.length - 1]),
                raw: el.raw,
                id: `artimg-${el.start}`
            });
        }
        // Forms handled via parsing logic inside parseSpecialBlock if <lollms_form> is in content
        cursor =  Math.max(cursor,el.end);
    });

    // Add remaining text
    if (cursor < content.length) {
        parts.push({ type: 'content', content: content.substring(cursor), id: `text-${cursor}` });
    }

    return parts;
});

// Module-level cache to prevent duplicate requests across unmounts/remounts or multiple instances
const globalResolvedArtefactImages = {};

const resolvedArtefactImages = ref({}); // 'title::index' -> 'base64'

const getTokens = (text) => {
    if (!text) return [];
    const allTokens = [];
    
    // Use \s* for more robust newline/whitespace handling
    const combinedRegex = /--- (Document|Skill|Note):[ \t]*(.*?)[ \t]*---\s*([\s\S]*?)\s*--- End \1(?:: .*?)? ---/g;
    
    let lastIndex = 0;
    let match;

    while ((match = combinedRegex.exec(text)) !== null) {
        // Add preceding segment
        if (match.index > lastIndex) {
            const markdownPart = text.substring(lastIndex, match.index);
            const tokens = getContentTokensWithMathProtection(markdownPart);
            if (Array.isArray(tokens)) {
                allTokens.push(...tokens);
            }
        }
        
        const blockType = match[1].toLowerCase();
        const title = (match[2] || 'Untitled').trim();
        const content = match[3]?.trim() || '';
        
        let finalType = 'document';
        if (blockType === 'skill') finalType = 'skill_block';
        if (blockType === 'note') finalType = 'note_block';

        // Stable key: Use hash of content + title instead of unstable match.index
        const contentHash = simpleHash(match[0]);

        allTokens.push({ 
            type: finalType, 
            title, 
            content, 
            raw: match[0],
            uid: `block-${blockType}-${contentHash}`
        });
        
        lastIndex = combinedRegex.lastIndex;
    }

    // Add remaining segment
    if (lastIndex < text.length) {
        const remaining = text.substring(lastIndex);
        const tokens = getContentTokensWithMathProtection(remaining);
        if (Array.isArray(tokens)) {
            allTokens.push(...tokens);
        }
    }

    return allTokens;
};

const activeTask = computed(() => {
    if (!props.messageId) return null;
    const discussionId = discussionsStore.currentDiscussionId;
    if (!discussionId) return null;
    const runningTasks = tasks.value.filter(t => t.status === 'running' || t.status === 'pending');
    const messageObj = discussionsStore.messages.find(m => m.id === props.messageId);
    if (messageObj?.metadata?.active_task_id) {
        const linkedTask = runningTasks.find(t => t.id === messageObj.metadata.active_task_id);
        if (linkedTask) return linkedTask;
    }
    const tracked = activeAiTasks.value[discussionId];
    if (tracked?.taskId) {
        const task = runningTasks.find(t => t.id === tracked.taskId);
        if (task && !props.isUser) return task;
    }
    return null;
});

function handleRegenerateClick(index, part) {
    if (editingPromptIdx.value === index) {
        emit('regenerate', { ...part, custom_prompt: editedPromptText.value });
        editingPromptIdx.value = -1;
    } else {
        editingPromptIdx.value = index;
        editedPromptText.value = part.prompt;
    }
}

function cancelEdit() {
    editingPromptIdx.value = -1;
}

const simpleHash = str => {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return hash;
};

function drawAnnotations(ctx, annotations, naturalWidth, naturalHeight, displayWidth) {
    if (!Array.isArray(annotations) || !ctx) return;
    annotations.forEach(ann => {
        const { box, point, polygon, class: oldLabel, label: newLabel, display } = ann;
        const scaleFactor = displayWidth > 0 ? naturalWidth / displayWidth : 1;
        const color = display?.border_color || '#FF0000';
        const lineWidth = (display?.border_width || 2) * scaleFactor;
        const fillOpacity = display?.fill_opacity !== undefined ? display.fill_opacity : 0.1;
        const showBorder = display?.show_border !== false;

        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        ctx.fillStyle = color;
        
        const text = newLabel || oldLabel || 'unknown';
        const fontSize = Math.max(12, 14 * scaleFactor);
        const padding = 4 * scaleFactor;
        ctx.font = `bold ${fontSize}px sans-serif`;
        ctx.textBaseline = 'bottom';
        
        const drawLabel = (x, y) => {
            const textMetrics = ctx.measureText(text);
            ctx.fillStyle = color;
            ctx.fillRect(x, y - fontSize - (padding * 2), textMetrics.width + (padding * 2), fontSize + (padding * 2));
            ctx.fillStyle = '#FFFFFF';
            ctx.fillText(text, x + padding, y - padding);
        };

        if (box?.length === 4) {
            const [x1, y1, x2, y2] = box;
            const absX = x1 * naturalWidth, absY = y1 * naturalHeight;
            const absW = (x2 - x1) * naturalWidth, absH = (y2 - y1) * naturalHeight;
            if (showBorder) ctx.strokeRect(absX, absY, absW, absH);
            ctx.fillStyle = `${color}${Math.round(fillOpacity * 255).toString(16).padStart(2, '0')}`;
            ctx.fillRect(absX, absY, absW, absH);
            drawLabel(absX, absY);
        } else if (polygon?.length > 1) {
            ctx.beginPath();
            polygon.forEach((p, i) => {
                if (i === 0) ctx.moveTo(p[0] * naturalWidth, p[1] * naturalHeight);
                else ctx.lineTo(p[0] * naturalWidth, p[1] * naturalHeight);
            });
            ctx.closePath();
            if (showBorder) ctx.stroke();
            ctx.fillStyle = `${color}${Math.round(fillOpacity * 255).toString(16).padStart(2, '0')}`;
            ctx.fill();
            drawLabel(polygon[0][0] * naturalWidth, polygon[0][1] * naturalHeight);
        } else if (point?.length === 2) {
            const [x, y] = point;
            const absX = x * naturalWidth, absY = y * naturalHeight;
            const radius = Math.max(3, 5 * scaleFactor);
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(absX, absY, radius, 0, 2 * Math.PI);
            ctx.fill();
            drawLabel(absX + radius, absY);
        }
    });
}

async function downloadAnnotatedImage(annotations, event) {
    const container = event.target.closest('.annotated-image-container');
    const imgElement = container?.querySelector('img');
    if (!imgElement || !annotations) return;

    const canvas = document.createElement('canvas');
    const { naturalWidth, naturalHeight } = imgElement;
    canvas.width = naturalWidth;
    canvas.height = naturalHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(imgElement, 0, 0, naturalWidth, naturalHeight);
    drawAnnotations(ctx, annotations, naturalWidth, naturalHeight, imgElement.clientWidth);

    const link = document.createElement('a');
    link.download = 'annotated_image.png';
    link.href = canvas.toDataURL('image/png');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

async function deleteArtefactImage(title, index) {
    const confirmed = await uiStore.showConfirmation({
        title: 'Delete Image/Page',
        message: `Are you sure you want to permanently delete this page/image from "${title}"? This cannot be undone.`,
        confirmText: 'Delete',
        danger: true
    });
    if (confirmed.confirmed) {
        try {
            await discussionsStore.deleteArtefactImage({
                discussionId: discussionsStore.currentDiscussionId,
                artefactTitle: title,
                imageIndex: index
            });
        } catch (e) {
            console.error(e);
        }
    }
}

function saveNoteFromRenderer(title, content) {
    uiStore.openModal('noteEditor', { title: title || 'New AI Note', content });
}

function saveSkillFromRenderer(part) {
    uiStore.openModal('skillEditor', { 
        skill: {
            name: part.title,
            description: part.description,
            category: part.category,
            content: part.content,
            language: 'markdown'
        }
    });
}

/**
 * Safely retrieves content for a widget.
 * Implements an aggressive lookup strategy directly from the inline tag.
 * Removed external buffering to ensure WYSIWYG consistency.
 */
function getWidgetContent(widgetOrPart) {
    try {
        if (!widgetOrPart) return '';
        
        const w = widgetOrPart.widget || widgetOrPart;

        // 1. Direct Content Check (From the raw string parsed in MessageContentRenderer)
        if (w.source || w.content || w.html || w.code) {
             return w.source || w.content || w.html || w.code;
        }

        // 2. Metadata/Event Log Cross-reference (Fallback for older backwards-compatible messages with UUIDs)
        const requestedId = widgetOrPart.id || w.id;
        const requestedTitle = w.title;

        if (props.inlineWidgets && props.inlineWidgets.length > 0) {
            const match = props.inlineWidgets.find(iw => iw.id === requestedId || iw.title === requestedTitle) || props.inlineWidgets[0];
            if (match) return match.source || match.content || match.html || match.code || '';
        }

        // 3. Manual Event scan
        if (props.events) {
            const event = props.events.find(e => e.type === 'widget_done' && e.content);
            if (event) return event.content.content || event.content.chunk || '';
        }
        
        return '';
    } catch (error) {
        return '';
    }
}

function openWidgetFullscreen(widget) {
    if (!widget) return;
    
    const title = widget.title || 'Interactive Widget';
    const source = getWidgetContent(widget);
    
    uiStore.openModal('interactiveOutput', {
        title: title,
        fullScreen: true,
        results: {
            [title]: {
                "html_output": source
            }
        }
    });
}



function openWidgetInNewTab(widget) {
    if (!widget) return;
    const source = getWidgetContent(widget);
    if (!source) return;

    const fullHtml = wrapInIsolatedShell(source);
    const blob = new Blob([fullHtml], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');

    setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function onImageLoad(event, annotations) {
    const img = event.target;
    if (!img || img.tagName !== 'IMG') return;
    const tryDrawing = () => {
        const container = img.closest('.annotated-image-container');
        if (!container) return;
        const canvas = container.querySelector('canvas');
        if (!canvas) return;
        const { naturalWidth, naturalHeight } = img;
        const { clientWidth: containerWidth, clientHeight: containerHeight } = container;
        if (naturalWidth === 0 || containerWidth === 0 || containerHeight === 0) return;
        canvas.width = naturalWidth;
        canvas.height = naturalHeight;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        drawAnnotations(ctx, annotations, naturalWidth, naturalHeight, img.clientWidth);
        const imgAspectRatio = naturalWidth / naturalHeight;
        const containerAspectRatio = containerWidth / containerHeight;
        if (imgAspectRatio > containerAspectRatio) {
            const scaledHeight = containerWidth / imgAspectRatio;
            const verticalMargin = (containerHeight - scaledHeight) / 2;
            Object.assign(canvas.style, { top: `${verticalMargin}px`, left: '0px', width: `${containerWidth}px`, height: `${scaledHeight}px` });
        } else {
            const scaledWidth = containerHeight * imgAspectRatio;
            const horizontalMargin = (containerHeight - scaledWidth) / 2;
            Object.assign(canvas.style, { left: `${horizontalMargin}px`, top: '0px', width: `${scaledWidth}px`, height: `${containerHeight}px` });
        }
    };
    requestAnimationFrame(tryDrawing);
}

function handleSourceClick(source, idx) {
    // Open modal directly when clicking items in the bottom list
    uiStore.openModal('sourceViewer', {
        title: source.title || source.name || `Source [${source.index || idx + 1}]`,
        content: source.content || source.chunk_text || source.text || '',
        source: source.source || source.url || '',
        score: source.relevance_score || source.score || 0,
        metadata: source.metadata || {}
    });
}

// Auto-size mermaid containers based on rendered SVG natural height
function onMermaidReady({ svg }, partIndex) {
    nextTick(() => {
        try {
            const viewBox = svg.getAttribute('viewBox');
            if (!viewBox) return;
            const [, , , vbHeight] = viewBox.split(' ').map(Number);
            if (!vbHeight || vbHeight <= 0) return;
            // Find the wrapper div for this part and set its height
            // Add padding for toolbar (48px) + some breathing room
            const minH = 300, maxH = 1200;
            const targetH = Math.min(maxH, Math.max(minH, vbHeight + 80));
            const wrappers = messageContentRef.value?.querySelectorAll('.mermaid-wrapper');
            if (wrappers && wrappers[partIndex]) {
                wrappers[partIndex].style.height = `${targetH}px`;
            }
        } catch (e) { /* ignore */ }
    });
}
</script>

<template>
  <div ref="messageContentRef">
    <div v-if="content || (isUser && !hasImages)" class="message-prose">
      <template v-if="messageParts.length > 0">
        <template v-for="part in messageParts" :key="part.id">
          <!-- ── Mermaid diagram ─────────────────────────────────────────── -->
          <div v-if="part.type === 'mermaid'" class="my-4 rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700 shadow-sm mermaid-wrapper">
            <MermaidViewer 
              :mermaid-code="part.code" 
              :message-id="messageId"
              @ready="onMermaidReady($event, index)" 
            />
          </div>
        <!-- Book Artefact Rendering -->
        <div v-else-if="part.type === 'artefact' && part.meta.type === 'book'" class="book-artefact-container my-6">
            <div class="book-frame bg-white dark:bg-slate-50 text-slate-900 p-8 sm:p-12 shadow-2xl rounded-sm border-l-8 border-slate-300 dark:border-slate-400 mx-auto max-w-3xl overflow-hidden relative">
                <div class="book-content prose prose-slate max-w-none" v-html="part.content"></div>
                <div class="absolute bottom-4 right-8 text-[10px] font-serif italic text-slate-400">LoLLMs Digital Edition</div>
            </div>
            <div class="flex justify-center mt-4">
                <button @click="$emit('export', { format: 'pdf', content: part.content, title: part.meta.title })" class="btn btn-secondary btn-xs gap-2">
                    <IconArrowDownTray class="w-3 h-3" /> Download as PDF
                </button>
            </div>
        </div>
          <div v-else-if="part.type === 'content'" class="content-token-container">
            <template v-for="(token, tokenIndex) in (getTokens(part.content) || [])" :key="token.uid || `token-${tokenIndex}`">
              <CodeBlock v-if="token.type === 'code'" :language="token.lang" :code="token.text" :message-id="messageId" />
              
              <details v-else-if="token.type === 'document'" class="document-block my-4 group/block">
                  <summary class="document-summary flex items-center justify-between pr-2">
                      <div class="flex items-center gap-2 overflow-hidden">
                        <IconFileText class="w-4 h-4 text-gray-600 dark:text-gray-400 shrink-0" />
                        <span class="font-mono truncate">{{ token.title }}</span>
                      </div>
                      <button @click.stop="discussionsStore.removeContextItem(token.title, 'document')" class="opacity-0 group-hover/block:opacity-100 p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500 transition-opacity" title="Remove from context">
                        <IconTrash class="w-3.5 h-3.5" />
                      </button>
                  </summary>
                  <div class="document-content p-4 prose prose-sm dark:prose-invert max-w-none">
                    <iframe 
                        v-if="token.content.includes('<html') || token.content.includes('<!DOCTYPE')"
                        :srcdoc="token.content"
                        class="w-full h-[500px] border-none"
                        sandbox="allow-scripts"
                    ></iframe>
                    <div v-else v-html="parsedMarkdown(token.content)"></div>
                  </div>
              </details>
              
              <details v-else-if="token.type === 'skill_block'" class="skill-block my-4 group/block">
                  <!-- ... -->
              </details>
              
              <details v-else-if="token.type === 'note_block'" class="note-block-collapsible my-4 group/block">
                  <!-- ... -->
              </details>
              
              <div v-else-if="token.raw" class="markdown-text" v-html="parsedMarkdown(token.raw)"></div>
            </template>
          </div>

          <!-- ── Explicit code block (non-mermaid) ──────────────────────── -->
          <template v-else-if="part.type === 'code'">
            <CodeBlock :language="part.lang" :code="part.code" :message-id="messageId" />
          </template>

          <details v-else-if="part.type === 'think'" class="think-block my-4" open>
            <summary class="think-summary">
              <IconThinking class="h-5 w-5 shrink-0" />
              <span>Thinking...</span>
            </summary>
            <div class="think-content" v-html="parsedMarkdown(part.content)"></div>
          </details>

          <div v-else-if="part.type === 'image_tool'" class="my-4 p-4 rounded-xl border-2 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/50 shadow-sm">
             <div class="flex items-center justify-between mb-4">
                 <div class="flex items-center gap-2">
                     <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400">
                         <IconPencil v-if="part.mode === 'edit'" class="w-5 h-5" />
                         <IconPresentationChartBar v-else-if="part.mode === 'slides'" class="w-5 h-5" />
                         <IconMap v-else-if="part.mode === 'street_view'" class="w-5 h-5 text-amber-500" />
                         <IconPhoto v-else class="w-5 h-5" />
                     </div>
                     <div class="flex flex-col">
                        <span class="text-[10px] font-black uppercase tracking-widest text-gray-500 dark:text-gray-400 leading-none mb-1">
                            <template v-if="part.mode === 'edit'">Image Edit</template>
                            <template v-else-if="part.mode === 'slides'">Slide Deck</template>
                            <template v-else-if="part.mode === 'street_view'">Street View</template>
                            <template v-else>Image Generation</template>
                        </span>
                        <span class="text-sm font-bold text-gray-800 dark:text-gray-200">AI Request Block</span>
                     </div>
                 </div>
                 <div class="flex items-center gap-1">
                    <button v-if="editingPromptIdx === index" @click="cancelEdit" class="btn-icon-sm" title="Cancel">
                        <IconRefresh class="w-4 h-4 transform rotate-45 text-red-500" />
                    </button>
                    <button @click="handleRegenerateClick(index, part)" class="btn btn-sm" :class="editingPromptIdx === index ? 'btn-primary' : 'btn-secondary'" title="Regenerate">
                        <IconCheckCircle v-if="editingPromptIdx === index" class="w-4 h-4 mr-1.5" />
                        <IconRefresh v-else class="w-4 h-4 mr-1.5" />
                        <span>{{ editingPromptIdx === index ? 'Submit' : 'Regenerate' }}</span>
                    </button>
                 </div>
             </div>
             <div v-if="activeTask" class="mb-4">
                <TaskProgressIndicator :task="activeTask" class="text-xs" />
             </div>
             <div v-if="editingPromptIdx === index" class="space-y-3 animate-in fade-in slide-in-from-top-2">
                <p class="text-[10px] font-bold text-blue-500 uppercase tracking-wide">Customize Prompt:</p>
                <textarea 
                    v-model="editedPromptText" 
                    rows="4" 
                    class="input-field w-full text-sm font-medium h-32 resize-y" 
                    placeholder="Enter customized generation prompt..."
                    @keyup.esc="cancelEdit"
                ></textarea>
                <p class="text-[10px] text-gray-500 italic">This will generate a new variant using the updated prompt.</p>
             </div>
             <div v-else class="relative group/prompt">
                 <div v-if="part.mode === 'street_view'" class="text-sm font-medium text-gray-800 dark:text-gray-200">
                    Fetching view for: <span class="font-bold">{{ part.prompt }}</span>
                 </div>
                 <template v-else>
                    <div v-if="part.slides && part.slides.length > 0" class="mt-2 pl-4 border-l-2 border-purple-200 dark:border-purple-800">
                        <div v-for="(slide, i) in part.slides" :key="i" class="text-xs text-gray-600 dark:text-gray-300 mb-1">
                            <span class="font-bold mr-1">{{ i + 1 }}.</span> {{ slide }}
                        </div>
                    </div>
                    <div v-else class="text-sm font-medium text-gray-800 dark:text-gray-200 italic line-clamp-4 group-hover/prompt:line-clamp-none transition-all">
                        "{{ part.prompt }}"
                    </div>
                 </template>
             </div>
          </div>

          <div v-else-if="part.type === 'scheduler'" class="my-4 p-4 rounded-xl border-2 border-indigo-200 dark:border-indigo-800 bg-indigo-50/50 dark:bg-indigo-900/20 shadow-sm">
             <div class="flex items-center gap-3">
                 <div class="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-900/50 text-indigo-600 dark:text-indigo-400">
                     <IconClock class="w-6 h-6" />
                 </div>
                 <div class="flex flex-col">
                    <span class="text-[10px] font-black uppercase tracking-widest text-indigo-500 dark:text-indigo-300 leading-none mb-1">Scheduled Task</span>
                    <span class="text-sm font-bold text-gray-800 dark:text-gray-200">{{ part.name }}</span>
                    <span class="text-xs text-gray-600 dark:text-gray-400 italic mt-1">"{{ part.prompt }}"</span>
                 </div>
             </div>
          </div>

          <!-- ── Note block ──────────────────────────────────────────────── -->
          <details v-else-if="part.type === 'note'" class="note-block my-4 rounded-xl overflow-hidden shadow-md border border-amber-200 dark:border-amber-800/60" open>
            <!-- [NEW] Live Status Pulse for secondary stream -->
            <div v-if="discussionsStore.liveArtefactBuffers[part.title] !== undefined" class="absolute top-0 right-0 p-1">
                <span class="flex h-2 w-2">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                </span>
            </div>
            <!-- Header bar as Summary -->
            <summary class="note-header flex items-center justify-between px-4 py-2.5 bg-amber-50 dark:bg-amber-900/30 border-amber-200 dark:border-amber-800/60 cursor-pointer list-none select-none">
              <div class="flex items-center gap-2.5">
                <IconChevronRight class="w-3 h-3 text-amber-500 transition-transform duration-200 summary-arrow" />
                <!-- Notepad icon -->
                <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
                <div class="flex flex-col leading-tight">
                  <span class="text-[9px] font-black uppercase tracking-widest text-amber-500 dark:text-amber-400">AI Note</span>
                  <span class="text-sm font-bold text-gray-800 dark:text-gray-100">{{ part.title }}</span>
                </div>
              </div>
              <!-- Save button (stop propagation to prevent toggle on button click) -->
              <button
                @click.stop="saveNoteFromRenderer(part.title, part.content)"
                class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-500 hover:bg-amber-600 text-white shadow-sm transition-colors"
                title="Save this note"
              >
                <IconSave class="w-3.5 h-3.5" />
                Save Note
              </button>
            </summary>
            <!-- Note content — token-aware so code blocks get syntax highlighting -->
            <div class="note-body px-5 py-4 bg-amber-50/40 dark:bg-amber-950/20 border-t border-amber-200 dark:border-amber-800/60">
              <div class="note-content prose prose-sm dark:prose-invert max-w-none text-gray-800 dark:text-gray-200">
                <template v-for="(token, ti) in getTokens(discussionsStore.liveArtefactBuffers[part.title] || part.content)" :key="`note-token-${ti}`">
                  <CodeBlock v-if="token.type === 'code'" :language="token.lang" :code="token.text" :message-id="messageId" />
                  <div v-else v-html="parsedMarkdown(token.raw)"></div>
                </template>
              </div>
            </div>
          </details>

          <!-- ── Skill block ──────────────────────────────────────────────── -->
          <details v-else-if="part.type === 'skill'" class="note-block my-4 rounded-xl overflow-hidden shadow-md border border-teal-200 dark:border-teal-800/60" open>
            <!-- [NEW] Live Status Pulse -->
            <div v-if="discussionsStore.liveArtefactBuffers[part.title] !== undefined" class="absolute top-0 right-0 p-1">
                <span class="flex h-2 w-2">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-2 w-2 bg-teal-500"></span>
                </span>
            </div>
            <summary class="note-header flex items-center justify-between px-4 py-2.5 bg-teal-50 dark:bg-teal-900/30 border-teal-200 dark:border-teal-800/60 cursor-pointer list-none select-none">
              <div class="flex items-center gap-2.5">
                <IconChevronRight class="w-3 h-3 text-teal-500 transition-transform duration-200 summary-arrow" />
                <IconSparkles class="w-4 h-4 text-teal-600 dark:text-teal-400 shrink-0" />
                <div class="flex flex-col leading-tight">
                  <span class="text-[9px] font-black uppercase tracking-widest text-teal-500 dark:text-teal-400">AI Skill Proposal</span>
                  <span class="text-sm font-bold text-gray-800 dark:text-gray-100">{{ part.title }}</span>
                </div>
              </div>
              <button
                @click.stop="saveSkillFromRenderer(part)"
                class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-teal-500 hover:bg-teal-600 text-white shadow-sm transition-colors"
              >
                <IconSave class="w-3.5 h-3.5" />
                Validate Skill
              </button>
            </summary>
            <div class="note-body px-5 py-4 bg-teal-50/40 dark:bg-amber-950/20 border-t border-teal-200 dark:border-teal-800/60">
               <div v-if="part.description" class="text-xs text-gray-500 dark:text-gray-400 italic mb-2">{{ part.description }}</div>
              <div class="note-content prose prose-sm dark:prose-invert max-w-none text-gray-800 dark:text-gray-200">
                <template v-for="(token, ti) in getTokens(discussionsStore.liveArtefactBuffers[part.title] || part.content)" :key="`skill-token-${ti}`">
                  <CodeBlock v-if="token.type === 'code'" :language="token.lang" :code="token.text" :message-id="messageId" />
                  <div v-else v-html="parsedMarkdown(token.raw)"></div>
                </template>
              </div>
            </div>
          </details>

          <template v-else-if="part.type === 'annotate'">
            <div class="annotated-image-container relative my-4 group">
                <AuthenticatedImage v-if="lastUserImage" :src="lastUserImage" @load="onImageLoad($event, part.annotations)"/>
                <p v-else class="text-red-500 text-sm">Could not find a previous image to annotate.</p>
                <canvas class="absolute pointer-events-none"></canvas>
                <div class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button @click="downloadAnnotatedImage(part.annotations, $event)" class="p-1.5 bg-black/50 text-white rounded-full hover:bg-black/80" title="Download Annotated Image">
                        <IconArrowDownTray class="w-4 h-4" />
                    </button>
                </div>
            </div>
          </template>

          <!-- ── New Unified Processing Component ───────────────────────────── -->
          <ProcessingBlock 
               v-else-if="part.type === 'processing'"
               :p-type="part.pType"
               :title="part.title"
               :status-content="part.statusContent"
               :is-closed="part.isClosed"
          />

          <!-- Forms no longer rendered here as they must be embedded in content -->

          <!-- ── OWL Visualization ───────────────────────────────────────── -->
          <div v-else-if="part.type === 'owl'" class="my-6 border-2 border-indigo-500 rounded-2xl overflow-hidden bg-white dark:bg-gray-950 shadow-xl">
              <div class="px-4 py-2 bg-indigo-600 text-white flex justify-between items-center">
                  <span class="text-[10px] font-black uppercase tracking-widest">Semantic OWL Visualizer</span>
                  <button @click="uiStore.copyToClipboard(part.content)" class="hover:text-indigo-200"><IconCopy class="w-4 h-4"/></button>
              </div>
              <div class="h-[400px] relative">
                  <InteractiveGraphViewer 
                      :nodes="[]" 
                      :edges="[]" 
                      :is-loading="false"
                      :owl-source="part.content" 
                  />
              </div>
          </div>

          <!-- ── OWL Visualization ───────────────────────────────────────── -->
          <div v-else-if="part.type === 'owl'" class="my-6 border-2 border-indigo-500 rounded-2xl overflow-hidden bg-white dark:bg-gray-950 shadow-xl">
              <div class="px-4 py-2 bg-indigo-600 text-white flex justify-between items-center">
                  <span class="text-[10px] font-black uppercase tracking-widest">Semantic OWL Visualizer</span>
                  <button @click="uiStore.copyToClipboard(part.content)" class="hover:text-indigo-200"><IconCopy class="w-4 h-4"/></button>
              </div>
              <div class="h-[400px] relative">
                  <InteractiveGraphViewer 
                      :nodes="[]" 
                      :edges="[]" 
                      :is-loading="false"
                      :owl-source="part.content" 
                  />
              </div>
          </div>

          <!-- ── Interactive Form ────────────────────────────────────────── -->
          <template v-else-if="part.type === 'form_ready'">
             <div class="my-4 p-4 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 shadow-sm">
                <InteractiveForm 
                    :form="part.form" 
                    :discussion-id="discussionsStore.currentDiscussionId"
                />
             </div>
          </template>

          <!-- ── Interactive Widget ──────────────────────────────────────── -->
          <template v-else-if="part.type === 'interactive_widget'">
             <div class="my-4 border rounded-lg p-4 bg-gray-50 dark:bg-gray-800">
                <h4 class="font-bold text-sm mb-2">{{ part.widget.title }}</h4>
                <div v-html="part.widget.source"></div>
             </div>
          </template>

          <!-- ── Artefact Image Resolution ───────────────────────────────── -->
          <div v-else-if="part.type === 'artefact_image'" class="my-6 artefact-image-mount">
             <div class="rounded-2xl border-2 border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 overflow-hidden shadow-lg group">
                  <div class="relative">
                      <AuthenticatedImage 
                          :src="`/api/discussions/${discussionsStore.currentDiscussionId}/artefacts/${encodeURIComponent(part.title)}/images/${part.index}`" 
                          class="w-full h-auto max-h-[600px] object-contain mx-auto"
                      />
                      <!-- Actions Overlay / Delete Button -->
                      <div class="absolute inset-0 bg-black/10 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3 z-10">
                          <button @click="deleteArtefactImage(part.title, part.index)" class="p-3 bg-red-600 hover:bg-red-700 text-white rounded-full shadow-lg transition-all active:scale-95 cursor-pointer" title="Delete this page/image">
                              <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                          </button>
                      </div>
                      <!-- Overlay Title -->
                      <div class="absolute bottom-0 inset-x-0 p-3 bg-black/40 backdrop-blur-md opacity-0 group-hover:opacity-100 transition-opacity">
                           <span class="text-[10px] font-black uppercase tracking-widest text-white">{{ part.title }} — Page {{ part.index + 1 }}</span>
                      </div>
                  </div>
             </div>
          </div>

          <!-- ── Interactive Teaching Widget (Inline Preview Mode) ─────────── -->
          <div v-else-if="part.type === 'interactive_widget' && part.widget" 
               class="my-4 group/widget-container clear-both isolation-auto">
              <div class="rounded-2xl border-2 border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-hidden shadow-xl transition-all hover:border-blue-500/20">
                  
                  <!-- Preview Header -->
                  <div class="px-4 py-2.5 border-b dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50 flex items-center justify-between">
                      <div class="flex items-center gap-3 min-w-0">
                          <div class="p-1.5 rounded-lg bg-blue-100 dark:bg-blue-900/40 text-blue-600">
                              <IconAnimateSpin v-if="part.widget.is_loading" class="w-4 h-4 animate-spin" />
                              <IconCpuChip v-else class="w-4 h-4" />
                          </div>
                          <div class="flex flex-col min-w-0">
                              <span class="text-[9px] font-black uppercase tracking-widest text-gray-400 leading-none mb-1">Sandbox Preview</span>
                              <h4 class="text-xs font-bold text-gray-700 dark:text-gray-200 truncate">{{ part.widget.title || 'Interactive Component' }}</h4>
                          </div>
                      </div>

                      <div v-if="!part.widget.is_loading" class="flex items-center gap-1">
                          <button 
                            @click="openWidgetFullscreen(part.widget)"
                            class="p-1.5 rounded-lg hover:bg-blue-500 hover:text-white text-gray-400 transition-all"
                            title="Full Screen View"
                          >
                              <IconMaximize class="w-3.5 h-3.5" />
                          </button>
                          <button 
                            @click="openWidgetInNewTab(part.widget)"
                            class="p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 transition-all"
                            title="Open in New Tab"
                          >
                              <IconGlobeAlt class="w-3.5 h-3.5" />
                          </button>
                      </div>
                  </div>
                  
                  <!-- Inline Iframe Viewport -->
                  <div class="relative w-full bg-white transition-all overflow-hidden border-b dark:border-gray-800" style="min-height: 100px;">
                      <iframe 
                        v-if="getWidgetContent(part.widget)"
                        :data-part-id="part.id"
                        :key="`${part.id}-${isStreaming ? 'live' : 'stable'}`"
                        :srcdoc="wrapInIsolatedShell(getWidgetContent(part.widget), part.id)" 
                        class="w-full border-none pointer-events-auto bg-white transition-[height] duration-300" 
                        style="height: 400px;"
                        sandbox="allow-scripts allow-same-origin allow-popups allow-forms allow-modals" 
                        referrerpolicy="no-referrer"
                      ></iframe>
                      
                      <!-- Loading Placeholder: Show only if both static content and live buffer are empty -->
                      <div v-else class="absolute inset-0 flex flex-col items-center justify-center bg-gray-50/50 dark:bg-gray-900/50">
                         <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin mb-3 opacity-30" />
                         <p class="text-[10px] font-black uppercase text-gray-400 tracking-widest">Awaiting source data...</p>
                      </div>
                  </div>

                  <!-- Footer / Status -->
                  <div class="px-4 py-2 bg-gray-50/30 dark:bg-gray-900/20 flex items-center justify-between border-t dark:border-gray-800">
                       <div class="flex items-center gap-2">
                          <div class="w-1.5 h-1.5 rounded-full" :class="part.widget.is_loading ? 'bg-gray-400' : 'bg-green-500 animate-pulse'"></div>
                          <span class="text-[9px] font-bold text-gray-400 uppercase tracking-tighter">{{ part.widget.is_loading ? 'Preparing Environment' : 'Sandbox Ready' }}</span>
                       </div>
                       <button v-if="!part.widget.is_loading" @click="openWidgetFullscreen(part.widget)" class="text-[9px] font-black text-blue-500 uppercase tracking-widest hover:underline">
                           Launch Visualizer &rarr;
                       </button>
                  </div>
              </div>
          </div>

        </template>

        <!-- ── [NEW] Live Active Event Indicator ──────────────────────── -->
        <div v-if="isStreaming && $attrs.message?.lastEvent" class="mt-4 animate-in fade-in slide-in-from-bottom-1">
             <div class="flex items-center gap-3 p-3 rounded-xl bg-blue-50/50 dark:bg-blue-900/10 border border-blue-100/50 dark:border-blue-800/30">
                  <div class="relative shrink-0">
                      <IconAnimateSpin class="w-5 h-5 text-blue-500 animate-spin" />
                      <div class="absolute inset-0 flex items-center justify-center">
                          <component :is="getEventIcon($attrs.message.lastEvent.type)" class="w-2.5 h-2.5 text-blue-600" />
                      </div>
                  </div>
                  <div class="flex flex-col min-w-0">
                      <span class="text-[9px] font-black uppercase tracking-widest text-blue-500/60 leading-none mb-1">Active Step</span>
                      <span class="text-xs font-bold text-gray-700 dark:text-gray-300 truncate">
                          {{ $attrs.message.lastEvent.content?.name || $attrs.message.lastEvent.content || 'Thinking...' }}
                      </span>
                  </div>
             </div>
        </div>
      </template>
    </div>
  </div>
</template>