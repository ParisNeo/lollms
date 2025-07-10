<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue';
import { useEditor, EditorContent } from '@tiptap/vue-3';
import { marked } from 'marked';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Table from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';
import CodeBlockLowlight from '@tiptap/extension-code-block-lowlight';
import { createLowlight } from 'lowlight';
import html from 'highlight.js/lib/languages/xml';
import css from 'highlight.js/lib/languages/css';
import js from 'highlight.js/lib/languages/javascript';
import python from 'highlight.js/lib/languages/python';
import json from 'highlight.js/lib/languages/json';
import 'highlight.js/styles/github-dark.css';

const lowlight = createLowlight({
  html,
  css,
  javascript: js,
  python,
  json,
});

marked.setOptions({
  gfm: true,
  breaks: true,
  mangle: false,
  headerIds: false,
});

const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
});

const emit = defineEmits(['update:modelValue']);

const showPasteOptions = ref(false);
const pasteMenuRef = ref(null);

const editor = useEditor({
  content: props.modelValue,
  extensions: [
    StarterKit,
    Link.configure({ openOnClick: false }),
    Table.configure({ resizable: true }),
    TableRow, TableHeader, TableCell,
    CodeBlockLowlight.configure({ lowlight }),
  ],
  onUpdate: () => {
    emit('update:modelValue', editor.value.getHTML());
  },
  editorProps: {
    attributes: {
      class: 'prose dark:prose-invert prose-sm sm:prose-base lg:prose-lg xl:prose-2xl m-5 focus:outline-none min-h-[200px]',
    },
    handlePaste(view, event) {
      const htmlContent = event.clipboardData?.getData('text/html');
      
      if (htmlContent) {
        editor.value.chain().focus().insertContent(htmlContent).run();
        return true;
      }

      const textContent = event.clipboardData?.getData('text/plain');
      if (textContent) {
        const htmlFromMarkdown = marked.parse(textContent);
        editor.value.chain().focus().insertContent(htmlFromMarkdown).run();
        return true;
      }

      return false;
    },
  },
});

watch(() => props.modelValue, (newValue) => {
    if (editor.value && editor.value.getHTML() !== newValue) {
        editor.value.commands.setContent(newValue, false);
    }
});

onUnmounted(() => {
    if (editor.value) {
        editor.value.destroy();
    }
    document.removeEventListener('click', handleClickOutside);
});

const handlePasteAction = async (action) => {
  try {
    switch (action) {
      case 'html':
        await pasteAsHtml();
        break;
      case 'text':
        await pasteAsText();
        break;
      case 'code':
        await pasteAsCode();
        break;
    }
  } catch (err) {
    console.error('Failed to read clipboard contents: ', err);
    alert('Failed to paste. Please ensure you have granted clipboard permissions.');
  }
  showPasteOptions.value = false;
  editor.value.chain().focus().run();
};

const pasteAsHtml = async () => {
  const clipboardItems = await navigator.clipboard.read();
  let htmlContent = '';
  for (const item of clipboardItems) {
    if (item.types.includes('text/html')) {
      const blob = await item.getType('text/html');
      htmlContent = await blob.text();
      break;
    }
  }
  if (!htmlContent) {
    htmlContent = await navigator.clipboard.readText();
  }
  editor.value.commands.insertContent(htmlContent);
};

const pasteAsText = async () => {
  const text = await navigator.clipboard.readText();
  editor.value.commands.insertContent(text);
};

const pasteAsCode = async () => {
  const text = await navigator.clipboard.readText();
  const codeBlockHtml = `<pre><code>${escapeHtml(text)}</code></pre>`;
  editor.value.commands.insertContent(codeBlockHtml);
};

const escapeHtml = (unsafe) => {
  return unsafe
    .replace(/&/g, "&")
    .replace(/</g, "<")
    .replace(/>/g, ">")
    .replace(/"/g, "\"")
    .replace(/'/g, "'");
}

const handleClickOutside = (event) => {
  if (pasteMenuRef.value && !pasteMenuRef.value.contains(event.target)) {
    showPasteOptions.value = false;
  }
};

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
});


const setLink = () => {
  const previousUrl = editor.value.getAttributes('link').href;
  const url = window.prompt('URL', previousUrl);
  if (url === null) return;
  if (url === '') {
    editor.value.chain().focus().extendMarkRange('link').unsetLink().run();
    return;
  }
  editor.value.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
};

