<template>
    <div :class="['toolbar bg-gray-100 dark:bg-gray-700 p-1 border-b border-gray-300 dark:border-gray-600 flex items-center justify-between', toolbarClass]">
        <div class="flex-1 flex flex-nowrap overflow-x-auto items-center gap-1">
            
            <!-- Markdown Formatting Group -->
            <template v-if="isMarkdown">
                <ToolbarButton :title="getButtonTitle('bold')" @click="$emit('format', 'bold')" icon="bold" :button-class="toolbarButtonBaseClass" collection="ui"/>
                <ToolbarButton :title="getButtonTitle('italic')" @click="$emit('format', 'italic')" icon="italic" :button-class="toolbarButtonBaseClass" collection="ui"/>
                <ToolbarButton :title="getButtonTitle('link')" @click="$emit('insert-link')" icon="link" :button-class="toolbarButtonBaseClass" collection="ui"/>

                <DropdownMenu title="Text Formatting" icon="type" :button-class="toolbarButtonBaseClass" collection="ui">
                    <ToolbarButton @click="$emit('format', 'strikethrough')" title="Strikethrough" icon="strikethrough" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Strikethrough</span></ToolbarButton>
                    <ToolbarButton @click="$emit('format', 'inlinecode')" title="Inline Code" icon="code" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Inline Code</span></ToolbarButton>
                </DropdownMenu>

                <DropdownMenu title="Headings" icon="hash" :button-class="toolbarButtonBaseClass" collection="ui">
                    <button @click="$emit('format', 'h1')" title="Heading 1" :class="[toolbarMenuItemClass, 'font-semibold text-lg']">Heading 1</button>
                    <button @click="$emit('format', 'h2')" title="Heading 2" :class="[toolbarMenuItemClass, 'font-semibold text-base']">Heading 2</button>
                    <button @click="$emit('format', 'h3')" title="Heading 3" :class="[toolbarMenuItemClass, 'font-semibold text-sm']">Heading 3</button>
                </DropdownMenu>

                <DropdownMenu title="Lists" icon="list" :button-class="toolbarButtonBaseClass" collection="ui">
                    <ToolbarButton @click="$emit('format', 'ul')" title="Unordered List" icon="list" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Unordered List</span></ToolbarButton>
                    <ToolbarButton @click="$emit('format', 'ol')" title="Ordered List" icon="ordered-list" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Ordered List</span></ToolbarButton>
                </DropdownMenu>

                <DropdownMenu title="Blocks" icon="layout" :button-class="toolbarButtonBaseClass" collection="ui">
                    <ToolbarButton @click="$emit('format', 'blockquote')" title="Blockquote" icon="blockquote" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Blockquote</span></ToolbarButton>
                    <ToolbarButton @click="$emit('format', 'hr')" title="Horizontal Rule" icon="minus" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Horizontal Rule</span></ToolbarButton>
                </DropdownMenu>
            </template>

            <!-- Code/Specialized Insertion Group -->
            <DropdownMenu :title="isMarkdown ? 'Insert Code Block' : 'Language Tools'" icon="code" :button-class="toolbarButtonBaseClass" collection="ui">
                
                <!-- IF MARKDOWN: Original Lang selection with fences -->
                <template v-if="isMarkdown">
                    <ToolbarButton @click="$emit('format', 'codeblock')" title="Generic Code Block" icon="terminal" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Generic Code</span></ToolbarButton>
                    <div class="my-1 border-t border-gray-200 dark:border-gray-600"></div>
                    
                    <DropdownSubmenu title="Programming Languages" icon="programming" collection="ui">
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'python' })" title="Python" icon="python" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Python</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'javascript' })" title="JavaScript" icon="javascript" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">JavaScript</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'typescript' })" title="TypeScript" icon="typescript" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">TypeScript</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'java' })" title="Java" icon="java" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Java</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'c++' })" title="C++" icon="cplusplus" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">C++</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'csharp' })" title="C#" icon="csharp" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">C#</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'go' })" title="Go" icon="go" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Go</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'rust' })" title="Rust" icon="rust" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Rust</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'swift' })" title="Swift" icon="swift" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Swift</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'kotlin' })" title="Kotlin" icon="kotlin" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Kotlin</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'r' })" title="R" icon="r-project" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">R</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'ruby' })" title="Ruby" icon="ruby" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Ruby</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'php' })" title="PHP" icon="php" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">PHP</span></ToolbarButton>
                    </DropdownSubmenu>
                    <DropdownSubmenu title="Web Technologies" icon="chrome" collection="ui">
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'html' })" title="HTML" icon="html5" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">HTML</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'css' })" title="CSS" icon="css3" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">CSS</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'vue' })" title="Vue.js" icon="vuejs" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Vue.js</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'react' })" title="React" icon="react" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">React</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'angular' })" title="Angular" icon="angular" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Angular</span></ToolbarButton>
                    </DropdownSubmenu>
                    <DropdownSubmenu title="Markup and Data" icon="file-text" collection="ui">
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'xml' })" title="XML" icon="xml" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">XML</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'json' })" title="JSON" icon="json" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">JSON</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'yaml' })" title="YAML" icon="yaml" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">YAML</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'markdown' })" title="Markdown" icon="markdown" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Markdown</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'latex' })" title="LaTeX" icon="latex" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">LaTeX</span></ToolbarButton>
                    </DropdownSubmenu>
                    <DropdownSubmenu title="Scripting and Shell" icon="terminal" collection="ui">
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'bash' })" title="Bash" icon="bash" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Bash</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'powershell' })" title="PowerShell" icon="powershell" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">PowerShell</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'perl' })" title="Perl" icon="perl" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Perl</span></ToolbarButton>
                    </DropdownSubmenu>
                    <DropdownSubmenu title="Diagramming" icon="git-branch" collection="ui">
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'svg' })" title="SVG" icon="svg" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">SVG</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'mermaid' })" title="Mermaid" icon="mermaid" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Mermaid</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'codeblock', { language: 'graphviz' })" title="Graphviz" icon="graphviz" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Graphviz (dot)</span></ToolbarButton>
                    </DropdownSubmenu>
                </template>

                <!-- IF NOT MARKDOWN: Specific raw snippet tools -->
                <template v-else>
                    <!-- Python Snippets -->
                    <template v-if="language === 'python'">
                        <ToolbarButton @click="$emit('format', 'insert', { code: 'def my_function():\n    pass' })" title="Function" icon="python" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">New Function</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'insert', { code: 'class MyClass:\n    def __init__(self):\n        pass' })" title="Class" icon="python" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">New Class</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'insert', { code: 'for i in range(10):\n    print(i)' })" title="For Loop" icon="python" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">For Loop</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'insert', { code: 'if __name__ == \'__main__\':\n    main()' })" title="Main block" icon="python" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Main block</span></ToolbarButton>
                    </template>

                    <!-- HTML Snippets -->
                    <template v-else-if="language === 'html'">
                        <ToolbarButton @click="$emit('format', 'insert', { code: '<div>\n    \n</div>' })" title="Div" icon="html5" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Div Block</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'insert', { code: '<img src=\'URL\' alt=\'description\' />' })" title="Image" icon="html5" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Image Tag</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'insert', { code: '<script>\n    \n</script>' })" title="Script" icon="html5" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Script Tag</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'insert', { code: '<!-- comment -->' })" title="Comment" icon="html5" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Comment</span></ToolbarButton>
                    </template>

                    <!-- JS/TS Snippets -->
                    <template v-else-if="language === 'javascript' || language === 'typescript'">
                        <ToolbarButton @click="$emit('format', 'insert', { code: 'console.log();' })" title="Log" icon="javascript" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Console Log</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'insert', { code: 'const myFunc = () => {\n    \n};' })" title="Arrow" icon="javascript" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Arrow Function</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'insert', { code: 'async function fetchData() {\n    const res = await fetch(url);\n    return res.json();\n}' })" title="Fetch" icon="javascript" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Async Fetch</span></ToolbarButton>
                    </template>

                    <!-- Mermaid Snippets -->
                    <template v-else-if="language === 'mermaid'">
                        <ToolbarButton @click="$emit('format', 'insert', { code: 'A[Start] --> B(Process)\nB --> C{Decision}\nC -->|Yes| D[End]\nC -->|No| E[End]' })" title="Flowchart" icon="mermaid" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Flowchart</span></ToolbarButton>
                        <ToolbarButton @click="$emit('format', 'insert', { code: 'sequenceDiagram\n    Alice->>John: Hello John, how are you?\n    John-->>Alice: Great!' })" title="Sequence" icon="mermaid" collection="languages" :button-class="toolbarMenuItemClass"><span class="ml-2">Sequence</span></ToolbarButton>
                    </template>

                    <div v-else class="px-3 py-2 text-xs text-gray-500 italic">No specific snippets for this language.</div>
                </template>
            </DropdownMenu>

            <DropdownMenu title="LaTeX Equations" icon="sigma" :button-class="toolbarButtonBaseClass" collection="ui">
                <ToolbarButton @click="$emit('format', 'latex')" title="Inline Math ($...$)" icon="latex" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Inline Math</span></ToolbarButton>
                <ToolbarButton @click="$emit('format', 'latexBlock')" title="Display Math ($$...$$)" icon="latexBlock" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Display Math</span></ToolbarButton>
            </DropdownMenu>

            <DropdownMenu title="File" icon="folder" :button-class="toolbarButtonBaseClass" collection="ui">
                <ToolbarButton @click="$emit('import')" title="Import from .md" icon="upload" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Import...</span></ToolbarButton>
                <ToolbarButton @click="$emit('export', 'md')" title="Export as .md" icon="download" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Export as MD</span></ToolbarButton>
                <DropdownSubmenu v-if="exportFormats.length > 0" title="Export As..." icon="arrow-down-tray" collection="ui">
                    <ToolbarButton v-for="format in exportFormats" :key="format.value" @click="$emit('export', format.value)" :button-class="toolbarMenuItemClass" icon="file-text" collection="ui">
                        <span class="ml-2">{{ format.label }}</span>
                    </ToolbarButton>
                </DropdownSubmenu>
                <ToolbarButton @click="$emit('insert-image')" title="Image" icon="image" collection="ui" :button-class="toolbarMenuItemClass"><span class="ml-2">Insert Image</span></ToolbarButton>
            </DropdownMenu>
            
            <div class="border-l border-gray-300 dark:border-gray-600 h-5 mx-1"></div>
            
            <ToolbarButton 
                :title="isWrappingEnabled ? 'Disable Text Wrapping' : 'Enable Text Wrapping'" 
                @click="$emit('toggle-wrapping')" 
                icon="wrap-text" 
                :button-class="[toolbarButtonBaseClass, {'bg-blue-100 dark:bg-blue-800/50': isWrappingEnabled}]" 
                collection="ui"
            />
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue';
import { useAuthStore } from '../../../stores/auth';
import ToolbarButton from '../ToolbarButton.vue';
import DropdownMenu from '../DropdownMenu/DropdownMenu.vue';
import DropdownSubmenu from '../DropDownMenu/DropdownSubmenu.vue';

