<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue';
import { parsedMarkdown as rawParsedMarkdown, getContentTokensWithMathProtection } from '../../../services/markdownParser';

import CodeBlock from './CodeBlock.vue';
import MermaidViewer from '../../modals/InteractiveMermaid.vue';
import StepDetail from '../../chat/StepDetail.vue';
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
import IconClock from '../../../assets/icons/IconClock.vue';
import IconSave from '../../../assets/icons/IconSave.vue';
import IconWrenchScrewdriver from '../../../assets/icons/IconWrenchScrewdriver.vue';
import IconCog from '../../../assets/icons/IconCog.vue';
import IconInfo from '../../../assets/icons/IconInfo.vue';
import IconError from '../../../assets/icons/IconError.vue';
import IconChevronRight from '../../../assets/icons/IconChevronRight.vue';

import { useTasksStore } from '../../../stores/tasks';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useUiStore } from '../../../stores/ui';
import { storeToRefs } from 'pinia';

const props = defineProps({
  content: { type: String, default: '' },
  events: { type: Array, default: () => [] },
  inlineWidgets: { type: Array, default: () => [] }, // Prop for persistent widgets
  isStreaming: { type: Boolean, default: false },
  isUser: { type: Boolean, default: false },
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
const { activeAiTasks } = storeToRefs(discussionsStore);

const editingPromptIdx = ref(-1);
const editedPromptText = ref('');

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
  await nextTick();
  renderMath();
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

    // 1. Technical Tag Cleanup (remove tags but not content for simple markers)
    content = content.replace(/<(?:tol|tool_call|tool_result|thought|think)[^>]*>|<\/(?:tol|tool_call|tool_result|thought|think)>/gi, '');
    
    // 2. Block Hiding (Hide tags AND everything inside them during streaming)
    // We search for the last occurrence of a block tag that hasn't been closed yet
    const blockTags = ['lollms_inline', 'annotate', 'generate_image', 'edit_image', 'generate_slides', 'artefact'];
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

    if (latestOpenIndex > -1) {
        const before = content.substring(0, latestOpenIndex);
        let statusMsg = 'Processing...';
        let colorClass = 'bg-gray-50 border-gray-200 text-gray-800 dark:bg-gray-900/40 dark:border-gray-800/30 dark:text-gray-200';

        if (detectedTag === 'lollms_inline') {
            statusMsg = 'Building interactive component...';
            colorClass = 'bg-indigo-50 border-indigo-200 text-indigo-800 dark:bg-indigo-900/40 dark:border-indigo-800/30 dark:text-indigo-200';
        } else if (detectedTag === 'annotate') {
            statusMsg = 'Annotating image...';
            colorClass = 'bg-blue-50 border-blue-200 text-blue-800 dark:bg-blue-900/40 dark:border-blue-800/30 dark:text-blue-200';
        } else if (detectedTag === 'generate_image' || detectedTag === 'edit_image') {
            statusMsg = detectedTag === 'edit_image' ? 'Editing image...' : 'Generating image...';
            colorClass = 'bg-purple-50 border-purple-200 text-purple-800 dark:bg-purple-900/40 dark:border-purple-800/30 dark:text-purple-200';
        }

        const spinnerHtml = `<div class="flex items-center gap-2 my-4 p-3 ${colorClass} border rounded-xl text-sm font-bold animate-in fade-in zoom-in-95 duration-300">
            <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
            <span>${statusMsg}</span>
        </div>`;
        
        return parsedMarkdown(before) + spinnerHtml;
    }

    return parsedMarkdown(content);
});