const toolbarActions = ref([
    { type: 'divider' },
    { icon: 'undo', action: () => editor.value.chain().focus().undo().run(), title: 'Undo' },
    { icon: 'redo', action: () => editor.value.chain().focus().redo().run(), title: 'Redo' },
    { type: 'divider' },
    { type: 'paste-menu' },
    { type: 'divider' },
    { icon: 'bold', action: () => editor.value.chain().focus().toggleBold().run(), isActive: () => editor.value?.isActive('bold'), title: 'Bold' },
    { icon: 'italic', action: () => editor.value.chain().focus().toggleItalic().run(), isActive: () => editor.value?.isActive('italic'), title: 'Italic' },
    { icon: 'strike', action: () => editor.value.chain().focus().toggleStrike().run(), isActive: () => editor.value?.isActive('strike'), title: 'Strikethrough' },
    { type: 'divider' },
    { icon: 'h-1', action: () => editor.value.chain().focus().toggleHeading({ level: 1 }).run(), isActive: () => editor.value?.isActive('heading', { level: 1 }), title: 'Heading 1' },
    { icon: 'h-2', action: () => editor.value.chain().focus().toggleHeading({ level: 2 }).run(), isActive: () => editor.value?.isActive('heading', { level: 2 }), title: 'Heading 2' },
    { icon: 'paragraph', action: () => editor.value.chain().focus().setParagraph().run(), isActive: () => editor.value?.isActive('paragraph'), title: 'Paragraph' },
    { type: 'divider' },
    { icon: 'bullet-list', action: () => editor.value.chain().focus().toggleBulletList().run(), isActive: () => editor.value?.isActive('bulletList'), title: 'Bullet List' },
    { icon: 'ordered-list', action: () => editor.value.chain().focus().toggleOrderedList().run(), isActive: () => editor.value?.isActive('orderedList'), title: 'Ordered List' },
    { icon: 'blockquote', action: () => editor.value.chain().focus().toggleBlockquote().run(), isActive: () => editor.value?.isActive('blockquote'), title: 'Blockquote' },
    { icon: 'code-block', action: () => editor.value.chain().focus().toggleCodeBlock().run(), isActive: () => editor.value?.isActive('codeBlock'), title: 'Code Block' },
    { type: 'divider' },
    { icon: 'link', action: setLink, isActive: () => editor.value?.isActive('link'), title: 'Set Link' },
    { icon: 'table', action: () => editor.value.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(), title: 'Insert Table' },
    { icon: 'hr', action: () => editor.value.chain().focus().setHorizontalRule().run(), title: 'Horizontal Rule' },
]);
</script>

<template>
  <div v-if="editor" class="border border-gray-300 dark:border-gray-600 rounded-md flex flex-col h-full max-h-[50vh]">
    <div class="toolbar flex items-center p-2 border-b border-gray-300 dark:border-gray-600 space-x-1 bg-gray-50 dark:bg-gray-700/50 rounded-t-md flex-wrap flex-shrink-0">
      <template v-for="(action, index) in toolbarActions" :key="index">
        <div v-if="action.type === 'divider'" class="w-px h-5 bg-gray-300 dark:bg-gray-600 mx-1"></div>
        
        <div v-else-if="action.type === 'paste-menu'" ref="pasteMenuRef" class="relative">
          <button @click="showPasteOptions = !showPasteOptions" type="button" class="toolbar-btn" title="Paste Options">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
            </svg>
          </button>
          <div v-if="showPasteOptions" class="paste-menu-dropdown">
            <button @click="handlePasteAction('html')" class="paste-menu-item">Paste as HTML</button>
            <button @click="handlePasteAction('text')" class="paste-menu-item">Paste as Plain Text</button>
            <button @click="handlePasteAction('code')" class="paste-menu-item">Paste as Code Block</button>
          </div>
        </div>
        
        <button v-else @click="action.action" type="button" class="toolbar-btn" :class="{'is-active': action.isActive && action.isActive()}" :title="action.title">
          <span v-if="action.icon === 'bold'" class="font-bold">B</span>
          <span v-else-if="action.icon === 'italic'" class="italic">I</span>
          <span v-else-if="action.icon === 'strike'" class="line-through">S</span>
          <span v-else-if="action.icon === 'h-1'" class="font-bold text-sm">H1</span>
          <span v-else-if="action.icon === 'h-2'" class="font-bold text-sm">H2</span>
          <svg v-else-if="action.icon === 'paragraph'" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 5h12M9 3v12" /></svg>
          <svg v-else-if="action.icon === 'bullet-list'" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7" /></svg>
          <svg v-else-if="action.icon === 'ordered-list'" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16" /></svg>
          <svg v-else-if="action.icon === 'blockquote'" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M13 15v5m0 0v-5m0 5h5M13 15h-5M3 3h2v2H3V3zm4 0h2v2H7V3zm4 0h2v2h-2V3zm4 0h2v2h-2V3zM3 7h2v2H3V7zm4 0h2v2H7V7zm4 0h2v2h-2V7zm4 0h2v2h-2V7z" /></svg>
          <svg v-else-if="action.icon === 'code-block'" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /></svg>
          <svg v-else-if="action.icon === 'link'" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
          <svg v-else-if="action.icon === 'table'" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
          <svg v-else-if="action.icon === 'hr'" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4 12h16" /></svg>
          <svg v-else-if="action.icon === 'undo'" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" /></svg>
          <svg v-else-if="action.icon === 'redo'" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" /></svg>
        </button>
      </template>
    </div>
    <div class="overflow-y-auto flex-grow">
      <editor-content :editor="editor" />
    </div>
  </div>
