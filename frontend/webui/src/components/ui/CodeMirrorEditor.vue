<template>
    <div :class="['markdown-editor-container  flex flex-col h-full border border-gray-300 dark:border-gray-600 rounded-md overflow-hidden', editorClass]">
        <div :class="['toolbar bg-gray-100 dark:bg-gray-700 p-1 border-b border-gray-300 dark:border-gray-600 flex items-center justify-between', toolbarClass]">
            <div class="flex-1 flex flex-nowrap overflow-x-auto items-center gap-1">
                <ToolbarButton :title="getButtonTitle('bold')" @click="applyFormat('bold')" icon="bold" :button-class="toolbarButtonBaseClass" collection="ui"/>
                <ToolbarButton :title="getButtonTitle('italic')" @click="applyFormat('italic')" icon="italic" :button-class="toolbarButtonBaseClass" collection="ui"/>
                <ToolbarButton :title="getButtonTitle('link')" @click="insertLink" icon="link" :button-class="toolbarButtonBaseClass" collection="ui"/>

                <DropdownMenu title="Text Formatting" icon="type" :button-class="toolbarButtonBaseClass" collection="ui">
                    <ToolbarButton @click="applyFormat('strikethrough')" title="Strikethrough" icon="strikethrough" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Strikethrough</span></ToolbarButton>
                    <ToolbarButton @click="applyFormat('inlinecode')" title="Inline Code" icon="code" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Inline Code</span></ToolbarButton>
                </DropdownMenu>

                <DropdownMenu title="Headings" icon="hash" :button-class="toolbarButtonBaseClass" collection="ui">
                    <ToolbarButton @click="applyFormat('h1')" title="Heading 1" :button-class="toolbarMenuItemClass" class="font-semibold text-lg">Heading 1</ToolbarButton>
                    <ToolbarButton @click="applyFormat('h2')" title="Heading 2" :button-class="toolbarMenuItemClass" class="font-semibold text-base">Heading 2</ToolbarButton>
                    <ToolbarButton @click="applyFormat('h3')" title="Heading 3" :button-class="toolbarMenuItemClass" class="font-semibold text-sm">Heading 3</ToolbarButton>
                </DropdownMenu>

                <DropdownMenu title="Lists" icon="list" :button-class="toolbarButtonBaseClass" collection="ui">
                    <ToolbarButton @click="applyFormat('ul')" title="Unordered List" icon="list" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Unordered List</span></ToolbarButton>
                    <ToolbarButton @click="applyFormat('ol')" title="Ordered List" icon="ordered-list" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Ordered List</span></ToolbarButton>
                </DropdownMenu>

                <DropdownMenu title="Blocks" icon="layout" :button-class="toolbarButtonBaseClass" collection="ui">
                    <ToolbarButton @click="applyFormat('blockquote')" title="Blockquote" icon="blockquote" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Blockquote</span></ToolbarButton>
                    <ToolbarButton @click="applyFormat('hr')" title="Horizontal Rule" icon="minus" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Horizontal Rule</span></ToolbarButton>
                </DropdownMenu>

                <DropdownMenu title="Insert Code Block" icon="code" :button-class="toolbarButtonBaseClass" collection="ui">
                    <ToolbarButton @click="applyFormat('codeblock')" title="Generic Code Block" icon="terminal" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Generic Code</span></ToolbarButton>
                    <div class="my-1 border-t border-gray-200 dark:border-gray-600"></div>
                    
                    <DropdownSubmenu title="Programming Languages" icon="programming" collection="ui">
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'python' })" title="Python" icon="python" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Python</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'javascript' })" title="JavaScript" icon="javascript" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">JavaScript</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'typescript' })" title="TypeScript" icon="typescript" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">TypeScript</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'java' })" title="Java" icon="java" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Java</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'c++' })" title="C++" icon="cplusplus" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">C++</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'csharp' })" title="C#" icon="csharp" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">C#</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'go' })" title="Go" icon="go" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Go</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'rust' })" title="Rust" icon="rust" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Rust</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'swift' })" title="Swift" icon="swift" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Swift</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'kotlin' })" title="Kotlin" icon="kotlin" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Kotlin</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'r' })" title="R" icon="r-project" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">R</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'ruby' })" title="Ruby" icon="ruby" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Ruby</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'php' })" title="PHP" icon="php" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">PHP</span></ToolbarButton>
                    </DropdownSubmenu>
                    <DropdownSubmenu title="Web Technologies" icon="chrome" collection="ui">
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'html' })" title="HTML" icon="html5" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">HTML</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'css' })" title="CSS" icon="css3" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">CSS</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'vue' })" title="Vue.js" icon="vuejs" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Vue.js</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'react' })" title="React" icon="react" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">React</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'angular' })" title="Angular" icon="angular" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Angular</span></ToolbarButton>
                    </DropdownSubmenu>
                    <DropdownSubmenu title="Markup and Data" icon="file-text" collection="ui">
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'xml' })" title="XML" icon="xml" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">XML</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'json' })" title="JSON" icon="json" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">JSON</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'yaml' })" title="YAML" icon="yaml" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">YAML</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'markdown' })" title="Markdown" icon="markdown" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Markdown</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'latex' })" title="LaTeX" icon="latex" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">LaTeX</span></ToolbarButton>
                    </DropdownSubmenu>
                    <DropdownSubmenu title="Scripting and Shell" icon="terminal" collection="ui">
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'bash' })" title="Bash" icon="bash" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Bash</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'powershell' })" title="PowerShell" icon="powershell" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">PowerShell</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'perl' })" title="Perl" icon="perl" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Perl</span></ToolbarButton>
                    </DropdownSubmenu>
                    <DropdownSubmenu title="Diagramming" icon="git-branch" collection="ui">
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'svg' })" title="SVG" icon="svg" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">SVG</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'mermaid' })" title="Mermaid" icon="mermaid" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Mermaid</span></ToolbarButton>
                        <ToolbarButton @click="applyFormat('codeblock', { language: 'graphviz' })" title="Graphviz" icon="graphviz" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Graphviz (dot)</span></ToolbarButton>
                    </DropdownSubmenu>
                </DropdownMenu>

                <DropdownMenu title="LaTeX Equations" icon="sigma" :button-class="toolbarButtonBaseClass" collection="ui">
                    <ToolbarButton @click="applyFormat('latex')" title="Inline Math ($...$)" icon="latex" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Inline Math</span></ToolbarButton>
                    <ToolbarButton @click="applyFormat('latexBlock')" title="Display Math ($$...$$)" icon="latexBlock" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Display Math</span></ToolbarButton>
                </DropdownMenu>

                <DropdownMenu title="File" icon="folder" :button-class="toolbarButtonBaseClass" collection="ui">
                    <ToolbarButton @click="importContent" title="Import from .md" icon="upload" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Import...</span></ToolbarButton>
                    <ToolbarButton @click="exportContent" title="Export as .md" icon="download" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Export as MD</span></ToolbarButton>
                     <DropdownSubmenu v-if="exportFormats.length > 0" title="Export As..." icon="arrow-down-tray" collection="ui">
                        <ToolbarButton v-for="format in exportFormats" :key="format.value" @click="handleExport(format.value)" :button-class="toolbarMenuItemClass">
                            <span class="ml-2">{{ format.label }}</span>
                        </ToolbarButton>
                    </DropdownSubmenu>
                    <ToolbarButton @click="insertImage" title="Image" icon="image" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Insert Image</span></ToolbarButton>
                </DropdownMenu>
                
                <div class="border-l border-gray-300 dark:border-gray-600 h-5 mx-1"></div>
                
                <ToolbarButton 
                    :title="isWrappingEnabled ? 'Disable Text Wrapping' : 'Enable Text Wrapping'" 
                    @click="toggleWrapping" 
                    icon="wrap-text" 
                    :button-class="[toolbarButtonBaseClass, {'bg-blue-100 dark:bg-blue-800/50': isWrappingEnabled}]" 
                    collection="ui"
                />
            </div>
            
            <div v-if="renderable" class="pl-2 flex items-center">
                <div class="flex items-center rounded-md border border-gray-300 dark:border-gray-500 bg-gray-200 dark:bg-gray-900/50 p-0.5">
                    <button @click="setMode('edit')" title="Edit Mode" :class="['px-2.5 py-1 text-sm rounded-md focus:outline-none focus:ring-1 focus:ring-blue-400 flex items-center gap-1.5', currentMode === 'edit' ? 'bg-white dark:bg-gray-600 text-gray-800 dark:text-gray-100 shadow-sm' : 'bg-transparent text-gray-600 dark:text-gray-400 hover:bg-gray-300/50 dark:hover:bg-gray-700/50']">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.5L14.732 3.732z"></path></svg>
                        <span>Edit</span>
                    </button>
                    <button @click="setMode('view')" title="Preview Mode" :class="['px-2.5 py-1 text-sm rounded-md focus:outline-none focus:ring-1 focus:ring-blue-400 flex items-center gap-1.5', currentMode === 'view' ? 'bg-white dark:bg-gray-600 text-gray-800 dark:text-gray-100 shadow-sm' : 'bg-transparent text-gray-600 dark:text-gray-400 hover:bg-gray-300/50 dark:hover:bg-gray-700/50']">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
                        <span>Preview</span>
                    </button>
                </div>
            </div>
        </div>
        <div class="editor-content flex-1 overflow-auto relative p-1 bg-white dark:bg-gray-800">
            <div v-show="currentMode === 'edit' || !renderable" ref="editorRef" class="editor-wrapper h-full w-full"></div>
            <div v-show="renderable && currentMode === 'view'" class="absolute inset-0 p-2 overflow-y-auto">
                <MessageContentRenderer :content="modelValue" :key="currentMode" />
            </div>
        </div>
        <div v-if="renderable" class="statusbar bg-gray-50 dark:bg-gray-700/50 p-1 border-t border-gray-300 dark:border-gray-600 text-xs text-gray-500 dark:text-gray-400 text-right px-2 select-none">
            <span>{{ charCount }} characters, {{ wordCount }} words</span>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick, defineExpose } from 'vue';