const parseSpecialBlock = (rawBlock, match = null) => {
    if (!match) {
        // [FIX] Unified regex for special blocks - capture widget id attribute
        const regex = /(<think>[\s\S]*?(?:<\/think>|$))|(<annotate>[\s\S]*?(?:<\/annotate>|$))|(<generate_image[^>]*>[\s\S]*?(?:<\/generate_image>|$))|(<edit_image[^>]*>[\s\S]*?(?:<\/edit_image>|$))|(<generate_slides[^>]*>[\s\S]*?(?:<\/generate_slides>|$))|(<street_view>[\s\S]*?(?:<\/street_view>|$))|(<schedule_task[^>]*>[\s\S]*?(?:<\/schedule_task>|$))|(<note[^>]*>[\s\S]*?(?:<\/note>|$))|(<skill[^>]*>[\s\S]*?(?:<\/skill>|$))|(<lollms_widget\s+id=["']([^"']+)["']\s*\/?>)/;
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
        // [FIXED] Enhanced Interactive Widget Anchor Logic
        const raw = match[10];
        let widgetId = match[11]; 
        
        // Secondary extraction if group 11 is empty but tag is present
        if (!widgetId && raw.includes('id=')) {
            const idMatch = raw.match(/id=["']([^"']+)["']/);
            if (idMatch) widgetId = idMatch[1];
        }
        
        if (raw.includes('<lollms_widget')) {
            const widgetData = props.inlineWidgets?.find(w => w.id === widgetId);
            if (!widgetData) {
                console.warn(`[WidgetRenderer] No source found in metadata for ID: ${widgetId}`);
            }
            return { type: 'interactive_widget', widget: widgetData, raw };
        }
        
        const eventData = props.events?.find(e => e.id === widgetId);
        return { type: 'inline_event', event: eventData, raw };
    }

    return { type: 'content', content: rawBlock };
};

// Helper to create a stable hash for a string to use as a key
const hashString = (str) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = (hash << 5) - hash + str.charCodeAt(i);
        hash |= 0;
    }
    return hash.toString(36);
};

const initEvents = computed(() => {
    // Only show events that happened before or at the start of text (offset <= 0 or missing)
    return (props.events || []).filter(e => !e.offset || e.offset <= 0);
});

