<script setup>
import { ref, shallowRef, watch } from 'vue'; // Import 'watch'
import { Codemirror } from 'vue-codemirror';
import { markdown } from '@codemirror/lang-markdown';
import { languages } from '@codemirror/language-data';
import { EditorView } from '@codemirror/view';
import LanguageSelectMenu from './LanguageSelectMenu.vue';

// Define props and emits for v-model
const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
});
const emit = defineEmits(['update:modelValue']);

// Editor refs
const view = shallowRef();
const code = ref(props.modelValue);

// --- FIX: Watch for external changes to v-model ---
// This ensures that if the parent component resets the modelValue,
// the editor's content is updated to match.
watch(() => props.modelValue, (newValue) => {
  if (newValue !== code.value) {
    code.value = newValue;
  }
});

// CodeMirror extensions
const extensions = [
  markdown({ codeLanguages: languages }),
  EditorView.lineWrapping,
];

// Language and icon data for the new menu
const languageGroups = [
  {
    isGroup: true,
    label: "Web",
    items: [
      { id: 'html', name: 'HTML', icon: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 3L5.77778 20.0899L12 22L18.2222 20.0899L20 3H4Z" fill="#E44D26"/><path d="M12 5V19.9L17.2222 18.4444L18.6667 5H12Z" fill="#F16529"/><path d="M12 9H15.5L15.25 12H12V9Z" fill="#EBEBEB"/><path d="M12 13H15L14.75 16L12 16.75V13Z" fill="#EBEBEB"/><path d="M12 9V12H8.75L8.5 9H12Z" fill="white"/><path d="M12 13V16.75L9.25 16L9 13H12Z" fill="white"/></svg>' },
      { id: 'css', name: 'CSS', icon: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 3L5.77778 20.0899L12 22L18.2222 20.0899L20 3H4Z" fill="#1572B6"/><path d="M12 5V19.9L17.2222 18.4444L18.6667 5H12Z" fill="#33A9DC"/><path d="M12 9H15.5L15.25 12H12V9Z" fill="#EBEBEB"/><path d="M12 13H15L14.75 16L12 16.75V13Z" fill="#EBEBEB"/><path d="M12 9V12H8.75L8.5 9H12Z" fill="white"/><path d="M12 13V16.75L9.25 16L9 13H12Z" fill="white"/></svg>' },
      { id: 'javascript', name: 'JavaScript', icon: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" fill="#F7DF1E"/><path d="M6 18H9V12.18C9 11.08 9.7 10.82 10.33 10.82C10.94 10.82 11.58 11.08 11.58 12.18V18H14.58V12C14.58 9.92 13.29 8.86 11.2 8.86C9.9 8.86 8.96 9.47 8.52 10.37L8.47 10.37V9H6V18ZM16 17.82C17.15 17.82 17.85 17.11 17.85 16.14C17.85 15.17 17.15 14.46 16 14.46C14.85 14.46 14.15 15.17 14.15 16.14C14.15 17.11 14.85 17.82 16 17.82Z" fill="black"/></svg>' },
    ]
  },
  {
    isGroup: true,
    label: "Scripting & Backend",
    items: [
      { id: 'python', name: 'Python', icon: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9 20H15L19 12V6C19 4.34315 17.6569 3 16 3H8C6.34315 3 5 4.34315 5 6V12L9 20Z" fill="#306998"/><path d="M15 4H9L5 12V18C5 19.6569 6.34315 21 8 21H16C17.6569 21 19 19.6569 19 18V12L15 4Z" fill="#FFD43B"/><circle cx="10" cy="8" r="1.5" fill="white"/><circle cx="14" cy="16" r="1.5" fill="white"/></svg>' },
      { id: 'sql', name: 'SQL', icon: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 3C7.02944 3 3 5.23858 3 8V16C3 18.7614 7.02944 21 12 21C16.9706 21 21 18.7614 21 16V8C21 5.23858 16.9706 3 12 3Z" fill="#00758F"/><path d="M12 4C16.4183 4 20 5.79086 20 8C20 10.2091 16.4183 12 12 12C7.58172 12 4 10.2091 4 8C4 5.79086 7.58172 4 12 4Z" fill="#F29111"/><path d="M4 8V12C4 14.2091 7.58172 16 12 16C16.4183 16 20 14.2091 20 12V8C20 10.2091 16.4183 12 12 12C7.58172 12 4 10.2091 4 8Z" fill="#E8620C"/></svg>' },
      { id: 'bash', name: 'Bash', icon: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 3H21V21H3V3Z" fill="#4EAA25"/><path d="M6 6L10 10L6 14" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 15H18" stroke="white" stroke-width="2" stroke-linecap="round"/></svg>' },
      { id: 'json', name: 'JSON', icon: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="10" fill="#222222"/><path d="M8 9C8 7.34315 9.34315 6 11 6H12C14.2091 6 16 7.79086 16 10V14C16 16.2091 14.2091 18 12 18H11C9.34315 18 8 16.6569 8 15" stroke="white" stroke-width="2.5"/><path d="M16 9C16 7.34315 14.6569 6 13 6H12C9.79086 6 8 7.79086 8 10V14C8 16.2091 9.79086 18 12 18H13C14.6569 18 16 16.6569 16 15" stroke="white" stroke-width="2.5"/></svg>' },
    ]
  },
  {
    isGroup: true,
    label: "Diagrams & Data Viz",
    items: [
      { id: 'svg', name: 'SVG', icon: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 15L9 21H15L12 15Z" fill="#FFB13B"/><path d="M3 14L5 10H1L3 14Z" fill="#FFB13B"/><circle cx="18" cy="7" r="4" fill="#DD5E98"/><path d="M10 3L11 9H22L10 3Z" fill="#42A5F5"/></svg>' },
      { id: 'mermaid', name: 'Mermaid', icon: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="3" width="18" height="18" rx="2" fill="#2E856E"/><path d="M8 8L12 12L8 16" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M13 16H16" stroke="white" stroke-width="2" stroke-linecap="round"/></svg>' },
      { id: 'dot', name: 'Graphviz (dot)', icon: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="6" cy="6" r="3" fill="#3B82F6"/><circle cx="18" cy="6" r="3" fill="#3B82F6"/><circle cx="6" cy="18" r="3" fill="#3B82F6"/><circle cx="18" cy="18" r="3" fill="#3B82F6"/><path d="M8.5 7.5L15.5 16.5" stroke="#9CA3AF" stroke-width="1.5"/><path d="M8.5 16.5L15.5 7.5" stroke="#9CA3AF" stroke-width="1.5"/></svg>' },
    ]
  }
];

function handleReady(payload) {
  view.value = payload.view;
}

function handleCodeChange(newCode) {
  code.value = newCode;
  emit('update:modelValue', newCode);
}

function insertText(text, cursorOffset = 0) {
  if (!view.value) return;
  const { state } = view.value;
  const selection = state.selection.main;
  const transaction = state.update({
    changes: { from: selection.to, insert: text },
    selection: { anchor: selection.to + cursorOffset },
  });
  view.value.dispatch(transaction);
  view.value.focus();
}

function wrapSelection(before, after) {
    if (!view.value) return;
    const { state } = view.value;
    const selection = state.selection.main;
    const selectedText = state.sliceDoc(selection.from, selection.to);

    const transaction = state.update({
        changes: {
            from: selection.from,
            to: selection.to,
            insert: `${before}${selectedText}${after}`,
        },
        selection: { anchor: selection.from + before.length },
    });
    view.value.dispatch(transaction);
    view.value.focus();
}

function insertCodeBlock(lang = '') {
  if (!view.value) return;
  const { state } = view.value;
  const selection = state.selection.main;
  const selectedText = state.sliceDoc(selection.from, selection.to);

  const before = `\`\`\`${lang}\n`;
  const after = `\n\`\`\``;

  if (selectedText) {
    wrapSelection(before, after);
  } else {
    insertText(`${before}${after}`, before.length);
  }
}

function insertTable() {
    const table = `| Header 1 | Header 2 |\n|----------|----------|\n| Cell 1   | Cell 2   |\n|          |          |`;
    insertText(table, 0);
}

const toolbarActions = [
  { icon: 'bold', action: () => wrapSelection('**', '**'), title: 'Bold' },
  { icon: 'italic', action: () => wrapSelection('*', '*'), title: 'Italic' },
  { icon: 'list-ul', action: () => insertText('\n- ', 3), title: 'Unordered List' },
  { icon: 'list-ol', action: () => insertText('\n1. ', 4), title: 'Ordered List' },
  { icon: 'quote', action: () => insertText('\n> ', 3), title: 'Quote' },
  { icon: 'table', action: insertTable, title: 'Insert Table' },
];
</script>

<template>
  <div class="codemirror-container border border-gray-300 dark:border-gray-600 rounded-md">
    <!-- Toolbar -->
    <div class="toolbar flex items-center p-2 bg-gray-100 dark:bg-gray-700 border-b border-gray-300 dark:border-gray-600 space-x-1">
      <!-- Basic Formatting -->
      <button v-for="item in toolbarActions" :key="item.title" @click="item.action" :title="item.title" class="toolbar-btn">
        <!-- SVG Icons -->
        <svg v-if="item.icon === 'bold'" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 2a2 2 0 00-2 2v2H6a2 2 0 00-2 2v8a2 2 0 002 2h4v2a2 2 0 002 2h0a2 2 0 002-2v-2h4a2 2 0 002-2V6a2 2 0 00-2-2h-4V4a2 2 0 00-2-2h0z"/></svg>
        <svg v-if="item.icon === 'italic'" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 4v16m4-16v16M6 4h12M6 20h12"/></svg>
        <svg v-if="item.icon === 'list-ul'" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7"/></svg>
        <svg v-if="item.icon === 'list-ol'" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7M4 6a2 2 0 11-4 0 2 2 0 014 0zM4 12a2 2 0 11-4 0 2 2 0 014 0zM4 18a2 2 0 11-4 0 2 2 0 014 0z"/></svg>
        <svg v-if="item.icon === 'quote'" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z"/></svg>
        <svg v-if="item.icon === 'table'" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
      </button>

      <div class="h-5 border-l border-gray-300 dark:border-gray-500 mx-2"></div>

      <!-- Language Dropdown -->
      <LanguageSelectMenu
        :language-groups="languageGroups"
        @select-language="insertCodeBlock"
      />
    </div>

    <!-- Editor -->
    <Codemirror
      :model-value="code"
      placeholder="What's on your mind? Markdown is supported..."
      :style="{ minHeight: '120px' }"
      :autofocus="true"
      :indent-with-tab="true"
      :tab-size="2"
      :extensions="extensions"
      @ready="handleReady"
      @change="handleCodeChange"
    />
  </div>
</template>

<style>
.cm-editor {
  background-color: transparent;
  outline: none;
}
.cm-scroller {
  padding: 8px;
}
.cm-gutters {
  background-color: transparent !important;
  border-right: none !important;
}
.cm-focused {
    outline: none !important;
    box-shadow: none !important;
}
.toolbar-btn {
  @apply p-1.5 rounded text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600;
}
</style>