import { basicSetup } from "codemirror";
import { EditorView, keymap, placeholder as cmPlaceholder } from "@codemirror/view";
import { EditorState, Compartment } from "@codemirror/state";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { languages } from "@codemirror/language-data";
import { html } from "@codemirror/lang-html";
import { python } from "@codemirror/lang-python";
import { javascript } from "@codemirror/lang-javascript";
import { indentWithTab } from "@codemirror/commands";

import { useAuthStore } from '../../stores/auth';
import { useDiscussionsStore } from '../../stores/discussions';
import DropdownMenu from './DropdownMenu.vue';
import DropdownSubmenu from './DropdownSubmenu.vue';
import ToolbarButton from './ToolbarButton.vue';
import MessageContentRenderer from './MessageContentRenderer.vue';

const props = defineProps({
    modelValue: { type: String, required: true },
    editorClass: { type: [String, Object, Array], default: '' },
    toolbarClass: { type: [String, Object,Array], default: '' },
    buttonClass: { type: [String, Object, Array], default: '' },
    theme: { type: Object, default: null },
    placeholder: { type: String, default: '' },
    autofocus: { type: Boolean, default: false },
    extensions: { type: Array, default: () => [] },
    language: { type: String, default: 'markdown' },
    renderable: { type: Boolean, default: true },
    initialMode: { type: String, default: 'edit', validator: (val) => ['edit', 'view'].includes(val) },
});

