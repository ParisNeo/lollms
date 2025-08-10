<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue';
import { parsedMarkdown, getContentTokensWithMathProtection } from '../../services/markdownParser';

import CodeBlock from './CodeBlock.vue';
import IconThinking from '../../assets/icons/IconThinking.vue';

const props = defineProps({
  content: { type: String, default: '' },
  isStreaming: { type: Boolean, default: false },
  isUser: { type: Boolean, default: false },
  hasImages: { type: Boolean, default: false }
});

const messageContentRef = ref(null);

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

onMounted(() => {
    renderMath();
});

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

const getContentTokens = (text) => {
    return getContentTokensWithMathProtection(text);
};

const parsedStreamingContent = computed(() => parsedMarkdown(props.content));
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
            <summary class="think-summary"><IconThinking class="h-5 w-5 flex-shrink-0" /><span>Thinking...</span></summary>
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