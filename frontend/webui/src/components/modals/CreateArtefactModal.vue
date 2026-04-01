<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from './GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';

// Icons
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const modalData = computed(() => uiStore.modalData('createArtefact'));
const discussionId = computed(() => modalData.value?.discussionId || discussionsStore.currentDiscussionId);

const title = ref('');
const content = ref('');
const isLoading = ref(false);
const selectedLanguage = ref('markdown');

const languages = [
    { id: 'markdown', name: 'Markdown', ext: '.md' },
    { id: 'python', name: 'Python', ext: '.py' },
    { id: 'html', name: 'HTML', ext: '.html' },
    { id: 'javascript', name: 'Javascript', ext: '.js' },
    { id: 'typescript', name: 'Typescript', ext: '.ts' },
    { id: 'css', name: 'CSS', ext: '.css' },
    { id: 'svg', name: 'SVG', ext: '.svg' },
    { id: 'mermaid', name: 'Mermaid Diagram', ext: '.mermaid' },
    { id: 'latex', name: 'LaTeX', ext: '.tex' },
    { id: 'json', name: 'JSON', ext: '.json' },
    { id: 'yaml', name: 'YAML', ext: '.yaml' },
    { id: 'sql', name: 'SQL', ext: '.sql' },
    { id: 'cpp', name: 'C++', ext: '.cpp' },
    { id: 'code', name: 'Generic Code', ext: '.txt' },
];

const snippets = {
    mermaid: [
        { label: 'Flowchart', code: 'graph TD\n    A[Start] --> B{Is it?}\n    B -- Yes --> C[OK]\n    B -- No --> D[End]' },
        { label: 'Sequence', code: 'sequenceDiagram\n    Alice->>Bob: Hello Bob, how are you?\n    Bob-->>Alice: Jolly good!' },
        { label: 'Class', code: 'classDiagram\n    Animal <|-- Duck\n    class Animal{\n        +int age\n        +move()\n    }' }
    ],
    html: [
        { label: 'Image', code: '<img src="URL" alt="Description" />' },
        { label: 'Link', code: '<a href="URL">Text</a>' },
        { label: 'Div Container', code: '<div class="container">\n    \n</div>' },
        { label: 'Basic Table', code: '<table>\n  <tr>\n    <th>Header</th>\n  </tr>\n  <tr>\n    <td>Data</td>\n  </tr>\n</table>' }
    ],
    python: [
        { label: 'Main Function', code: 'def main():\n    print("Hello World")\n\nif __name__ == "__main__":\n    main()' },
        { label: 'Class Template', code: 'class MyClass:\n    def __init__(self):\n        pass' },
        { label: 'List Comp', code: '[x for x in range(10) if x % 2 == 0]' }
    ],
    latex: [
        { label: 'Document', code: '\\documentclass{article}\n\\begin{document}\n\n\\end{document}' },
        { label: 'Equation', code: '\\begin{equation}\n    e=mc^2\n\\end{equation}' }
    ],
    svg: [
        { label: 'Circle', code: '<circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" />' },
        { label: 'Rect', code: '<rect width="300" height="100" style="fill:rgb(0,0,255);stroke-width:3;stroke:rgb(0,0,0)" />' }
    ]
};

const currentSnippets = computed(() => snippets[selectedLanguage.value] || []);

watch(() => uiStore.isModalOpen('createArtefact'), (isOpen) => {
    if (isOpen) {
        title.value = 'Untitled Document.md';
        content.value = '';
        selectedLanguage.value = 'markdown';
    }
});

// Update title extension when language changes
watch(selectedLanguage, (newLang) => {
    const langObj = languages.find(l => l.id === newLang);
    if (langObj && title.value.includes('.')) {
        const base = title.value.split('.')[0];
        title.value = base + langObj.ext;
    }
});

function insertSnippet(snippetCode) {
    if (!content.value.trim()) {
        content.value = snippetCode;
    } else {
        content.value += '\n\n' + snippetCode;
    }
}

async function handleSubmit() {
    if (!discussionId.value) {
        uiStore.addNotification('No discussion selected.', 'error');
        return;
    }
    if (!title.value.trim()) {
        uiStore.addNotification('Title is required.', 'warning');
        return;
    }
    
    isLoading.value = true;
    try {
        await discussionsStore.createManualArtefact({
            discussionId: discussionId.value,
            title: title.value.trim(),
            content: content.value,
            imagesB64: []
        });
        uiStore.closeModal('createArtefact');
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modalName="createArtefact"
        title="Create New Document"
        maxWidthClass="max-w-4xl"
    >
        <template #body>
            <div class="space-y-4 p-1 h-full flex flex-col">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div class="md:col-span-2">
                        <label for="artefact-title" class="label">Document Title</label>
                        <div class="relative mt-1">
                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                <IconFileText class="h-4 w-4 text-gray-400" />
                            </div>
                            <input
                                id="artefact-title"
                                v-model="title"
                                type="text"
                                class="input-field pl-10"
                                placeholder="e.g. My Notes.md"
                                required
                            />
                        </div>
                    </div>
                    <div>
                        <label for="artefact-type" class="label">Language / Format</label>
                        <select v-model="selectedLanguage" class="input-field mt-1">
                            <option v-for="lang in languages" :key="lang.id" :value="lang.id">
                                {{ lang.name }} ({{ lang.ext }})
                            </option>
                        </select>
                    </div>
                </div>

                <div v-if="currentSnippets.length > 0" class="flex flex-wrap gap-2 py-1">
                    <span class="text-[10px] font-black uppercase text-gray-400 self-center mr-2">Quick Snippets:</span>
                    <button 
                        v-for="s in currentSnippets" 
                        :key="s.label"
                        @click="insertSnippet(s.code)"
                        class="px-2 py-1 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-blue-500 hover:text-white text-[10px] font-bold transition-all border dark:border-gray-700"
                    >
                        + {{ s.label }}
                    </button>
                </div>

                <div class="flex-grow flex flex-col min-h-[400px]">
                    <label class="label mb-1">Content</label>
                    <div class="flex-grow border border-gray-300 dark:border-gray-600 rounded-md overflow-hidden relative shadow-inner">
                        <CodeMirrorEditor 
                            v-model="content" 
                            class="h-full absolute inset-0"
                            :language="selectedLanguage"
                            :allowedModes="'both'"
                            placeholder="Start typing or use a snippet above..."
                        />
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('createArtefact')" type="button" class="btn btn-secondary">Cancel</button>
                <button @click="handleSubmit" type="button" class="btn btn-primary" :disabled="isLoading || !title.trim()">
                    <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
                    Create & Load
                </button>
            </div>
        </template>
    </GenericModal>
</template>