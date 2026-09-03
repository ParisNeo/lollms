import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useTasksStore } from './tasks';

export const usePromptsStore = defineStore('prompts', () => {
    const uiStore = useUiStore();
    const tasksStore = useTasksStore();

    const userPrompts = ref([]);
    const systemPrompts = ref([]);
    const lollmsPrompts = ref([]);
    const isLoading = ref(false);

    const systemPromptsByZooCategory = computed(() => {
        if (!Array.isArray(systemPrompts.value)) return {};
        const categories = {};
        systemPrompts.value.forEach(prompt => {
            const category = prompt.category || 'General';
            if (!categories[category]) {
                categories[category] = [];
            }
            categories[category].push(prompt);
        });
        for (const category in categories) {
            categories[category].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
        }
        const sortedCategories = {};
        Object.keys(categories).sort().forEach(key => {
            sortedCategories[key] = categories[key];
        });
        return sortedCategories;
    });

    const userPromptsByCategory = computed(() => {
        if (!Array.isArray(userPrompts.value)) return {};
        const categories = {};
        userPrompts.value.forEach(prompt => {
            const category = prompt.category || 'General';
            if (!categories[category]) {
                categories[category] = [];
            }
            categories[category].push(prompt);
        });
        for (const category in categories) {
            categories[category].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
        }
        const sortedCategories = {};
        Object.keys(categories).sort().forEach(key => {
            sortedCategories[key] = categories[key];
        });
        return sortedCategories;
    });

    async function fetchPrompts() {
        isLoading.value = true;
        try {
            const response = await apiClient.get('/api/prompts');
            userPrompts.value = response.data.user_prompts || [];
            systemPrompts.value = response.data.system_prompts || [];
            
            // Enhanced default standard prompt templates with rich placeholder configurations
            lollmsPrompts.value = [
                {
                    id: 'default-summarize',
                    name: 'Summarize Text',
                    description: 'Extract concise summaries with selectable length and structure',
                    content: `Provide a @<summary_length>@ summary of the following text, emphasizing the @<focus_area>@:\n\n@<text_to_summarize>@\n\n@<summary_length>@\ntitle: Summary Length\ntype: str\noptions: Concise (1 paragraph), Balanced (3 key paragraphs), Detailed Bullet Points, Executive Brief\ndefault: Balanced (3 key paragraphs)\n@</summary_length>@\n\n@<focus_area>@\ntitle: Key Focus Area\ntype: str\ndefault: Main findings and actionable conclusions\n@</focus_area>@\n\n@<text_to_summarize>@\ntitle: Source Content\ntype: text\nhelp: Paste the text or article you wish to summarize\n@</text_to_summarize>@`
                },
                {
                    id: 'default-translate',
                    name: 'Translate Language',
                    description: 'Translate text to any language with selectable tone',
                    content: `Translate the following text into @<target_language>@ using a @<translation_tone>@ tone:\n\n@<text_to_translate>@\n\n@<target_language>@\ntitle: Target Language\ntype: str\noptions: English, French, Spanish, German, Italian, Portuguese, Arabic, Chinese, Japanese, Russian\ndefault: English\n@</target_language>@\n\n@<translation_tone>@\ntitle: Style & Tone\ntype: str\noptions: Natural & Fluent, Formal/Professional, Academic, Conversational\ndefault: Natural & Fluent\n@</translation_tone>@\n\n@<text_to_translate>@\ntitle: Text to Translate\ntype: text\n@</text_to_translate>@`
                },
                {
                    id: 'default-code-review',
                    name: 'Code Review & Refactor',
                    description: 'Review source code for security, performance, and best practices',
                    content: `Perform a thorough code review on the following @<programming_language>@ code.\nPrimary Goal: @<review_goal>@\n\n\`\`\`@<programming_language>@\n@<source_code>@\n\`\`\`\n\nProvide:\n1. Critical bugs, edge-case failures, or security vulnerabilities\n2. Performance & memory optimizations\n3. Clean refactored implementation with explanations\n\n@<programming_language>@\ntitle: Language\ntype: str\noptions: Python, JavaScript, TypeScript, Rust, Go, C++, Java, PHP, Bash\ndefault: Python\n@</programming_language>@\n\n@<review_goal>@\ntitle: Review Focus\ntype: str\noptions: Security & Edge Cases, Performance & Memory, Clean Architecture (SOLID), Complete Refactoring\ndefault: Security & Edge Cases\n@</review_goal>@\n\n@<source_code>@\ntitle: Source Code\ntype: text\n@</source_code>@`
                },
                {
                    id: 'default-explain-concept',
                    name: 'Explain Concept',
                    description: 'Explain any complex concept tailored to a specific audience level',
                    content: `Explain the concept of **@<concept_name>@** as if I were a @<target_audience>@.\nDepth: @<explanation_depth>@\n\nUse intuitive real-world analogies, step-by-step logic, and clear visual examples.\n\n@<concept_name>@\ntitle: Concept / Topic\ntype: str\ndefault: Quantum Entanglement\n@</concept_name>@\n\n@<target_audience>@\ntitle: Target Audience\ntype: str\noptions: 5-year-old child, High School Student, University Undergrad, Senior Software Engineer, Executive\ndefault: University Undergrad\n@</target_audience>@\n\n@<explanation_depth>@\ntitle: Detail Depth\ntype: str\noptions: Intuitive Overview, Step-by-Step Breakdown, Mathematical & Rigorous Deep Dive\ndefault: Step-by-Step Breakdown\n@</explanation_depth>@`
                },
                {
                    id: 'default-mindmap',
                    name: 'Generate Mermaid Mindmap',
                    description: 'Convert unstructured ideas or text into an interactive MermaidJS diagram',
                    content: `Convert the following subject into a clean, valid MermaidJS @<diagram_type>@ diagram:\nCentral Topic: @<central_topic>@\n\nContext & Information:\n@<source_material>@\n\n@<diagram_type>@\ntitle: Diagram Type\ntype: str\noptions: mindmap, flowchart TD, sequenceDiagram, classDiagram, stateDiagram-v2\ndefault: mindmap\n@</diagram_type>@\n\n@<central_topic>@\ntitle: Central Topic Title\ntype: str\ndefault: Artificial Intelligence System Architecture\n@</central_topic>@\n\n@<source_material>@\ntitle: Additional Details (Optional)\ntype: text\n@</source_material>@`
                },
                {
                    id: 'default-fact-check',
                    name: 'Fact-Check & Verify',
                    description: 'Evaluate assertions, examine veracity, and verify citations',
                    content: `Critically verify and fact-check the following claim or text excerpt:\n\n"@<claim_text>@"\n\nStrictness Level: @<strictness>@\n\nInstructions:\n1. Verify individual assertions against factual knowledge.\n2. Note any inaccuracies, misleading figures, or missing context.\n3. Provide a clear verdict (True, Mostly True, Misleading, False) with reasoning.\n\n@<claim_text>@\ntitle: Claim / Statement to Verify\ntype: text\n@</claim_text>@\n\n@<strictness>@\ntitle: Strictness\ntype: str\noptions: Rigorous & Academic, Balanced, Fast Assessment\ndefault: Rigorous & Academic\n@</strictness>@`
                },
                {
                    id: 'default-grammar-polish',
                    name: 'Polish Grammar & Style',
                    description: 'Enhance clarity, fix grammar, and adapt vocabulary for any tone',
                    content: `Proofread, polish, and enhance the following text in @<target_tone>@ tone:\n\n@<draft_text>@\n\n@<target_tone>@\ntitle: Target Style\ntype: str\noptions: Professional & Polished, Academic Publication, Persuasive Sales Copy, Casual & Engaging\ndefault: Professional & Polished\n@</target_tone>@\n\n@<draft_text>@\ntitle: Draft Text\ntype: text\n@</draft_text>@`
                }
            ];
        } catch (error) {
            console.error("Failed to fetch prompts:", error);
            userPrompts.value = [];
            systemPrompts.value = [];
        } finally {
            isLoading.value = false;
        }
    }

    async function createPrompt(promptData) {
        try {
            const response = await apiClient.post('/api/prompts', promptData);
            userPrompts.value.push(response.data);
            userPrompts.value.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
            uiStore.addNotification('Prompt saved successfully!', 'success');
            return response.data;
        } catch (error) {
            throw error;
        }
    }

    async function updatePrompt(id, promptData) {
        try {
            const response = await apiClient.put(`/api/prompts/${id}`, promptData);
            const index = userPrompts.value.findIndex(p => p.id === id);
            if (index !== -1) {
                userPrompts.value[index] = response.data;
            }
            uiStore.addNotification('Prompt updated successfully!', 'success');
            return response.data;
        } catch (error) {
            throw error;
        }
    }

    async function deletePrompt(id) {
        try {
            await apiClient.delete(`/api/prompts/${id}`);
            userPrompts.value = userPrompts.value.filter(p => p.id !== id);
            uiStore.addNotification('Prompt deleted.', 'success');
        } catch (error) {
            throw error;
        }
    }

    async function generatePrompt(prompt) {
        try {
            const response = await apiClient.post('/api/prompts/generate-with-ai', { prompt });
            tasksStore.addTask(response.data);
            uiStore.addNotification(`Task '${response.data.name}' started.`, 'info');
            return response.data;
        } catch (error) {
            throw error;
        }
    }

    async function sharePrompt(prompt_content, target_username) {
        try {
            const response = await apiClient.post('/api/prompts/share', { prompt_content, target_username });
            uiStore.addNotification(response.data.message || 'Prompt shared successfully!', 'success');
            return true;
        } catch (error) {
            return false;
        }
    }

    async function exportPrompts() {
        try {
            const response = await apiClient.get('/api/prompts/export');
            const dataStr = JSON.stringify(response.data, null, 2);
            const blob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `lollms_prompts_${new Date().toISOString().slice(0, 10)}.json`;
            a.click();
            URL.revokeObjectURL(url);
            uiStore.addNotification('Prompts exported successfully!', 'success');
        } catch (error) {
            console.error("Failed to export prompts:", error);
            uiStore.addNotification('Failed to export prompts.', 'error');
        }
    }

    async function importPrompts(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = async (event) => {
                try {
                    const rawText = event.target.result;
                    let payloadPrompts = [];
                    const ext = (file.name.split('.').pop() || '').toLowerCase();

                    if (ext === 'json') {
                        let parsed = JSON.parse(rawText);
                        if (Array.isArray(parsed)) {
                            payloadPrompts = parsed;
                        } else if (parsed && Array.isArray(parsed.prompts)) {
                            payloadPrompts = parsed.prompts;
                        } else if (parsed && parsed.name && parsed.content) {
                            payloadPrompts = [parsed];
                        }
                    } else if (['md', 'txt'].includes(ext)) {
                        const baseTitle = file.name.replace(/\.[^/.]+$/, '').replace(/_/g, ' ');
                        payloadPrompts = [{
                            name: baseTitle,
                            content: rawText,
                            description: `Imported from ${file.name}`,
                            category: 'Imported'
                        }];
                    } else {
                        throw new Error(`Unsupported prompt file format: .${ext}`);
                    }

                    if (!payloadPrompts || payloadPrompts.length === 0) {
                        throw new Error("No valid prompt templates found in file.");
                    }

                    const response = await apiClient.post('/api/prompts/import', { prompts: payloadPrompts });
                    await fetchPrompts();
                    uiStore.addNotification(response.data.message || `Successfully imported ${payloadPrompts.length} prompt(s).`, 'success');
                    resolve(response.data);
                } catch (error) {
                    const message = error.response?.data?.detail || error.message || 'Failed to import prompts.';
                    uiStore.addNotification(message, 'error');
                    reject(error);
                }
            };
            reader.onerror = (error) => {
                uiStore.addNotification('Failed to read import file.', 'error');
                reject(error);
            };
            reader.readAsText(file);
        });
    }

    return {
        userPrompts,
        systemPrompts,
        lollmsPrompts,
        isLoading,
        systemPromptsByZooCategory,
        userPromptsByCategory,
        fetchPrompts,
        createPrompt,
        updatePrompt,
        deletePrompt,
        generatePrompt,
        sharePrompt,
        exportPrompts,
        importPrompts,
    };
});