<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue';
import { parsedMarkdown as rawParsedMarkdown, getContentTokensWithMathProtection } from '../../services/markdownParser';

import CodeBlock from './CodeBlock.vue';
import IconThinking from '../../assets/icons/IconThinking.vue';

const props = defineProps({
  content: { type: String, default: '' },
  isStreaming: { type: Boolean, default: false },
  isUser: { type: Boolean, default: false },
  hasImages: { type: Boolean, default: false }
});

const messageContentRef = ref(null);

// --- Math Rendering ---
function renderMath() {
  // **CRITICAL FIX**: Corrected `messageContent-ref` to `messageContentRef`
  if (messageContentRef.value && window.renderMathInElement) {
    window.renderMathInElement(messageContentRef.value, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '\\[', right: '\\]', display: true },
        { left: '\\(', right: '\\)', display: false },
        { left: '$', right: '$', display: false } // Keeping single dollar for compatibility
      ],
      throwOnError: false
    });
  }
}

// Watchers and Lifecycle hooks are correct
watch(() => props.content, async () => {
  await nextTick();
  renderMath();
}, { flush: 'post' });

onMounted(async () => {
  await nextTick();
  renderMath();
});


// --- Content Processing ---

/**
 * A robust parser that isolates math from the markdown renderer.
 * This is applied to non-code content tokens.
 */
const parsedMarkdown = (content) => {
  if (!content) return '';

  const mathBlocks = [];
  const placeholder = 'zZz_MATH_PLACEHOLDER_zZz';

  // **CRITICAL FIX**: A simpler, correct regex to capture all math delimiters.
  // It captures $$...$$, \[...\], \(...\), and $...$
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

// For streaming content, directly use the robust parser
const parsedStreamingContent = computed(() => parsedMarkdown(props.content));

// --- Tokenization for Settled Content (Correctly Preserved) ---

// This logic correctly separates <think> blocks
const messageParts = computed(() => {
  if (!props.content || props.isStreaming) return [];
  const parts = [];
  const content = props.content;
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

// This logic correctly separates code blocks using your imported service
const getContentTokens = (text) => {
  return getContentTokensWithMathProtection(text);
};
</script>

<template>
  <div :key="isStreaming ? 'streaming' : 'settled'" ref="messageContentRef">
    <div v-if="content || (isUser && !hasImages)" class="message-prose">
      <div v-if="isStreaming" v-html="parsedStreamingContent"></div>
      <template v-else>
        <template v-for="(part, index) in messageParts" :key="index">
          <template v-if="part.type === 'content'">
            <template v-for="(token, tokenIndex) in getContentTokens(part.content)" :key="tokenIndex">
              <CodeBlock v-if="token.type === 'code'" :language="token.lang" :code="token.text" />
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
        </template>
      </template>
    </div>
  </div>
</template>

<style scoped>
.message-prose { @apply prose prose-base dark:prose-invert max-w-none break-words; }
.think-block { @apply bg-blue-50 dark:bg-gray-900/40 border border-blue-200 dark:border-blue-800/30 rounded-lg; }
details[open] > .think-summary { @apply border-b border-blue-200 dark:border-blue-800/30; }
.think-summary { @apply flex items-center gap-2 p-2 text-sm font-semibold text-blue-800 dark:text-blue-200 cursor-pointer list-none select-none; -webkit-tap-highlight-color: transparent; }
.think-summary:focus-visible { @apply ring-2 ring-blue-400 outline-none; }
.think-summary::-webkit-details-marker { display: none; }
.think-content { @apply p-3; }
</style>
