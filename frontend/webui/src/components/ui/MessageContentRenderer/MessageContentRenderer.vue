<!-- [UPDATE] frontend/webui/src/components/ui/MessageContentRenderer/MessageContentRenderer.vue -->
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
import TaskProgressIndicator from '../TaskProgressIndicator.vue'; 

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

const emit = defineEmits(['regenerate']);

const messageContentRef = ref(null);
const tasksStore = useTasksStore();
const discussionsStore = useDiscussionsStore();
const { tasks } = storeToRefs(tasksStore);
const { activeAiTasks } = storeToRefs(discussionsStore);

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

// Enhanced parser for tags
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

const messageParts = computed(() => {
    if (!props.content || props.isStreaming) return [];
    const parts = [];
    const content = props.content;
    
    const specialBlockRegex = /(<think>[\s\S]*?(?:<\/think>|$))|(<annotate>[\s\S]*?(?:<\/annotate>|$))|(<generate_image[^>]*>[\s\S]*?(?:<\/generate_image>|$))|(<edit_image[^>]*>[\s\S]*?(?:<\/edit_image>|$))|(<generate_slides[^>]*>[\s\S]*?(?:<\/generate_slides>|$))/g;
    
    let lastIndex = 0;
    let match;

    while ((match = specialBlockRegex.exec(content)) !== null) {
        if (match.index > lastIndex) {
            parts.push({ type: 'content', content: content.substring(lastIndex, match.index) });
        }

        if (match[1]) { // <think>
            const thinkContent = match[1].replace(/<think>|<\/think>/g, '').trim();
            if (thinkContent) {
                parts.push({ type: 'think', content: thinkContent });
            }
        } else if (match[2]) { // <annotate>
            let annotateContent = match[2].replace(/<annotate>|<\/annotate>/g, '').trim();
            const jsonMatch = annotateContent.match(/(\{[\s\S]*\}|\[[\s\S]*\])/);
            if (jsonMatch) annotateContent = jsonMatch[0];
            
            if (annotateContent) {
                try {
                    parts.push({ type: 'annotate', annotations: JSON.parse(annotateContent) });
                } catch (e) {
                    parts.push({ type: 'content', content: `[Invalid annotation data]` });
                }
            }
        } else if (match[3]) { // <generate_image>
            const fullTag = match[3];
            const promptContent = fullTag.replace(/<generate_image[^>]*>|<\/generate_image>/g, '').trim();
            parts.push({ type: 'image_tool', mode: 'generate', prompt: promptContent, raw: fullTag });
        } else if (match[4]) { // <edit_image>
            const fullTag = match[4];
            const promptContent = fullTag.replace(/<edit_image[^>]*>|<\/edit_image>/g, '').trim();
            parts.push({ type: 'image_tool', mode: 'edit', prompt: promptContent, raw: fullTag });
        } else if (match[5]) { // <generate_slides>
            const fullTag = match[5];
            const innerContent = fullTag.replace(/<generate_slides[^>]*>|<\/generate_slides>/g, '').trim();
            
            const slideRegex = /<Slide>(.*?)<\/Slide>/gis;
            const slides = [];
            let sMatch;
            while ((sMatch = slideRegex.exec(innerContent)) !== null) {
                slides.push(sMatch[1].trim());
            }
            
            parts.push({ 
                type: 'image_tool', 
                mode: 'slides', 
                prompt: innerContent, 
                slides: slides,       
                raw: fullTag 
            });
        }
        
        lastIndex = match.index + match[0].length;
    }

    if (lastIndex < content.length) {
        parts.push({ type: 'content', content: content.substring(lastIndex) });
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

// [UPDATE] Find active task associated with this message to show progress indicator
const activeTask = computed(() => {
    if (!props.messageId) return null;
    const discussionId = discussionsStore.currentDiscussionId;
    if (!discussionId) return null;
    
    // Check active tasks in the store
    const runningTasks = tasks.value.filter(t => t.status === 'running' || t.status === 'pending');
    
    // 1. Check if the message metadata explicitly links to a task (set by backend for slides)
    // We access the message object from the store because props might be a copy or partial
    const messageObj = discussionsStore.messages.find(m => m.id === props.messageId);
    if (messageObj && messageObj.metadata && messageObj.metadata.active_task_id) {
        const linkedTask = runningTasks.find(t => t.id === messageObj.metadata.active_task_id);
        if (linkedTask) return linkedTask;
    }

    // 2. Fallback: Check if the discussion has a tracked active task that might be relevant
    const tracked = activeAiTasks.value[discussionId];
    if (tracked && tracked.taskId) {
        const task = runningTasks.find(t => t.id === tracked.taskId);
        // Heuristic: If we are the AI message and a task is running, it might be ours.
        // Especially if it's a generation type task.
        if (task && !props.isUser) {
             return task;
        }
    }
    return null;
});


const simpleHash = str => {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash |= 0;
  }
  return hash;
};

// ... (Annotation helpers: drawAnnotations, downloadAnnotatedImage, onImageLoad - unchanged)
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
</script>

<template>
  <div :key="isStreaming ? 'streaming' : 'settled'" ref="messageContentRef">
    <div v-if="content || (isUser && !hasImages)" class="message-prose">
      <div v-if="isStreaming" v-html="parsedStreamingContent"></div>
      <template v-else>
        <template v-for="(part, index) in messageParts" :key="`part-${index}-${part.type}`">
          
          <!-- Standard Content -->
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

          <!-- Thinking Block -->
          <details v-else-if="part.type === 'think'" class="think-block my-4" open>
            <summary class="think-summary">
              <IconThinking class="h-5 w-5 flex-shrink-0" />
              <span>Thinking...</span>
            </summary>
            <div class="think-content" v-html="parsedMarkdown(part.content)"></div>
          </details>

          <!-- Image Tool Call (Generation / Editing / Slides) - Rendered as a nice block with Regenerate -->
          <div v-else-if="part.type === 'image_tool'" class="my-4 p-3 rounded-lg border dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
             <div class="flex items-center justify-between mb-2">
                 <div class="flex items-center gap-2">
                     <div class="p-1.5 rounded-md bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400">
                         <IconPencil v-if="part.mode === 'edit'" class="w-4 h-4" />
                         <IconPresentationChartBar v-else-if="part.mode === 'slides'" class="w-4 h-4" />
                         <IconPhoto v-else class="w-4 h-4" />
                     </div>
                     <span class="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                         <template v-if="part.mode === 'edit'">Edit Request</template>
                         <template v-else-if="part.mode === 'slides'">Slides Request</template>
                         <template v-else>Generation Request</template>
                     </span>
                 </div>
                 <button @click="$emit('regenerate', part)" class="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 transition-colors" title="Regenerate">
                     <IconRefresh class="w-4 h-4" />
                 </button>
             </div>
             
             <!-- Show Active Task Progress if matched -->
             <div v-if="activeTask" class="mb-2">
                <TaskProgressIndicator :task="activeTask" class="text-xs" />
             </div>

             <!-- Slide List View -->
             <div v-if="part.slides && part.slides.length > 0" class="mt-2 pl-4 border-l-2 border-purple-200 dark:border-purple-800">
                 <div v-for="(slide, i) in part.slides" :key="i" class="text-xs text-gray-600 dark:text-gray-300 mb-1">
                     <span class="font-bold mr-1">{{ i + 1 }}.</span> {{ slide }}
                 </div>
             </div>
             <!-- Standard Prompt View -->
             <div v-else class="text-sm font-medium text-gray-800 dark:text-gray-200 italic">
                 "{{ part.prompt }}"
             </div>
          </div>

          <!-- Annotation Block -->
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
.think-block { @apply bg-blue-50 dark:bg-gray-900/40 border border-blue-200 dark:border-blue-800/30 rounded-lg; }
details[open] > .think-summary { @apply border-b border-blue-200 dark:border-blue-800/30; }
.think-summary { @apply flex items-center gap-2 p-2 text-sm font-semibold text-blue-800 dark:text-blue-200 cursor-pointer list-none select-none; -webkit-tap-highlight-color: transparent; }
.think-summary:focus-visible { @apply ring-2 ring-blue-400 outline-none; }
.think-summary::-webkit-details-marker { display: none; }
.think-content { @apply p-3; }

.document-block {
    @apply bg-gray-50 dark:bg-gray-900/40 border border-gray-200 dark:border-gray-700/50 rounded-lg;
}
.document-summary {
    @apply flex items-center gap-2 p-2 text-sm font-semibold text-gray-800 dark:text-gray-200 cursor-pointer list-none select-none;
    -webkit-tap-highlight-color: transparent;
}
.document-summary:focus-visible { @apply ring-2 ring-blue-400 outline-none; }
.document-summary::-webkit-details-marker { display: none; }
details[open] > .document-summary {
    @apply border-b border-gray-200 dark:border-gray-700/50;
}
.document-content { @apply p-3; }
</style>