</template>

<style>
.toolbar-btn {
    @apply p-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 flex items-center justify-center h-8 w-8;
}
.toolbar-btn.is-active {
    @apply bg-blue-500 text-white hover:bg-blue-600;
}
.paste-menu-dropdown {
  @apply absolute top-full left-0 mt-2 w-48 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-md shadow-lg z-10;
}
.paste-menu-item {
  @apply block w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700;
}
.paste-menu-item:first-child {
  @apply rounded-t-md;
}
.paste-menu-item:last-child {
  @apply rounded-b-md;
}
.prose {
    max-width: none;
}
.tiptap table {
  border-collapse: collapse;
  table-layout: fixed;
  width: 100%;
  margin: 0;
  overflow: hidden;
}
.tiptap table td, .tiptap table th {
  min-width: 1em;
  border: 2px solid #ced4da;
  padding: 3px 5px;
  vertical-align: top;
  box-sizing: border-box;
  position: relative;
}
.tiptap table th {
  font-weight: bold;
  text-align: left;
  background-color: #f1f3f5;
}
.dark .tiptap table th {
    background-color: #374151;
}
.dark .tiptap table td, .dark .tiptap table th {
    border: 2px solid #4b5563;
}
.tiptap .column-resizer {
  position: absolute;
  right: -2px;
  top: 0;
  height: 100%;
  width: 4px;
  background-color: #adf;
  cursor: col-resize;
  user-select: none;
}
.tiptap .table-wrapper {
  padding: 1rem 0;
  overflow-x: auto;
}
.tiptap pre {
  background: #0d1117;
  color: #c9d1d9;
  font-family: 'JetBrainsMono', monospace;
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
}
.tiptap pre code {
  color: inherit;
  padding: 0;
  background: none;
  font-size: 0.8rem;
}
.tiptap .hljs-comment,
.tiptap .hljs-quote {
  color: #8b949e;
}
.tiptap .hljs-variable,
.tiptap .hljs-template-variable,
.tiptap .hljs-selector-id,
.tiptap .hljs-selector-class,
.tiptap .hljs-regexp,
.tiptap .hljs-deletion {
  color: #f97583;
}
.tiptap .hljs-number,
.tiptap .hljs-built_in,
.tiptap .hljs-literal,
.tiptap .hljs-type,
.tiptap .hljs-params,
.tiptap .hljs-meta,
.tiptap .hljs-link {
  color: #ff9800;
}
.tiptap .hljs-attribute {
  color: #ffc107;
}
.tiptap .hljs-string,
.tiptap .hljs-symbol,
.tiptap .hljs-bullet,
.tiptap .hljs-addition {
  color: #a5d6ff;
}
.tiptap .hljs-title,
.tiptap .hljs-section {
  color: #d2a8ff;
}
.tiptap .hljs-keyword,
.tiptap .hljs-selector-tag {
  color: #ff7b72;
}
.tiptap .hljs-emphasis {
  font-style: italic;
}
.tiptap .hljs-strong {
  font-weight: bold;
}
</style>