const emit = defineEmits(['update:modelValue', 'ready']);

const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const editorRef = ref(null);
const editorView = ref(null);
let updatingFromSelf = false;
const currentMode = ref(props.initialMode);
const isWrappingEnabled = ref(true);
let wrappingCompartment = new Compartment();

defineExpose({ editorView });

// --- STATUS & MODE ---
const charCount = computed(() => props.modelValue.length);
const wordCount = computed(() => props.modelValue.trim() ? props.modelValue.trim().split(/\s+/).length : 0);

const setMode = (mode) => {
    if (['edit', 'view'].includes(mode)) {
        currentMode.value = mode;
    }
};

watch(currentMode, (newMode) => {
    if (newMode === 'edit') {
        nextTick(() => editorView.value?.focus());
    }
});

watch(() => props.initialMode, (newMode) => {
    if (['edit', 'view'].includes(newMode)) {
        currentMode.value = newMode;
    }
});

// --- STYLING ---
const toolbarButtonBaseClass = computed(() => {
    return ['toolbar-btn', props.buttonClass || 'p-1.5 bg-transparent rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400 dark:text-gray-200 flex items-center justify-center h-8 px-2.5'];
});

const toolbarMenuItemClass = computed(() => {
    return 'w-full p-1.5 bg-transparent rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400 dark:text-gray-200 flex items-center justify-start';
});