const props = defineProps({
    toolbarClass: { type: [String, Object, Array], default: '' },
    buttonClass: { type: [String, Object, Array], default: '' },
    language: { type: String, default: 'markdown' },
    currentMode: { type: String, default: 'edit' },
    isWrappingEnabled: { type: Boolean, default: true },
});

const isMarkdown = computed(() => props.language?.toLowerCase() === 'markdown');

defineEmits(['format', 'insert-link', 'insert-image', 'import', 'export', 'set-mode', 'toggle-wrapping']);

const authStore = useAuthStore();

const toolbarButtonBaseClass = computed(() => {
    return ['toolbar-btn', props.buttonClass || 'p-1.5 bg-transparent rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400 dark:text-gray-200 flex items-center justify-center h-8 px-2.5'];
});

const toolbarMenuItemClass = computed(() => {
    return 'w-full p-1.5 bg-transparent rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400 dark:text-gray-200 flex items-center justify-start';
});

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
</script>

<style scoped>
.mode-button {
    @apply px-2.5 py-1 text-sm rounded-md focus:outline-none focus:ring-1 focus:ring-blue-400 flex items-center gap-1.5;
}
.mode-button.active {
    @apply bg-white dark:bg-gray-600 text-gray-800 dark:text-gray-100 shadow-sm;
}
.mode-button.inactive {
    @apply bg-transparent text-gray-600 dark:text-gray-400 hover:bg-gray-300/50 dark:hover:bg-gray-700/50;
}
</style>    