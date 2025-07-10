<script setup>
import { ref } from 'vue';
import { useEditor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Table from '@tiptap/extension-table';
import TableRow from '@tiptap/extension-table-row';
import TableCell from '@tiptap/extension-table-cell';
import TableHeader from '@tiptap/extension-table-header';

const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
});

const emit = defineEmits(['update:modelValue']);

const editor = useEditor({
  content: props.modelValue,
  extensions: [
    StarterKit,
    Link.configure({
      openOnClick: false,
    }),
    Table.configure({
      resizable: true,
    }),
    TableRow,
    TableHeader,
    TableCell,
  ],
  onUpdate: () => {
    emit('update:modelValue', editor.value.getHTML());
  },
  editorProps: {
    attributes: {
      class: 'prose dark:prose-invert prose-sm sm:prose-base lg:prose-lg xl:prose-2xl m-5 focus:outline-none min-h-[200px]',
    },
  },
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
    { icon: 'bold', action: () => editor.value.chain().focus().toggleBold().run(), isActive: () => editor.value?.isActive('bold') },
    { icon: 'italic', action: () => editor.value.chain().focus().toggleItalic().run(), isActive: () => editor.value?.isActive('italic') },
    { icon: 'h-1', action: () => editor.value.chain().focus().toggleHeading({ level: 1 }).run(), isActive: () => editor.value?.isActive('heading', { level: 1 }) },
    { icon: 'h-2', action: () => editor.value.chain().focus().toggleHeading({ level: 2 }).run(), isActive: () => editor.value?.isActive('heading', { level: 2 }) },
    { icon: 'bullet-list', action: () => editor.value.chain().focus().toggleBulletList().run(), isActive: () => editor.value?.isActive('bulletList') },
    { icon: 'ordered-list', action: () => editor.value.chain().focus().toggleOrderedList().run(), isActive: () => editor.value?.isActive('orderedList') },
    { icon: 'link', action: setLink, isActive: () => editor.value?.isActive('link') },
    { icon: 'table', action: () => editor.value.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run() },
]);
</script>

<template>
  <div v-if="editor" class="border border-gray-300 dark:border-gray-600 rounded-md">
    <div class="toolbar flex items-center p-2 border-b border-gray-300 dark:border-gray-600 space-x-1 bg-gray-50 dark:bg-gray-700/50 rounded-t-md">
      <button v-for="action in toolbarActions" :key="action.icon" @click="action.action" type="button" class="toolbar-btn" :class="{'is-active': action.isActive && action.isActive()}">
        <!-- Icons -->
        <span v-if="action.icon === 'bold'" class="font-bold">B</span>
        <span v-if="action.icon === 'italic'" class="italic">I</span>
        <span v-if="action.icon === 'h-1'" class="font-bold text-sm">H1</span>
        <span v-if="action.icon === 'h-2'" class="font-bold text-sm">H2</span>
        <svg v-if="action.icon === 'bullet-list'" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7" /></svg>
        <svg v-if="action.icon === 'ordered-list'" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16" /></svg>
        <svg v-if="action.icon === 'link'" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
        <svg v-if="action.icon === 'table'" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
      </button>
    </div>
    <editor-content :editor="editor" />
  </div>
</template>

<style>
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
    background-color: #374151; /* gray-700 */
}
.dark .tiptap table td, .dark .tiptap table th {
    border: 2px solid #4b5563; /* gray-600 */
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

.toolbar-btn {
    @apply p-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600;
}
.toolbar-btn.is-active {
    @apply bg-blue-500 text-white;
}
</style>