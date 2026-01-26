<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue';
import { parsedMarkdown as rawParsedMarkdown, getContentTokensWithMathProtection } from '../../../services/markdownParser';

import CodeBlock from './CodeBlock.vue';
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

import { useTasksStore } from '../../../stores/tasks';
import { useDiscussionsStore } from '../../../stores/discussions';
import { storeToRefs } from 'pinia';

const props = defineProps({
  content: { type: String, default: '' },
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
const { tasks } = storeToRefs(tasksStore);
const { activeAiTasks } = storeToRefs(discussionsStore);

// State for prompt editing
const editingPromptIdx = ref(-1);
const editedPromptText = ref('');

// ... (Math Rendering logic unchanged)
function renderMath() {
  if (messageContentRef.value && messageContentRef.value.isConnected && window.renderMathInElement) {
    try {
      window.renderMathInElement(messageContentRef.value, {
        delimiters: [
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
    
    // Check for streaming annotation blocks
    const openAnnTagIndex = content.lastIndexOf('<annotate>');
    const closeAnnTagIndex = content.lastIndexOf('</annotate>');
    
    if (openAnnTagIndex > -1 && openAnnTagIndex > closeAnnTagIndex) {
        const before = content.substring(0, openAnnTagIndex);
        const spinnerHtml = `<div class="flex items-center gap-2 my-4 p-3 bg-blue-50 dark:bg-gray-900/40 border border-blue-200 dark:border-blue-800/30 rounded-lg text-sm font-semibold text-blue-800 dark:text-blue-200">
            <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
            <span>Annotating image...</span>
        </div>`;
        return parsedMarkdown(before) + spinnerHtml;
    }
    
    // Check for streaming generation blocks
    const activeGenBlock = content.match(/<(generate_image|edit_image|generate_slides)[^>]*>(?!.*?<\/\1>)/s);
    if (activeGenBlock) {
         let tagType = 'Processing';
         if (activeGenBlock[1] === 'edit_image') tagType = 'Editing image';
         else if (activeGenBlock[1] === 'generate_image') tagType = 'Generating image';
         else if (activeGenBlock[1] === 'generate_slides') tagType = 'Generating slides';

         const before = content.substring(0, activeGenBlock.index);
         const spinnerHtml = `<div class="flex items-center gap-2 my-4 p-3 bg-purple-50 dark:bg-gray-900/40 border border-purple-200 dark:border-purple-800/30 rounded-lg text-sm font-semibold text-purple-800 dark:text-purple-200">
            <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
            <span>${tagType}...</span>
        </div>`;
        return parsedMarkdown(before) + spinnerHtml;
    }

    return parsedMarkdown(content);
});

// Helper to parse a raw special block string into a structured object
const parseSpecialBlock = (rawBlock, match = null) => {
    if (!match) {
        // Fallback regex if match not provided
         const regex = /(<think>[\s\S]*?(?:<\/think>|$))|(<annotate>[\s\S]*?(?:<\/annotate>|$))|(<generate_image[^>]*>[\s\S]*?(?:<\/generate_image>|$))|(<edit_image[^>]*>[\s\S]*?(?:<\/edit_image>|$))|(<generate_slides[^>]*>[\s\S]*?(?:<\/generate_slides>|$))|(<street_view>[\s\S]*?(?:<\/street_view>|$))|(<schedule_task[^>]*>[\s\S]*?(?:<\/schedule_task>|$))/;
         match = regex.exec(rawBlock);
    }
    
    if (!match) return { type: 'content', content: rawBlock };

    if (match[1]) { // think
        const content = match[1].replace(/<think>|<\/think>/g, '').trim();
        return { type: 'think', content };
    } 
    else if (match[2]) { // annotate
        let annotateContent = match[2].replace(/<annotate>|<\/annotate>/g, '').trim();
        const jsonMatch = annotateContent.match(/(\{[\s\S]*\}|\[[\s\S]*\])/);
        if (jsonMatch) annotateContent = jsonMatch[0];
        try {
            return { type: 'annotate', annotations: JSON.parse(annotateContent) };
        } catch (e) {
            return { type: 'content', content: `[Invalid annotation data]` };
        }
    } 
    else if (match[3]) { // generate_image
        const fullTag = match[3];
        const promptContent = fullTag.replace(/<generate_image[^>]*>|<\/generate_image>/g, '').trim();
        return { type: 'image_tool', mode: 'generate', prompt: promptContent, raw: fullTag };
    } 
    else if (match[4]) { // edit_image
        const fullTag = match[4];
        const promptContent = fullTag.replace(/<edit_image[^>]*>|<\/edit_image>/g, '').trim();
        return { type: 'image_tool', mode: 'edit', prompt: promptContent, raw: fullTag };
    } 
    else if (match[5]) { // generate_slides
        const fullTag = match[5];
        const innerContent = fullTag.replace(/<generate_slides[^>]*>|<\/generate_slides>/g, '').trim();
        const slideRegex = /<Slide>(.*?)<\/Slide>/gis;
        const slides = [];
        let sMatch;
        while ((sMatch = slideRegex.exec(innerContent)) !== null) {
            slides.push(sMatch[1].trim());
        }
        return { type: 'image_tool', mode: 'slides', prompt: innerContent, slides: slides, raw: fullTag };
    }
    else if (match[6]) { // street_view
        const fullTag = match[6];
        const location = fullTag.replace(/<street_view>|<\/street_view>/g, '').trim();
        return { type: 'image_tool', mode: 'street_view', prompt: location, raw: fullTag };
    }
    else if (match[7]) { // schedule_task
        const fullTag = match[7];
        const promptContent = fullTag.replace(/<schedule_task[^>]*>|<\/schedule_task>/g, '').trim();
        let name = "Task";
        const nameMatch = fullTag.match(/name="([^"]*)"/);
        if (nameMatch) name = nameMatch[1];
        return { type: 'scheduler', name: name, prompt: promptContent, raw: fullTag };
    }

    return { type: 'content', content: rawBlock };
};

const messageParts = computed(() => {
    if (!props.content || props.isStreaming) return [];
    
    const content = props.content;
    const parts = [];

    // 1. Identify all Markdown Code Blocks first to respect their boundaries
    // Regex matches: ```lang? [content] ```
    const codeBlockRegex = /(^\s*```(?:(\w*)\r?\n)?([\s\S]*?)^\s*```\s*?$)/gm; 
    const codeBlocks = [];
    let cbMatch;
    
    while ((cbMatch = codeBlockRegex.exec(content)) !== null) {
        codeBlocks.push({
            start: cbMatch.index,
            end: cbMatch.index + cbMatch[0].length,
            lang: cbMatch[2] || 'plaintext',
            inner: cbMatch[3], // The content inside fences
            full: cbMatch[0]
        });
    }

    // 2. Identify all Tool Blocks
    const toolRegex = /(<think>[\s\S]*?(?:<\/think>|$))|(<annotate>[\s\S]*?(?:<\/annotate>|$))|(<generate_image[^>]*>[\s\S]*?(?:<\/generate_image>|$))|(<edit_image[^>]*>[\s\S]*?(?:<\/edit_image>|$))|(<generate_slides[^>]*>[\s\S]*?(?:<\/generate_slides>|$))|(<street_view>[\s\S]*?(?:<\/street_view>|$))|(<schedule_task[^>]*>[\s\S]*?(?:<\/schedule_task>|$))/g;
    const tools = [];
    let toolMatch;

    while ((toolMatch = toolRegex.exec(content)) !== null) {
        tools.push({
            start: toolMatch.index,
            end: toolMatch.index + toolMatch[0].length,
            raw: toolMatch[0],
            match: toolMatch
        });
    }

    // 3. Reconcile Tools vs Code Blocks
    // Logic: If a Tool is strictly inside a code block AND consumes the entire code block content, 
    // we "unwrap" it (treat code block as the tool). Otherwise, code block takes precedence.
    const activeTools = [];

    for (const tool of tools) {
        let isInsideCode = false;
        let isValidTool = true;

        for (const code of codeBlocks) {
            // Check if tool is strictly inside the code block
            if (tool.start >= code.start && tool.end <= code.end) {
                isInsideCode = true;
                
                // Unwrapping Check: Does the tool text match the code block inner text (ignoring whitespace)?
                // We use trim() on both sides.
                const codeInnerTrimmed = code.inner.trim();
                const toolRawTrimmed = tool.raw.trim();

                if (codeInnerTrimmed === toolRawTrimmed) {
                    // It's a match! The code block is just a wrapper for the tool.
                    // Expand the tool's effective range to cover the whole code block.
                    tool.start = code.start;
                    tool.end = code.end;
                    isValidTool = true;
                } else {
                    // Tool is just a snippet inside a larger code block. Treat as code.
                    isValidTool = false;
                }
                break; // Found the containing block
            } 
            // Check for partial overlap (should rarely happen in valid md, but possible)
            else if (tool.start < code.end && tool.end > code.start) {
                // Overlap exists. Priority to code block to prevent breaking code rendering.
                isValidTool = false;
            }
        }

        if (isValidTool) {
            activeTools.push(tool);
        }
    }

    // 4. Sort tools by start index
    activeTools.sort((a, b) => a.start - b.start);

    // 5. Construct final parts list
    let cursor = 0;
    for (const tool of activeTools) {
        // Push content before tool
        if (tool.start > cursor) {
            parts.push({ type: 'content', content: content.substring(cursor, tool.start) });
        }
        
        // Push tool
        parts.push(parseSpecialBlock(tool.raw, tool.match));
        
        // Advance cursor
        cursor = tool.end;
    }

    // Push remaining content
    if (cursor < content.length) {
        parts.push({ type: 'content', content: content.substring(cursor) });
    }

    return parts.length > 0 ? parts : [{ type: 'content', content: '' }];
});

const getTokens = (text) => {
    if (!text) return [];
    const allTokens = [];
    const docRegex = /(?:^|\n)--- Document: ([\w.\s-]+?)( v\d+)? ---\r?\n([\s\S]*?)\r?\n--- End Document: \1 ---/g;
    let lastIndex = 0;
    let match;

    while ((match = docRegex.exec(text)) !== null) {
        if (match.index > lastIndex) {
            const markdownPart = text.substring(lastIndex, match.index);
            allTokens.push(...getContentTokensWithMathProtection(markdownPart));
        }
        const title = match[1].trim() + (match[2] || '');
        allTokens.push({ type: 'document', title: title, content: match[3], raw: match[0] });
        lastIndex = docRegex.lastIndex;
    }

    if (lastIndex < text.length) {
        const markdownPart = text.substring(lastIndex);
        allTokens.push(...getContentTokensWithMathProtection(markdownPart));
    }

    return allTokens;
};

const activeTask = computed(() => {
    if (!props.messageId) return null;
    const discussionId = discussionsStore.currentDiscussionId;
    if (!discussionId) return null;
    const runningTasks = tasks.value.filter(t => t.status === 'running' || t.status === 'pending');
    const messageObj = discussionsStore.messages.find(m => m.id === props.messageId);
    if (messageObj && messageObj.metadata && messageObj.metadata.active_task_id) {
        const linkedTask = runningTasks.find(t => t.id === messageObj.metadata.active_task_id);
        if (linkedTask) return linkedTask;
    }
    const tracked = activeAiTasks.value[discussionId];
    if (tracked && tracked.taskId) {
        const task = runningTasks.find(t => t.id === tracked.taskId);
        if (task && !props.isUser) return task;
    }
    return null;
});

function handleRegenerateClick(index, part) {
    if (editingPromptIdx.value === index) {
        // [MODIFIED] Pass the custom prompt during regeneration
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
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
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
        const fillOpacity = display?.fill_opacity !== undefined ? display?.fill_opacity : 0.1;
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

        if (box && box.length === 4) {
            const [x1, y1, x2, y2] = box;
            const absX = x1 * naturalWidth;
            const absY = y1 * naturalHeight;
            const absW = (x2 - x1) * naturalWidth;
            const absH = (y2 - y1) * naturalHeight;
            if (showBorder) ctx.strokeRect(absX, absY, absW, absH);
            ctx.fillStyle = `${color}${Math.round(fillOpacity * 255).toString(16).padStart(2, '0')}`;
            ctx.fillRect(absX, absY, absW, absH);
            drawLabel(absX, absY);
        } else if (polygon && Array.isArray(polygon) && polygon.length > 1) {
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
        } else if (point && point.length === 2) {
            const [x, y] = point;
            const absX = x * naturalWidth;
            const absY = y * naturalHeight;
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
    // Check if the clicked element is a citation button (injected via markdownParser extension)
    const btn = event.target.closest('.citation-btn');
    if (btn) {
        const index = btn.dataset.index;
        if (index) {
            emit('citation-click', parseInt(index));
        }
    }
}
</script>

<template>
  <div :key="isStreaming ? 'streaming' : 'settled'" ref="messageContentRef" @click="handleContentClick">
    <div v-if="content || (isUser && !hasImages)" class="message-prose">
      <div v-if="isStreaming" v-html="parsedStreamingContent"></div>
      <template v-else>
        <template v-for="(part, index) in messageParts" :key="`part-${index}-${part.type}`">
          
          <template v-if="part.type === 'content'">
            <template v-for="(token, tokenIndex) in getTokens(part.content)" :key="`token-${tokenIndex}-${token.type}-${simpleHash(token.raw)}`">
              <CodeBlock v-if="token.type === 'code'" :language="token.lang" :code="token.text" :message-id="messageId" />
              <details v-else-if="token.type === 'document'" class="document-block my-4">
                  <summary class="document-summary">
                      <IconFileText class="w-4 h-4 text-gray-600 dark:text-gray-400 flex-shrink-0" />
                      <span class="font-mono">{{ token.title }}</span>
                  </summary>
                  <div class="document-content">
                      <MessageContentRenderer :content="token.content" />
                  </div>
              </details>
              <div v-else v-html="parsedMarkdown(token.raw)"></div>
            </template>
          </template>

          <details v-else-if="part.type === 'think'" class="think-block my-4" open>
            <summary class="think-summary">
              <IconThinking class="h-5 w-5 flex-shrink-0" />
              <span>Thinking...</span>
            </summary>
            <div class="think-content" v-html="parsedMarkdown(part.content)"></div>
          </details>

          <!-- [UPDATE] Enhanced Image Tool Call Block -->
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

             <!-- [NEW] Inline Prompt Editor -->
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
                 <!-- Existing blocks for slides/other -->
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

          <!-- [NEW] Scheduler Block -->
          <div v-else-if="part.type === 'scheduler'" class="my-4 p-4 rounded-xl border-2 border-indigo-200 dark:border-indigo-800 bg-indigo-50/50 dark:bg-indigo-900/20 shadow-sm">
             <div class="flex items-center gap-3">
                 <div class="p-2 rounded-lg bg-indigo-100 dark:bg-indigo-900/50 text-indigo-600 dark:text-indigo-400">
                     <IconClock class="w-6 h-6" />
                 </div>
                 <div class="flex flex-col">
                    <span class="text-[10px] font-black uppercase tracking-widest text-indigo-500 dark:text-indigo-300 leading-none mb-1">
                        Scheduled Task
                    </span>
                    <span class="text-sm font-bold text-gray-800 dark:text-gray-200">{{ part.name }}</span>
                    <span class="text-xs text-gray-600 dark:text-gray-400 italic mt-1">"{{ part.prompt }}"</span>
                 </div>
             </div>
          </div>

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

        </template>
      </template>
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
</style>
