<template>
    <div :class="['markdown-editor-container flex flex-col h-full border border-gray-300 dark:border-gray-600 rounded-md overflow-hidden', editorClass]">
        <Toolbar
            :toolbarClass="toolbarClass"
            :buttonClass="buttonClass"
            :renderable="renderable"
            :currentMode="currentMode"
            :isWrappingEnabled="isWrappingEnabled"
            @format="handleFormat"
            @insert-link="handleInsertLink"
            @insert-image="handleInsertImage"
            @import="handleImport"
            @export="handleExport"
            @set-mode="setMode"
            @toggle-wrapping="toggleWrapping"
        />
        <div class="editor-content flex-1 overflow-auto relative p-1 bg-white dark:bg-gray-800">
            <div v-show="currentMode === 'edit' || !renderable" ref="editorRef" class="editor-wrapper h-full w-full"></div>
            <div v-show="renderable && currentMode === 'view'" class="absolute inset-0 p-2 overflow-y-auto">
                <MessageContentRenderer :content="modelValue" :key="currentMode" />
            </div>
        </div>
        <StatusBar :modelValue="modelValue" :renderable="renderable" />
    </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick, defineExpose } from 'vue';
import { basicSetup } from "codemirror";
import { EditorView, keymap, placeholder as cmPlaceholder } from "@codemirror/view";
import { EditorState, Compartment } from "@codemirror/state";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { languages } from "@codemirror/language-data";
import { html } from "@codemirror/lang-html";
import { python } from "@codemirror/lang-python";
import { javascript } from "@codemirror/lang-javascript";
import { indentWithTab } from "@codemirror/commands";

import { useDiscussionsStore } from '../../../stores/discussions';

import Toolbar from './Toolbar.vue';
import StatusBar from './StatusBar.vue';
import MessageContentRenderer from '../MessageContentRenderer/MessageContentRenderer.vue';

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
    renderable: { type: Boolean, default: false },
    initialMode: { type: String, default: 'edit', validator: (val) => ['edit', 'view'].includes(val) },
    readOnly: { type: Boolean, default: false },
});

const emit = defineEmits(['update:modelValue', 'ready']);

const discussionsStore = useDiscussionsStore();
const editorRef = ref(null);
const editorView = ref(null);
let updatingFromSelf = false;
const currentMode = ref(props.initialMode);
const isWrappingEnabled = ref(true);
let wrappingCompartment = new Compartment();
let readOnlyCompartment = new Compartment();

defineExpose({ editorView });

// --- MODE & WRAPPING ---
const setMode = (mode) => {
    if (['edit', 'view'].includes(mode)) currentMode.value = mode;
};

const toggleWrapping = () => {
    isWrappingEnabled.value = !isWrappingEnabled.value;
    if (editorView.value) {
        editorView.value.dispatch({
            effects: wrappingCompartment.reconfigure(isWrappingEnabled.value ? EditorView.lineWrapping : [])
        });
        editorView.value.focus();
    }
};

watch(currentMode, (newMode) => {
    if (newMode === 'edit') nextTick(() => editorView.value?.focus());
});
watch(() => props.initialMode, (newMode) => {
    if (['edit', 'view'].includes(newMode)) currentMode.value = newMode;
});

// --- EDITOR LOGIC ---
const getLanguageExtension = () => {
    switch (props.language.toLowerCase()) {
        case 'html': return html();
        case 'python': return python();
        case 'javascript': return javascript();
        default: return markdown({ base: markdownLanguage, codeLanguages: languages });
    }
};
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

const handleFormat = (type, options = {}) => {
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

const handleInsertLink = () => {
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

const handleInsertImage = () => {
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

const handleImport = () => {
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

const handleExport = (format) => discussionsStore.exportRawContent({ content: props.modelValue, format });

// --- LIFECYCLE ---
const initializeEditor = () => {
    if (editorView.value) {
        editorView.value.destroy();
    }

    const baseExtensions = [
        basicSetup,
        keymap.of([indentWithTab]),
        getLanguageExtension(),
        wrappingCompartment.of(isWrappingEnabled.value ? EditorView.lineWrapping : []),
        readOnlyCompartment.of(props.readOnly ? [EditorState.readOnly.of(true), EditorView.editable.of(false)] : []),
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

watch(() => props.readOnly, (isReadOnly) => {
    if (editorView.value) {
        editorView.value.dispatch({
            effects: readOnlyCompartment.reconfigure(isReadOnly ? [EditorState.readOnly.of(true), EditorView.editable.of(false)] : [])
        });
    }
});

watch(() => props.modelValue, (newValue) => {
    if (editorView.value && newValue !== editorView.value.state.doc.toString()) {
        updatingFromSelf = true;
        editorView.value.dispatch({
            changes: { from: 0, to: editorView.value.state.doc.length, insert: newValue }
        });
        nextTick(() => { updatingFromSelf = false; });
    }
});

watch(() => props.theme, initializeEditor);
watch(() => props.language, initializeEditor);
onMounted(initializeEditor);
onBeforeUnmount(() => editorView.value?.destroy());
</script>