const messageParts = computed(() => {
    if (!props.content) return [];
    
    const content = props.content;
    const parts = [];

    // 1. Define all detectable patterns
    const patterns = [
        { type: 'code', regex: /(^\s*```(?:(\w*)\r?\n)?([\s\S]*?)^\s*```\s*?$)/gm },
        // [FIX] Synchronized regex to ensure Widget ID (group 11) is captured for the renderer
        { type: 'tool', regex: /(<think>[\s\S]*?(?:<\/think>|$))|(<annotate>[\s\S]*?(?:<\/annotate>|$))|(<generate_image[^>]*>[\s\S]*?(?:<\/generate_image>|$))|(<edit_image[^>]*>[\s\S]*?(?:<\/edit_image>|$))|(<generate_slides[^>]*>[\s\S]*?(?:<\/generate_slides>|$))|(<street_view>[\s\S]*?(?:<\/street_view>|$))|(<schedule_task[^>]*>[\s\S]*?(?:<\/schedule_task>|$))|(<note[^>]*>[\s\S]*?(?:<\/note>|$))|(<skill[^>]*>[\s\S]*?(?:<\/skill>|$))|(<lollms_widget\s+id=["']([^"']+)["']\s*\/?>)/g },
        { type: 'block_doc', regex: /--- (Document|Skill|Note):[ \t]*(.*?)[ \t]*---\s*([\s\S]*?)\s*--- End \1(?:: .*?)? ---/g }
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

    // 3. Extract elements from out-of-band Events (Tool calls, System steps)
    // REMOVED: System events are now rendered exclusively in the top timeline block,
    // not interleaved in the messageParts loop. This prevents redundancy.

    // 4. Sort and Resolve overlaps
    allElements.sort((a, b) => (a.start - b.start) || (b.end - a.end));
    
    const activeElements = [];
    let lastEnd = 0;

    for (const el of allElements) {
        if (el.start >= lastEnd || el.type === 'system_event') {
            activeElements.push(el);
            lastEnd = el.end;
        }
    }

    // 4. Assemble final parts with strictly stable start-index IDs
    let cursor = 0;
    activeElements.forEach(el => {
        // Add preceding text
        if (el.start > cursor) {
            const text = content.substring(cursor, el.start);
            parts.push({ type: 'content', content: text, id: `text-${cursor}` });
        }

        if (el.type === 'system_event') {
            parts.push({ type: 'system_event', event: el.event, id: `event-${el.event.id || el.start}` });
        } else if (el.type === 'code') {
            const lang = (el.match[2] || 'plaintext').trim();
            const inner = el.match[3];
            if (lang.toLowerCase() === 'mermaid') {
                parts.push({ type: 'mermaid', code: inner.trim(), id: `mermaid-${el.start}` });
            } else {
                parts.push({ type: 'code', lang, code: inner, id: `code-${el.start}` });
            }
        } else if (el.type === 'tool') {
            const parsed = parseSpecialBlock(el.raw, el.match);
            parts.push({ ...parsed, id: `${parsed.type}-${el.start}` });
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
        }
        cursor =  Math.max(cursor,el.end);
    });

    // Add remaining text
    if (cursor < content.length) {
        parts.push({ type: 'content', content: content.substring(cursor), id: `text-${cursor}` });
    }

    return parts;
});

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

function handleContentClick(event) {
    const btn = event.target.closest('.citation-btn');
    if (btn) {
        const index = parseInt(btn.dataset.index);
        if (index) {
            // Find the source object for this index
            const source = props.sources?.find(s => s.index === index) || props.sources?.[index - 1];
            if (source) {
                // Open the modal directly for better accessibility from the text
                uiStore.openModal('sourceViewer', {
                    title: source.title || source.name || `Source [${index}]`,
                    content: source.content || source.chunk_text || source.text || '',
                    source: source.source || source.url || '',
                    score: source.relevance_score || source.score || 0,
                    metadata: source.metadata || {}
                });
            }
        }
    }
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
  <div ref="messageContentRef" @click="handleContentClick">
    <div v-if="content || (isUser && !hasImages)" class="message-prose">
      <template v-if="messageParts.length > 0">
        <template v-for="part in messageParts" :key="part.id">
          
          <!-- ── Mermaid diagram ─────────────────────────────────────────── -->

          <!-- ── Initialization Logs (Only events with offset 0) ──────────────── -->
          <div v-if="initEvents.length > 0" class="mb-4">
              <details class="group timeline-details overflow-hidden rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50/20 dark:bg-gray-900/10">
                  <summary class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors list-none select-none">
                      <div class="flex items-center gap-2">
                          <IconCog class="w-3.5 h-3.5 text-gray-400" />
                          <span class="text-[10px] font-black uppercase tracking-widest text-gray-500">System Initialization</span>
                      </div>
                      <IconChevronRight class="w-3 h-3 text-gray-400 group-open:rotate-90 transition-transform" />
                  </summary>
                  <div class="p-3 border-t dark:border-gray-700 bg-white dark:bg-gray-950/20 space-y-3">
                      <div v-for="event in initEvents" :key="event.id" class="flex flex-col gap-1">
                          <div class="text-[10px] font-bold text-gray-600 dark:text-gray-400">{{ event.content?.name || event.content }}</div>
                          <StepDetail :data="event.content" :level="0" />
                      </div>
                  </div>
              </details>
          </div>

          <div v-if="part.type === 'system_event'" class="my-3 ml-2">
              <details class="group/event overflow-hidden rounded-xl border border-gray-100 dark:border-gray-800 bg-gray-50/10 dark:bg-gray-900/10 transition-all hover:border-blue-500/20 shadow-sm">
                  <summary class="flex items-center justify-between px-3 py-1.5 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800/50 transition-colors list-none select-none">
                      <div class="flex items-center gap-2.5">
                          <component :is="getEventIcon(part.event.type)" class="w-3.5 h-3.5 text-gray-400 group-open/event:text-blue-500 transition-colors" />
                          <span class="text-[10px] font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                              {{ part.event.tool ? part.event.tool.replace('_', ' ') : part.event.content }}
                          </span>
                      </div>
                      <IconChevronRight class="w-3 h-3 text-gray-300 group-open/event:rotate-90 transition-transform" />
                  </summary>
                  <div class="p-3 border-t dark:border-gray-800 bg-white dark:bg-gray-950/20">
                      <StepDetail :data="part.event.content" :level="0" />
                  </div>
              </details>
          </div>

          <!-- ── Mermaid diagram ─────────────────────────────────────────── -->
          <div v-if="part.type === 'mermaid'" class="my-4 rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700 shadow-sm mermaid-wrapper">
            <MermaidViewer 
              :mermaid-code="part.code" 
              :message-id="messageId"
              @ready="onMermaidReady($event, index)" 
            />
          </div>

          <!-- ── Inline Event Marker (Expandable Tool Block) ────────────── -->
          <div v-if="part.type === 'inline_event' && part.event" class="my-6 animate-in fade-in slide-in-from-left-2">
              <details class="group/inline w-full border dark:border-gray-700 rounded-2xl bg-gray-50/30 dark:bg-gray-900/20 overflow-hidden transition-all hover:border-blue-500/30">
                  <summary class="flex items-center justify-between p-3.5 cursor-pointer list-none select-none">
                      <div class="flex items-center gap-4">
                          <div class="p-2.5 rounded-xl bg-white dark:bg-gray-900 shadow-sm text-blue-500 group-open/inline:text-emerald-500 transition-colors">
                              <IconWrenchScrewdriver v-if="part.event.type === 'tool_call'" class="w-5 h-5" />
                              <IconCheckCircle v-else class="w-5 h-5" />
                          </div>
                          <div class="flex flex-col">
                              <span class="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400">Action performed</span>
                              <span class="text-sm font-bold text-gray-800 dark:text-gray-200">
                                  {{ part.event.tool ? part.event.tool.replace('_', ' ') : 'System Step' }}
                              </span>
                          </div>
                      </div>
                      <div class="flex items-center gap-3">
                          <span class="text-[10px] font-black text-gray-400 group-open/inline:hidden uppercase tracking-widest">Show Result</span>
                          <IconChevronRight class="w-4 h-4 text-gray-400 group-open/inline:rotate-90 transition-transform" />
                      </div>
                  </summary>
                  
                  <div class="p-4 border-t dark:border-gray-700 bg-white dark:bg-gray-950/40">
                      <!-- Render the tool parameters and output beautifully -->
                      <StepDetail :data="part.event.content" :level="0" />
                  </div>
              </details>
          </div>

          <div v-if="part.type === 'content'" class="content-token-container">
            <template v-for="(token, tokenIndex) in (getTokens(part.content) || [])" :key="token.uid || `token-${tokenIndex}`">
              <CodeBlock v-if="token.type === 'code'" :language="token.lang" :code="token.text" :message-id="messageId" />
              
              <details v-else-if="token.type === 'document'" class="document-block my-4 group/block">
                  <summary class="document-summary flex items-center justify-between pr-2">
                      <div class="flex items-center gap-2 overflow-hidden">
                        <IconFileText class="w-4 h-4 text-gray-600 dark:text-gray-400 flex-shrink-0" />
                        <span class="font-mono truncate">{{ token.title }}</span>
                      </div>
                      <button @click.stop="discussionsStore.removeContextItem(token.title, 'document')" class="opacity-0 group-hover/block:opacity-100 p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500 transition-opacity" title="Remove from context">
                        <IconTrash class="w-3.5 h-3.5" />
                      </button>
                  </summary>
                  <div class="document-content p-4 prose prose-sm dark:prose-invert max-w-none" v-if="token.content" v-html="parsedMarkdown(token.content)"></div>
              </details>
              
              <details v-else-if="token.type === 'skill_block'" class="skill-block my-4 group/block">
                  <summary class="skill-summary flex items-center justify-between pr-2">
                      <div class="flex items-center gap-2 overflow-hidden">
                        <IconSparkles class="w-4 h-4 text-teal-600 dark:text-teal-400 flex-shrink-0" />
                        <span class="font-mono text-xs font-bold tracking-wider text-teal-700 dark:text-teal-300 truncate">Skill: {{ token.title }}</span>
                      </div>
                      <button @click.stop="discussionsStore.removeContextItem(token.title, 'skill')" class="opacity-0 group-hover/block:opacity-100 p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500 transition-opacity" title="Remove from context">
                        <IconTrash class="w-3.5 h-3.5" />
                      </button>
                  </summary>
                  <div class="skill-content p-4 prose prose-sm dark:prose-invert max-w-none" v-if="token.content" v-html="parsedMarkdown(token.content)"></div>
              </details>
              
              <details v-else-if="token.type === 'note_block'" class="note-block-collapsible my-4 group/block">
                  <summary class="note-summary flex items-center justify-between pr-2">
                      <div class="flex items-center gap-2 overflow-hidden">
                        <IconFileText class="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
                        <span class="font-mono text-xs font-bold tracking-wider text-amber-700 dark:text-amber-300 truncate">Note: {{ token.title }}</span>
                      </div>
                      <button @click.stop="discussionsStore.removeContextItem(token.title, 'note')" class="opacity-0 group-hover/block:opacity-100 p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500 transition-opacity" title="Remove from context">
                        <IconTrash class="w-3.5 h-3.5" />
                      </button>
                  </summary>
                  <div class="note-content p-4 prose prose-sm dark:prose-invert max-w-none" v-if="token.content" v-html="parsedMarkdown(token.content)"></div>
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
              <IconThinking class="h-5 w-5 flex-shrink-0" />
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
                <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
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
                <IconSparkles class="w-4 h-4 text-teal-600 dark:text-teal-400 flex-shrink-0" />
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

          <!-- ── Interactive Teaching Widget ───────────────────────────── -->
          <div v-else-if="part.type === 'interactive_widget' && part.widget" class="my-6">
              <div class="rounded-2xl border-2 border-blue-500/20 bg-white dark:bg-gray-900 shadow-xl overflow-hidden">
                  <div class="px-4 py-2 bg-blue-500/5 border-b dark:border-gray-800 flex items-center justify-between">
                      <div class="flex items-center gap-2">
                          <IconCpuChip class="w-4 h-4 text-blue-500" />
                          <span class="text-xs font-bold text-blue-600 dark:text-blue-400 uppercase tracking-widest">{{ part.widget.title }}</span>
                      </div>
                      <span class="text-[10px] font-black text-gray-400 uppercase tracking-tighter">{{ part.widget.type }} Engine</span>
                  </div>
                  <div class="aspect-video w-full">
                      <!-- [FIX] Use live buffer if widget is currently being streamed -->
                      <iframe 
                        :srcdoc="discussionsStore.liveArtefactBuffers[part.widget?.title] || part.widget?.source" 
                        class="w-full h-full border-0" 
                        sandbox="allow-scripts allow-same-origin allow-forms"
                      ></iframe>
                  </div>
              </div>
          </div>

        </template>

        <!-- ── [NEW] Live Active Event Indicator ──────────────────────── -->
        <div v-if="isStreaming && $attrs.message?.lastEvent" class="mt-4 animate-in fade-in slide-in-from-bottom-1">
             <div class="flex items-center gap-3 p-3 rounded-xl bg-blue-50/50 dark:bg-blue-900/10 border border-blue-100/50 dark:border-blue-800/30">
                  <div class="relative flex-shrink-0">
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

    <!-- ── Dedicated Sources Area (At the absolute end) ────────────────── -->
    <div v-if="sources && sources.length > 0" 
         class="mt-10 border-t-2 border-gray-100 dark:border-gray-800 pt-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        <details class="group/sources-list">
            <summary class="flex items-center justify-between cursor-pointer list-none select-none mb-4">
                <div class="flex items-center gap-3">
                    <div class="p-2 rounded-lg bg-blue-50 dark:bg-blue-900/20 group-hover:bg-blue-100 transition-colors">
                        <IconGather class="w-5 h-5 text-blue-500" />
                    </div>
                    <h3 class="text-xs font-black uppercase tracking-[0.25em] text-gray-400 dark:text-gray-500">Sources & References ({{ sources.length }})</h3>
                </div>
                <IconChevronRight class="w-4 h-4 text-gray-300 group-open/sources-list:rotate-90 transition-transform" />
            </summary>
            
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 pb-4">
                <div v-for="(source, sIdx) in sources" :key="sIdx" 
                     @click="handleSourceClick(source, sIdx)"
                     class="p-3.5 bg-white dark:bg-gray-800/40 border border-gray-100 dark:border-gray-700/50 rounded-2xl hover:border-blue-500 hover:shadow-md transition-all cursor-pointer group/src shadow-sm relative overflow-hidden">
                
                <div class="flex items-start justify-between gap-3 relative z-10">
                    <div class="flex items-center gap-2.5 min-w-0">
                        <span class="flex-shrink-0 w-6 h-6 flex items-center justify-center bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-lg text-[10px] font-black font-mono">
                            {{ source.index || sIdx + 1 }}
                        </span>
                        <span class="font-bold text-sm truncate text-gray-800 dark:text-gray-100 group-hover/src:text-blue-600 transition-colors">{{ source.title || 'Untitled Source' }}</span>
                    </div>
                    <div v-if="source.relevance_score" class="flex-shrink-0 text-[10px] font-mono font-bold text-emerald-500 bg-emerald-50 dark:bg-emerald-900/20 px-1.5 py-0.5 rounded-full border border-emerald-100 dark:border-emerald-800/50">
                        {{ Math.round(source.relevance_score > 1 ? source.relevance_score : source.relevance_score * 100) }}%
                    </div>
                </div>

                <p v-if="source.content" class="mt-2.5 text-xs text-gray-500 dark:text-gray-400 line-clamp-2 leading-relaxed">
                    {{ source.content }}
                </p>

                <div class="mt-3 flex items-center justify-between">
                    <span class="text-[8px] font-mono text-gray-400 truncate max-w-[70%] opacity-60">{{ source.source }}</span>
                    <span class="text-[9px] font-black text-blue-500 uppercase tracking-widest opacity-0 group-hover/src:opacity-100 transform translate-x-2 group-hover/src:translate-x-0 transition-all">Details &rarr;</span>
                </div>

                <!-- Subtle hover background decoration -->
                <div class="absolute -right-4 -bottom-4 w-20 h-20 bg-blue-500/5 rounded-full blur-2xl group-hover/src:bg-blue-500/10 transition-colors"></div>
            </div>
        </div>
    </details>
    </div>
  </div>
</template>

<style scoped>
.message-prose {
    @apply prose prose-base dark:prose-invert max-w-none break-words;
    font-size: var(--message-font-size, 14px);
}
.btn-icon-sm { @apply p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors flex items-center justify-center; }
.think-block { @apply bg-blue-50 dark:bg-gray-900/40 border border-blue-200 dark:border-blue-800/30 rounded-lg; }
details[open] > .think-summary { @apply border-b border-blue-200 dark:border-blue-800/30; }
.think-summary { @apply flex items-center gap-2 p-2 text-sm font-semibold text-blue-800 dark:text-blue-200 cursor-pointer list-none select-none; -webkit-tap-highlight-color: transparent; }
.think-summary:focus-visible { @apply ring-2 ring-blue-400 outline-none; }
.think-summary::-webkit-details-marker { display: none; }
.think-content { @apply p-3; }
.document-block { @apply bg-gray-50 dark:bg-gray-900/40 border border-gray-200 dark:border-gray-700/50 rounded-lg; }
.document-summary { @apply flex items-center gap-2 p-2 text-sm font-semibold text-gray-800 dark:text-gray-200 cursor-pointer list-none select-none; -webkit-tap-highlight-color: transparent; }
.document-summary:focus-visible { @apply ring-2 ring-blue-400 outline-none; }
.document-summary::-webkit-details-marker { display: none; }
details[open] > .document-summary { @apply border-b border-gray-200 dark:border-gray-700/50; }
.document-content { @apply p-3; }

.skill-block { @apply bg-teal-50/30 dark:bg-teal-900/10 border border-teal-200 dark:border-teal-800/40 rounded-lg overflow-hidden shadow-sm transition-all; }
.skill-summary { @apply flex items-center gap-2 p-2 text-sm cursor-pointer list-none select-none hover:bg-teal-100/50 dark:hover:bg-teal-900/30 transition-colors; }
.skill-summary::-webkit-details-marker { display: none; }
details[open].skill-block > .skill-summary { @apply border-b border-teal-200 dark:border-teal-800/40; }

.note-block-collapsible { @apply bg-amber-50/30 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800/40 rounded-lg overflow-hidden shadow-sm transition-all; }
.note-summary { @apply flex items-center gap-2 p-2 text-sm cursor-pointer list-none select-none hover:bg-amber-100/50 dark:hover:bg-amber-900/30 transition-colors; }
.note-summary::-webkit-details-marker { display: none; }
details[open].note-block-collapsible > .note-summary { @apply border-b border-amber-200 dark:border-amber-800/40; }

.document-block { @apply bg-gray-50/50 dark:bg-gray-900/30 border border-gray-200 dark:border-gray-700/50 rounded-lg overflow-hidden shadow-sm transition-all; }
.document-summary { @apply flex items-center gap-2 p-2 text-sm cursor-pointer list-none select-none hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors; }
.document-summary::-webkit-details-marker { display: none; }
details[open].document-block > .document-summary { @apply border-b border-gray-200 dark:border-gray-700/50; }

.timeline-details summary::-webkit-details-marker { display: none; }
.timeline-details[open] { @apply shadow-xl ring-2 ring-blue-500/5 bg-white dark:bg-gray-900/40 border-blue-500/20; }
.timeline-details summary:focus { @apply outline-none; }

/* Mermaid wrapper — starts at a sensible default, auto-sized by onMermaidReady */
.mermaid-wrapper {
  height: 500px;
  transition: height 0.2s ease;
}

/* Note block */
.note-block {
  position: relative;
}

.note-block summary::-webkit-details-marker {
  display: none;
}

.note-block[open] .summary-arrow {
  transform: rotate(90deg);
}
.note-content :deep(p) { @apply my-1.5 leading-relaxed; }
.note-content :deep(h1),
.note-content :deep(h2),
.note-content :deep(h3) { @apply font-bold text-gray-900 dark:text-gray-100 mt-3 mb-1.5; }
.note-content :deep(ul),
.note-content :deep(ol) { @apply my-1.5 pl-5; }
.note-content :deep(li) { @apply my-0.5; }
.note-content :deep(code) { @apply bg-amber-100 dark:bg-amber-900/40 text-amber-900 dark:text-amber-200 px-1 py-0.5 rounded text-xs; }
.note-content :deep(pre) { @apply bg-amber-100/60 dark:bg-amber-900/30 rounded-lg p-3 my-2 overflow-auto; }
.note-content :deep(blockquote) { @apply border-l-2 border-amber-400 pl-3 italic text-gray-600 dark:text-gray-400 my-2; }
.note-content :deep(hr) { @apply border-amber-200 dark:border-amber-800 my-3; }
.note-content :deep(table) { @apply w-full text-sm my-2; }
.note-content :deep(th) { @apply bg-amber-100 dark:bg-amber-900/40 font-semibold px-2 py-1 text-left; }
.note-content :deep(td) { @apply border-t border-amber-100 dark:border-amber-900/30 px-2 py-1; }
</style>