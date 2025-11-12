<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue';
import { parsedMarkdown as rawParsedMarkdown, getContentTokensWithMathProtection } from '../../../services/markdownParser';

import CodeBlock from './CodeBlock.vue';
import IconThinking from '../../../assets/icons/IconThinking.vue';
import IconFileText from '../../../assets/icons/IconFileText.vue';
import AuthenticatedImage from '../AuthenticatedImage.vue';
import IconArrowDownTray from '../../../assets/icons/IconArrowDownTray.vue';

const props = defineProps({
  content: { type: String, default: '' },
  isStreaming: { type: Boolean, default: false },
  isUser: { type: Boolean, default: false },
  hasImages: { type: Boolean, default: false },
  lastUserImage: { type: String, default: null },
  messageId: { type: String, default: null },
});

const messageContentRef = ref(null);

// --- Math Rendering ---
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
    /(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|(?<!\$)\$[^\s$](?:[\s\S]*?[^\s$])?\$(?!\$))/g,
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
    const openTagIndex = content.lastIndexOf('<annotate>');
    const closeTagIndex = content.lastIndexOf('</annotate>');
    
    if (openTagIndex > -1 && openTagIndex > closeTagIndex) {
        const before = content.substring(0, openTagIndex);
        const spinnerHtml = `<div class="flex items-center gap-2 my-4 p-3 bg-blue-50 dark:bg-gray-900/40 border border-blue-200 dark:border-blue-800/30 rounded-lg text-sm font-semibold text-blue-800 dark:text-blue-200">
            <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
            <span>Annotating image...</span>
        </div>`;
        return parsedMarkdown(before) + spinnerHtml;
    }
    
    return parsedMarkdown(content);
});

const messageParts = computed(() => {
    if (!props.content || props.isStreaming) return [];
    const parts = [];
    const content = props.content;
    const specialBlockRegex = /(<think>[\s\S]*?(?:<\/think>|$))|(<annotate>[\s\S]*?(?:<\/annotate>|$))/g;
    let lastIndex = 0;
    let match;

    while ((match = specialBlockRegex.exec(content)) !== null) {
        if (match.index > lastIndex) {
            parts.push({ type: 'content', content: content.substring(lastIndex, match.index) });
        }

        if (match[1]) { // Captured a <think> block
            const thinkContent = match[1].replace(/<think>|<\/think>/g, '').trim();
            if (thinkContent) {
                parts.push({ type: 'think', content: thinkContent });
            }
        } else if (match[2]) { // Captured an <annotate> block
            const annotateContent = match[2].replace(/<annotate>|<\/annotate>/g, '').trim();
            if (annotateContent) {
                try {
                    parts.push({ type: 'annotate', annotations: JSON.parse(annotateContent) });
                } catch (e) {
                    console.error("Failed to parse annotation JSON:", e);
                    parts.push({ type: 'content', content: `[Invalid annotation data: ${annotateContent}]` });
                }
            }
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

        if (box && box.length === 4) { // Bounding Box
            const [x1, y1, x2, y2] = box;
            const absX = x1 * naturalWidth;
            const absY = y1 * naturalHeight;
            const absW = (x2 - x1) * naturalWidth;
            const absH = (y2 - y1) * naturalHeight;

            if (showBorder) ctx.strokeRect(absX, absY, absW, absH);
            ctx.fillStyle = `${color}${Math.round(fillOpacity * 255).toString(16).padStart(2, '0')}`;
            ctx.fillRect(absX, absY, absW, absH);
            drawLabel(absX, absY);

        } else if (polygon && Array.isArray(polygon) && polygon.length > 1) { // Polygon
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

        } else if (point && point.length === 2) { // Point
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

        if (naturalWidth === 0 || containerWidth === 0 || containerHeight === 0) {
            return;
        }

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
            const horizontalMargin = (containerWidth - scaledWidth) / 2;
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