// --- EXPORT ---
const exportFormats = computed(() => {
    const formats = [];
    if (authStore.export_to_txt_enabled) formats.push({ label: 'Text (.txt)', value: 'txt' });
    if (authStore.export_to_markdown_enabled) formats.push({ label: 'Markdown (.md)', value: 'md' });
    if (authStore.export_to_html_enabled) formats.push({ label: 'HTML (.html)', value: 'html' });
    if (authStore.export_to_pdf_enabled) formats.push({ label: 'PDF (.pdf)', value: 'pdf' });
    if (authStore.export_to_docx_enabled) formats.push({ label: 'Word (.docx)', value: 'docx' });
    if (authStore.export_to_xlsx_enabled) formats.push({ label: 'Excel (.xlsx)', value: 'xlsx' });
    if (authStore.export_to_pptx_enabled) formats.push({ label: 'PowerPoint (.pptx)', value: 'pptx' });
    return formats;
});

function handleExport(format) {
    discussionsStore.exportRawContent({
        content: props.modelValue,
        format: format,
    });
}


// --- FILE OPERATIONS ---
const exportContent = () => {
    const blob = new Blob([props.modelValue], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'document.md';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
};

const importContent = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.md,.txt,text/markdown,text/plain';
    input.onchange = e => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = re => {
            const content = re.target.result;
            emit('update:modelValue', content);
        };
        reader.readAsText(file);
    };
    input.click();
};

// --- EDITOR HELPERS ---
const getSelectedLines = (state) => {
    let lines = [];
    for (let range of state.selection.ranges) {
        const fromLine = state.doc.lineAt(range.from);
        const toLine = state.doc.lineAt(range.to);
        for (let i = fromLine.number; i <= toLine.number; i++) {
            if (!lines.some(l => l.number === i)) lines.push(state.doc.line(i));
        }
    }
    return lines;
};

const needsNewline = (state, pos, isBefore) => {
    if ((isBefore && pos === 0) || (!isBefore && pos === state.doc.length)) return false;
    const surroundingChar = isBefore ? state.doc.sliceString(pos - 1, pos) : state.doc.sliceString(pos, pos + 1);
    return surroundingChar !== '\n';
};

const getButtonTitle = (type) => {
    const map = {
        bold: 'Bold (Ctrl+B)', italic: 'Italic (Ctrl+I)', strikethrough: 'Strikethrough',
        h1: 'Heading 1', h2: 'Heading 2', h3: 'Heading 3', blockquote: 'Blockquote',
        ul: 'Unordered List', ol: 'Ordered List', codeblock: 'Code Block',
        inlinecode: 'Inline Code', link: 'Insert Link', image: 'Insert Image',
        hr: 'Horizontal Rule', latex: 'Inline LaTeX ($...$)', latexBlock: 'LaTeX Block ($$...$$)',
    };
    return map[type] || type;
};

// --- EDITOR ACTIONS ---
const applyFormat = (type, options = {}) => {
    if (!editorView.value) return;
    const view = editorView.value;
    const state = view.state;
    let changes = [];
    const selection = state.selection.main;
    const selectedText = state.doc.sliceString(selection.from, selection.to);
    
    if (type === 'codeblock') {
        const lang = options.language || '';
        const startTag = '```' + lang + '\n';
        const endTag = '\n```';
        
        let textToInsert;
        let selectionStart, selectionEnd;

        if (selectedText) {
            textToInsert = startTag + selectedText + endTag;
            selectionStart = selection.from;
            selectionEnd = selection.from + textToInsert.length;
        } else {
            const placeholder = 'code here';
            textToInsert = startTag + placeholder + endTag;
            selectionStart = selection.from + startTag.length;
            selectionEnd = selectionStart + placeholder.length;
        }
        
        let finalInsertion = textToInsert;
        if (needsNewline(state, selection.from, true) && selection.from > 0) {
            finalInsertion = '\n' + finalInsertion;
            selectionStart += 1;
            selectionEnd += 1;
        }
        if (needsNewline(state, selection.to, false) && selection.to < state.doc.length) {
            finalInsertion += '\n';
        }
        
        view.dispatch({
            changes: { from: selection.from, to: selection.to, insert: finalInsertion },
            selection: { anchor: selectionStart, head: selectionEnd }
        });
        view.focus();
        return;
    }

    let prefix = '', suffix = '', blockPrefix = '';
    let isBlockEnv = false;

    switch (type) {
        case 'bold': prefix = '**'; suffix = '**'; break;
        case 'italic': prefix = '_'; suffix = '_'; break;
        case 'strikethrough': prefix = '~~'; suffix = '~~'; break;
        case 'inlinecode': prefix = '`'; suffix = '`'; break;
        case 'latex': prefix = '$'; suffix = '$'; break;
        case 'h1': blockPrefix = '# '; break;
        case 'h2': blockPrefix = '## '; break;
        case 'h3': blockPrefix = '### '; break;
        case 'blockquote': blockPrefix = '> '; break;
        case 'ul': blockPrefix = '- '; break;
        case 'ol': blockPrefix = '1. '; break;
        case 'latexBlock': prefix = '$$\n'; suffix = '\n$$'; isBlockEnv = true; break;
        case 'hr': changes.push({ from: selection.from, insert: (needsNewline(state, selection.from, true) ? '\n' : '') + '---\n' }); break;
    }

    let effectivePrefix = prefix;
    let effectiveSuffix = suffix;

    if (isBlockEnv) {
        if (needsNewline(state, selection.from, true)) effectivePrefix = '\n' + prefix;
        if (needsNewline(state, selection.to, false)) effectiveSuffix = suffix + '\n';
    }

    if (blockPrefix) {
        const lines = getSelectedLines(state);
        lines.forEach(line => {
            const currentPrefixMatch = line.text.match(/^([#>\-\*]|\d+\.)\s*/);
            const prefixLen = currentPrefixMatch ? currentPrefixMatch[0].length : 0;
            if (currentPrefixMatch && currentPrefixMatch[0].trim() === blockPrefix.trim()) {
                changes.push({ from: line.from, to: line.from + prefixLen, insert: '' });
            } else {
                changes.push({ from: line.from, to: line.from + prefixLen, insert: blockPrefix });
            }
        });
        if (changes.length > 0) view.dispatch({ changes });
    } else if (prefix || suffix) {
        const insert = effectivePrefix + selectedText + effectiveSuffix;
        view.dispatch({
            changes: { from: selection.from, to: selection.to, insert: insert },
            selection: { anchor: selection.from + effectivePrefix.length, head: selection.to + effectivePrefix.length }
        });
    } else if (type === 'hr' && changes.length > 0) {
        view.dispatch({ changes, selection: { anchor: selection.from + changes[0].insert.length } });
    }

    view.focus();
};

const insertLink = () => {
    if (!editorView.value) return;
    const url = prompt("Enter link URL:", "https://");
    if (!url) return;

    const view = editorView.value, state = view.state, selection = state.selection.main;
    const selectedText = state.doc.sliceString(selection.from, selection.to);
    const linkText = selectedText || 'link text';
    const textToInsert = `[${linkText}](${url})`;

    view.dispatch({
        changes: { from: selection.from, to: selection.to, insert: textToInsert },
        selection: selection.empty
            ? { anchor: selection.from + 1, head: selection.from + 1 + linkText.length }
            : { anchor: selection.from + textToInsert.length }
    });
    view.focus();
};

const insertImage = () => {
    if (!editorView.value) return;
    const url = prompt("Enter image URL:", "https://");
    if (!url) return;
    const altText = prompt("Enter alt text:", "image");

    const view = editorView.value, state = view.state, selection = state.selection.main;
    const textToInsert = `![${altText || ''}](${url})`;
    let effectiveInsert = textToInsert;
    if (needsNewline(state, selection.from, true)) effectiveInsert = '\n' + effectiveInsert;
    if (needsNewline(state, selection.to, false) || (selection.empty && needsNewline(state, selection.from, false))) effectiveInsert += '\n';

    view.dispatch({
        changes: { from: selection.from, to: selection.to, insert: effectiveInsert },
        selection: { anchor: selection.from + effectiveInsert.length }
    });
    view.focus();
};

const getLanguageExtension = () => {
    switch (props.language.toLowerCase()) {
        case 'html': return html();
        case 'python': return python();
        case 'javascript': return javascript();
        default: return markdown({ base: markdownLanguage, codeLanguages: languages });
    }
}

const toggleWrapping = () => {
    isWrappingEnabled.value = !isWrappingEnabled.value;
    if (editorView.value) {
        editorView.value.dispatch({
            effects: wrappingCompartment.reconfigure(isWrappingEnabled.value ? EditorView.lineWrapping : [])
        });
        editorView.value.focus();
    }
};

// --- LIFECYCLE & WATCHERS ---
const initializeEditor = () => {
    if (editorView.value) {
        editorView.value.destroy();
    }

    const baseExtensions = [
        basicSetup,
        keymap.of([indentWithTab]),
        getLanguageExtension(),
        wrappingCompartment.of(isWrappingEnabled.value ? EditorView.lineWrapping : []), // Dynamic wrapping
        EditorView.updateListener.of((update) => {
            if (update.docChanged && !updatingFromSelf) {
                emit('update:modelValue', update.state.doc.toString());
            }
        }),
        EditorView.contentAttributes.of({ 'aria-label': 'Markdown editor content' })
    ];

    if (props.placeholder) {
        baseExtensions.push(cmPlaceholder(props.placeholder));
    }

    if (props.theme) {
        baseExtensions.push(props.theme);
    }
    
    const finalExtensions = [...baseExtensions, ...props.extensions];

    const state = EditorState.create({
        doc: props.modelValue,
        extensions: finalExtensions,
    });
    editorView.value = new EditorView({ state, parent: editorRef.value });

    if (props.autofocus) {
        nextTick(() => {
            editorView.value?.focus();
        });
    }

    emit('ready', { view: editorView.value, state: editorView.value.state });
};

watch(() => props.modelValue, (newValue) => {
    if (editorView.value && newValue !== editorView.value.state.doc.toString()) {
        updatingFromSelf = true;
        editorView.value.dispatch({
            changes: { from: 0, to: editorView.value.state.doc.length, insert: newValue }
        });
        nextTick(() => { updatingFromSelf = false; });
    }
});

watch(() => props.theme, () => {
    initializeEditor();
});

watch(() => props.language, () => {
    initializeEditor();
});

onMounted(() => {
    initializeEditor();
});

onBeforeUnmount(() => {
    if (editorView.value) {
        editorView.value.destroy();
    }
});
</script>