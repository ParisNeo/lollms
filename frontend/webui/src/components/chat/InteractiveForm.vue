<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue';
import apiClient from '../../services/api';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const props = defineProps({
    form: { type: Object, required: true },
    discussionId: { type: String, default: '' },
    messageContent: { type: String, default: '' }
});

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();
const activeDiscussionId = computed(() => props.discussionId || discussionsStore.currentDiscussionId || '');
const answers = reactive({});
const isSubmitting = ref(false);
const isDone = ref(!!props.form?.submitted);

// Normalize messy or descriptive types produced by various LLMs
const normalizeFieldType = (type) => {
    if (!type) return 'text';
    const t = String(type).toLowerCase().trim();
    if (t.includes('select') || t.includes('dropdown') || t.includes('combo') || t.includes('choice') || t.includes('menu')) return 'select';
    if (t.includes('radio')) return 'radio';
    if (t.includes('check') || t.includes('bool') || t.includes('toggle') || t.includes('switch')) return 'checkbox';
    if (t.includes('textarea') || t.includes('multiline') || t.includes('paragraph') || t.includes('area') || t.includes('long')) return 'textarea';
    if (t.includes('num') || t.includes('int') || t.includes('float') || t.includes('digit') || t.includes('age') || t.includes('count')) return 'number';
    if (t.includes('range') || t.includes('slider')) return 'range';
    if (t.includes('rating') || t.includes('star') || t.includes('score')) return 'rating';
    if (t.includes('date') || t.includes('calendar') || t.includes('day') || t.includes('year') || t.includes('month')) return 'date';
    if (t.includes('time') || t.includes('hour')) return 'time';
    if (t.includes('email') || t.includes('mail')) return 'email';
    if (t.includes('pass')) return 'password';
    if (t.includes('url') || t.includes('link') || t.includes('web') || t.includes('site')) return 'url';
    if (t.includes('section') || t.includes('header') || t.includes('divider') || t.includes('title')) return 'section';
    return 'text';
};

function getFallbackOptions(label, name) {
    const combined = `${label || ''} ${name || ''}`.toLowerCase();
    if (combined.includes('lang')) {
        return ['Python', 'JavaScript', 'TypeScript', 'C++', 'Java', 'Rust', 'Go'];
    }
    if (combined.includes('experience') || combined.includes('level')) {
        return ['Beginner', 'Intermediate', 'Advanced', 'Expert'];
    }
    if (combined.includes('status')) {
        return ['Active', 'Pending', 'Completed'];
    }
    if (combined.includes('gender')) {
        return ['Female', 'Male', 'Non-binary', 'Prefer not to say'];
    }
    return ['Option 1', 'Option 2', 'Option 3'];
}

const LINE_SPEC_TYPE_PHRASE_RE = /^(text|textarea|number|select|multiselect|radio|checkbox|date|time|datetime|datetime-local|slider|range|rating|email|password|url|tel|color|file)(\s+(dropdown|input|field|buttons?|picker|control|box|area))?$/i;
const isValidLineSpecType = (rawType) => LINE_SPEC_TYPE_PHRASE_RE.test(String(rawType || '').trim());
const sanitizeForLineSpec = (txt) => String(txt || '')
    .replace(/<lollms_inline\b[\s\S]*?(?:<\/lollms_inline>|$)/gi, '\n')
    .replace(/<lollms_form\b[\s\S]*?(?:<\/lollms_form>|$)/gi, '\n')
    .replace(/<processing\b[\s\S]*?(?:<\/processing>|$)/gi, '\n')
    .replace(/<lollms_widget\b[^>]*\/?>/gi, '\n')
    .replace(/```[\s\S]*?```/g, '\n')
    .replace(/`[^`\n]*`/g, ' ');

function parseTextLinesForFields(rawText) {
    if (!rawText || typeof rawText !== 'string') return [];
    const sanitized = sanitizeForLineSpec(rawText);
    const lines = sanitized.split('\n');
    const fields = [];
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('<') || trimmed.startsWith('#')) continue;
        const match = trimmed.match(/^(?:[-*•]|\d+\.)?\s*([A-Za-z0-9_][A-Za-z0-9_\s]*?)\s*(?:—|–|\s-\s|:|\|)\s*([A-Za-z0-9_\s\(\)\/]+?)$/i);
        if (match) {
            const rawLabel = match[1].trim().replace(/^[*_]+|[*_]+$/g, '');
            const rawType = match[2].trim();
            if (!isValidLineSpecType(rawType) || !rawLabel || rawLabel.length < 2) continue;
            const normType = normalizeFieldType(rawType);
            const name = rawLabel.toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '');
            fields.push({
                name: name || `field_${fields.length + 1}`,
                label: rawLabel,
                type: normType
            });
        }
    }
    return fields;
}

// Defensive Field Normalizer: Resolves fields across all library/event structures
const resolvedFields = computed(() => {
    if (!props.form) return [];

    let rawFields = null;

    // 1. Direct fields array or object
    if (props.form.fields !== undefined && props.form.fields !== null && (Array.isArray(props.form.fields) ? props.form.fields.length > 0 : true)) {
        rawFields = props.form.fields;
    } else if (props.form.form && props.form.form.fields !== undefined && props.form.form.fields !== null && (Array.isArray(props.form.form.fields) ? props.form.form.fields.length > 0 : true)) {
        rawFields = props.form.form.fields;
    } else if (props.form.form_fields !== undefined && props.form.form_fields !== null && (Array.isArray(props.form.form_fields) ? props.form.form_fields.length > 0 : true)) {
        rawFields = props.form.form_fields;
    } else if (props.form.elements !== undefined && props.form.elements !== null) {
        rawFields = props.form.elements;
    } else if (props.form.inputs !== undefined && props.form.inputs !== null) {
        rawFields = props.form.inputs;
    } else if (props.form.items !== undefined && props.form.items !== null) {
        rawFields = props.form.items;
    } else if (props.form.data?.fields !== undefined && props.form.data?.fields !== null) {
        rawFields = props.form.data.fields;
    } else if (props.form.content?.fields !== undefined && props.form.content?.fields !== null) {
        rawFields = props.form.content.fields;
    } else if (Array.isArray(props.form.form) && props.form.form.length > 0) {
        rawFields = props.form.form;
    }

    // 2. Parse if serialized as a JSON string
    if (typeof rawFields === 'string') {
        const trimmed = rawFields.trim();
        if (trimmed.startsWith('[') || trimmed.startsWith('{')) {
            try {
                const parsed = JSON.parse(trimmed);
                if (Array.isArray(parsed) || (typeof parsed === 'object' && parsed !== null)) {
                    rawFields = parsed.fields || parsed.form_fields || parsed;
                }
            } catch (e) {
                // Continue
            }
        }
    }

    // 3. Convert dictionary/object to array if keyed by field name
    if (rawFields && typeof rawFields === 'object' && !Array.isArray(rawFields)) {
        rawFields = Object.entries(rawFields).map(([key, val]) => {
            if (typeof val === 'object' && val !== null) {
                return { name: val.name || key, ...val };
            }
            return { name: key, label: String(val), type: 'text' };
        });
    }

    // 4. In-place XML parser fallback if raw markup is present
    if (!rawFields || (Array.isArray(rawFields) && rawFields.length === 0)) {
        const rawXml = props.form.raw || props.form.content || props.form.raw_xml || (typeof props.form.form === 'string' ? props.form.form : '') || (typeof props.form.description === 'string' && props.form.description.includes('<field') ? props.form.description : '');
        if (typeof rawXml === 'string') {
            const extracted = [];
            const fieldRegex = /<field\b([^>]*?)(?:>(.*?)<\/field>|\s*\/?>|>)/gis;
            const matches = [...rawXml.matchAll(fieldRegex)];
            for (const m of matches) {
                const fieldAttrsStr = m[1] || '';
                const innerContent = (m[2] || '').trim();
                const fAttrs = {};
                const attrRegex = /(\w+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g;
                for (const ma of fieldAttrsStr.matchAll(attrRegex)) {
                    fAttrs[ma[1]] = ma[2] !== undefined ? ma[2] : (ma[3] !== undefined ? ma[3] : ma[4]);
                }
                if (innerContent) {
                    const options = [...innerContent.matchAll(/<option\b([^>]*)>(.*?)<\/option>/gis)].map(om => {
                        const valMatch = (om[1] || '').match(/value=["']([^"']*)["']/i);
                        const val = valMatch ? valMatch[1] : om[2].trim();
                        return { label: om[2].trim() || val, value: val };
                    });
                    if (options.length > 0) {
                        fAttrs.options = options;
                    } else if (!fAttrs.default && !innerContent.includes('<')) {
                        fAttrs.default = innerContent;
                    }
                }
                if (!fAttrs.options && (fAttrs.choices || fAttrs.options_list || fAttrs.values)) {
                    fAttrs.options = fAttrs.choices || fAttrs.options_list || fAttrs.values;
                }
                if (fAttrs.name || fAttrs.label || fAttrs.id) {
                    if (!fAttrs.name && fAttrs.id) fAttrs.name = fAttrs.id;
                    if (!fAttrs.name && fAttrs.label) fAttrs.name = fAttrs.label.toLowerCase().replace(/[^a-z0-9_]+/g, '_');
                    extracted.push(fAttrs);
                }
            }
            if (extracted.length > 0) {
                rawFields = extracted;
            }

            // 5. Line-based field specification fallback (e.g. "Favorite Language — select dropdown")
            if ((!rawFields || rawFields.length === 0) && rawXml) {
                const sanitizedXml = sanitizeForLineSpec(rawXml);
                const lines = sanitizedXml.split('\n').map(l => l.trim()).filter(Boolean);
                const textFields = [];
                for (const line of lines) {
                    if (line.startsWith('<') && line.endsWith('>')) continue;
                    const sepMatch = line.match(/^[-*•]?\s*([A-Za-z0-9_\s]+?)\s*(?:—|–|\s-\s|:)\s*([A-Za-z0-9_\s\(\)]+)$/);
                    if (sepMatch) {
                        const rawLabel = sepMatch[1].trim();
                        const rawType = sepMatch[2].trim();
                        if (!isValidLineSpecType(rawType) || !rawLabel || rawLabel.length < 2) continue;
                        const normType = normalizeFieldType(rawType);
                        textFields.push({
                            name: rawLabel.toLowerCase().replace(/[^a-z0-9_]+/g, '_'),
                            label: rawLabel,
                            type: normType
                        });
                    }
                }
                if (textFields.length > 0) {
                    rawFields = textFields;
                }
            }
        }
    }

    // 6. Direct parent message recovery if fields are empty or only contain the dummy response input
    const isOnlyFallback = !rawFields || rawFields.length === 0 || (rawFields.length === 1 && (rawFields[0].name === 'response' || rawFields[0].name === 'answers'));
    if (isOnlyFallback && props.messageContent) {
        const textFields = parseTextLinesForFields(props.messageContent);
        if (textFields.length > 0) {
            rawFields = textFields;
        }
    }

    if (!Array.isArray(rawFields) || rawFields.length === 0) return [];

    // Ensure all fields have sanitized names, labels, and normalized types
    return rawFields.map((f, idx) => {
        const normType = normalizeFieldType(f.type);
        const name = f.name || f.id || (f.label ? f.label.toLowerCase().replace(/[^a-z0-9_]+/g, '_') : `field_${idx}`);
        const label = f.label || (f.name ? f.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : `Field ${idx + 1}`);
        let opts = f.options || f.choices || f.values;
        if (typeof opts === 'string' && opts.trim()) {
            const sep = opts.includes('\n') ? /\n/ : ',';
            opts = opts.split(sep).map(o => o.trim()).filter(Boolean);
        }
        if ((normType === 'select' || normType === 'radio') && (!opts || opts.length === 0)) {
            opts = getFallbackOptions(label, name);
        }
        return {
            ...f,
            name,
            label,
            type: normType,
            options: opts
        };
    });
});

const formTitle = computed(() => {
    const raw = props.form?.title || props.form?.form?.title || props.form?.name || '';
    if (!raw || ['lollms_form', 'form', 'interactive_form', 'processing', 'process'].includes(raw.toLowerCase().replace(/[^a-z0-9]/g, ''))) {
        return 'Interactive Form';
    }
    return raw.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
});

const formDescription = computed(() => {
    return props.form?.description || props.form?.form?.description || '';
});

const formSubmitLabel = computed(() => {
    return props.form?.submit_label || props.form?.form?.submit_label || 'Send Response';
});

// Normalized options helper: Always outputs [{ label: string, value: string }]
const getOptions = (field) => {
    let opts = field.options || field.choices || field.values || field.items || field.content || [];

    if ((!opts || opts.length === 0) && field.value && Array.isArray(field.value)) {
        opts = field.value;
    }

    if (typeof opts === 'string' && opts.trim().startsWith('[')) {
        try {
            const cleaned = opts.trim().replace(/'/g, '"');
            const parsed = JSON.parse(cleaned);
            if (Array.isArray(parsed)) {
                opts = parsed;
            }
        } catch (e) {
            // Keep fallback
        }
    }

    if (typeof opts === 'string' && opts.trim().length > 0) {
        const separator = opts.includes('\n') ? /\n/ : ',';
        opts = opts.split(separator).map(o => o.trim()).filter(Boolean);
    }

    if (Array.isArray(opts)) {
        return opts.map(o => {
            if (typeof o === 'object' && o !== null) {
                const val = o.value !== undefined ? String(o.value) : (o.id !== undefined ? String(o.id) : (o.label || o.name || ''));
                const lbl = o.label !== undefined ? String(o.label) : (o.title !== undefined ? String(o.title) : (o.name || val));
                return { label: lbl, value: val };
            }
            const s = String(o).trim();
            return { label: s, value: s };
        });
    }

    return [];
};

const initAnswers = () => {
    const fieldsList = resolvedFields.value;
    if (!Array.isArray(fieldsList) || fieldsList.length === 0) {
        if (answers['response'] === undefined) {
            answers['response'] = '';
        }
        return;
    }

    fieldsList.forEach(field => {
        if (!field || !field.name) return;

        if (answers[field.name] !== undefined) return;

        const fType = (field.type || 'text').toLowerCase();

        if (field.default !== undefined && field.default !== null && field.default !== '') {
            if (fType === 'checkbox') {
                answers[field.name] = (field.default === 'true' || field.default === true || field.default === '1');
            } else if (fType === 'number' || fType === 'range') {
                answers[field.name] = Number(field.default);
            } else {
                answers[field.name] = field.default;
            }
        }
        else if (fType === 'checkbox') answers[field.name] = false;
        else if (fType === 'number' || fType === 'range') answers[field.name] = Number(field.min) || 0;
        else if (fType === 'rating') answers[field.name] = 3;
        else if (fType === 'radio') {
            const opts = getOptions(field);
            answers[field.name] = opts.length > 0 ? opts[0].value : '';
        }
        else if (fType === 'select') {
            answers[field.name] = '';
        }
        else answers[field.name] = '';
    });

    if (props.form?.submitted && props.form?.answers) {
        Object.assign(answers, props.form.answers);
    }
};

onMounted(() => {
    initAnswers();
});

watch(resolvedFields, () => {
    initAnswers();
}, { deep: true });

watch(() => [props.form?.submitted, props.form?.answers], ([sub, ans]) => {
    if (sub !== undefined) {
        isDone.value = Boolean(sub);
    }
    if (ans && typeof ans === 'object') {
        Object.assign(answers, ans);
    }
}, { immediate: true, deep: true });

async function submitForm() {
    if (isSubmitting.value || isDone.value) return;
    isSubmitting.value = true;
    try {
        const formId = props.form.id || props.form.form_id || props.form.form?.id || props.form.form?.form_id || 'form';
        const targetDiscussionId = activeDiscussionId.value;

        // 1. Submit answers to backend endpoint
        if (targetDiscussionId) {
            try {
                await apiClient.post(`/api/discussions/${targetDiscussionId}/forms/${encodeURIComponent(formId)}/submit`, {
                    answers: { ...answers }
                });
            } catch (apiErr) {
                console.warn("Backend form submission notice:", apiErr);
            }
        }

        isDone.value = true;
        uiStore.addNotification("Response submitted successfully.", "success");

        // 2. Build structured answers using human-readable field labels
        const fieldsMap = {};
        resolvedFields.value.forEach(f => {
            fieldsMap[f.name] = f.label || f.name;
        });

        const answerEntries = Object.entries(answers);
        const formattedAnswers = answerEntries.length > 0
            ? answerEntries.map(([k, v]) => `* **${fieldsMap[k] || k}**: ${v}`).join('\n')
            : "No field values filled.";

        const promptMessage = `${formattedAnswers}\n\n*Form submitted successfully.*`;

        // 3. Send message so the AI processes the form submission in chat
        await discussionsStore.sendMessage({
            prompt: promptMessage
        });

    } catch (e) {
        console.error("Failed to submit form data:", e);
        uiStore.addNotification("Failed to submit form data.", "error");
    } finally {
        isSubmitting.value = false;
    }
}
</script>

<template>
    <div class="my-4 border border-blue-200/80 dark:border-blue-900/60 rounded-2xl overflow-hidden bg-white dark:bg-gray-900 shadow-lg transition-all max-w-xl mx-auto not-prose">
        <!-- Form Header -->
        <div class="px-5 py-3.5 bg-gradient-to-r from-blue-50/80 to-indigo-50/50 dark:from-blue-950/40 dark:to-gray-800/60 border-b border-blue-100 dark:border-gray-800 flex items-center justify-between">
            <div class="flex items-center gap-3 min-w-0">
                <div class="p-2 bg-blue-600 text-white rounded-xl shadow-xs shrink-0">
                    <IconCheckCircle v-if="isDone" class="w-4 h-4" />
                    <IconPlus v-else class="w-4 h-4" />
                </div>
                <div class="min-w-0">
                    <h4 class="font-bold text-sm tracking-tight text-gray-900 dark:text-white truncate">{{ formTitle }}</h4>
                    <p v-if="formDescription" class="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate">{{ formDescription }}</p>
                </div>
            </div>
            <div v-if="isDone" class="flex items-center gap-1.5 px-2.5 py-1 bg-green-500/10 text-green-600 dark:text-green-400 rounded-full border border-green-500/20 shrink-0">
                <IconCheckCircle class="w-3.5 h-3.5" />
                <span class="text-[9px] font-black uppercase tracking-wider">Submitted</span>
            </div>
        </div>

        <!-- Form Fields Body -->
        <div class="p-5 space-y-4">
            <div v-if="form?.isLoading && resolvedFields.length === 0" class="text-center py-4 text-xs text-gray-400 italic flex items-center justify-center gap-2">
                <IconAnimateSpin class="w-4 h-4 text-blue-500 animate-spin" />
                <span>Loading form questions...</span>
            </div>

            <!-- Fields Render List -->
            <template v-if="resolvedFields.length > 0">
                <div v-for="field in resolvedFields" :key="field.name || field.id" class="group/field transition-all">
                    <!-- TYPE: Section / Header -->
                    <div v-if="field.type === 'section'" class="pt-3 pb-1 border-b dark:border-gray-800">
                        <h5 class="text-xs font-black uppercase tracking-wider text-blue-600 dark:text-blue-400">{{ field.label || field.name }}</h5>
                    </div>

                    <!-- INPUT FIELDS -->
                    <template v-else>
                        <div class="flex justify-between items-baseline mb-1">
                            <label class="block text-xs font-bold text-gray-700 dark:text-gray-200">
                                {{ field.label || field.name }}
                                <span v-if="field.required" class="text-red-500 ml-0.5">*</span>
                            </label>
                            <span v-if="field.hint" class="text-[10px] text-gray-400 italic">{{ field.hint }}</span>
                        </div>

                        <!-- TYPE: Text / Number / Email / Date / Password / Url / Time -->
                        <input v-if="['text', 'number', 'email', 'date', 'password', 'url', 'time'].includes(field.type)" 
                               :type="field.type"
                               v-model="answers[field.name]" 
                               :placeholder="field.placeholder || ''" 
                               :min="field.min"
                               :max="field.max"
                               :step="field.step"
                               class="input-field text-xs py-2 px-3" 
                               :disabled="isDone">

                        <!-- TYPE: Textarea -->
                        <textarea v-else-if="field.type === 'textarea'" 
                                  v-model="answers[field.name]" 
                                  :rows="field.rows || 3" 
                                  class="input-field text-xs py-2 px-3 resize-none" 
                                  :placeholder="field.placeholder || ''"
                                  :disabled="isDone"></textarea>

                        <!-- TYPE: Select (Dropdown) -->
                        <div v-else-if="field.type === 'select'" class="relative">
                            <select v-model="answers[field.name]" 
                                    class="input-field text-xs py-2 px-3 appearance-none pr-8 cursor-pointer" 
                                    :disabled="isDone">
                                <option value="" disabled>{{ field.placeholder || 'Select an option...' }}</option>
                                <option v-for="opt in getOptions(field)" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                            </select>
                            <div class="absolute inset-y-0 right-0 flex items-center pr-2.5 pointer-events-none text-gray-400">
                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                            </div>
                        </div>

                        <!-- TYPE: Radio Buttons -->
                        <div v-else-if="field.type === 'radio'" class="flex flex-wrap gap-4 pt-1">
                            <label v-for="opt in getOptions(field)" :key="opt.value" class="flex items-center gap-2 cursor-pointer select-none">
                                <input type="radio" :name="field.name" :value="opt.value" v-model="answers[field.name]" :disabled="isDone" class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-600 bg-transparent">
                                <span class="text-xs text-gray-700 dark:text-gray-300">{{ opt.label }}</span>
                            </label>
                        </div>

                        <!-- TYPE: Range (Slider) -->
                        <div v-else-if="field.type === 'range'" class="pt-1">
                            <div class="flex items-center gap-4">
                                <input type="range" :min="field.min || 0" :max="field.max || 100" :step="field.step || 1" 
                                       v-model.number="answers[field.name]" 
                                       class="grow h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-600" 
                                       :disabled="isDone">
                                <div class="min-w-[3rem] text-center px-2 py-0.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-lg font-mono font-bold text-xs border border-blue-100 dark:border-blue-800">
                                    {{ answers[field.name] }}
                                </div>
                            </div>
                            <div class="flex justify-between mt-1 text-[9px] font-mono text-gray-400">
                                <span>{{ field.min || 0 }}</span>
                                <span>{{ field.max || 100 }}</span>
                            </div>
                        </div>

                        <!-- TYPE: Rating (Stars) -->
                        <div v-else-if="field.type === 'rating'" class="flex items-center gap-1 pt-1">
                            <button v-for="i in (Number(field.max) || 5)" :key="i" 
                                    @click="!isDone && (answers[field.name] = i)" 
                                    type="button"
                                    class="text-xl transition-all hover:scale-110" 
                                    :class="[
                                        answers[field.name] >= i ? 'text-amber-400' : 'text-gray-300 dark:text-gray-600',
                                        isDone ? 'cursor-default' : 'cursor-pointer'
                                    ]">
                                ★
                            </button>
                            <span class="ml-2 font-mono text-xs text-gray-400">{{ answers[field.name] }} / {{ field.max || 5 }}</span>
                        </div>

                        <!-- TYPE: Checkbox (Toggle Style) -->
                        <label v-else-if="field.type === 'checkbox'" class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800/40 rounded-xl cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors border dark:border-gray-700">
                            <span class="text-xs font-semibold text-gray-700 dark:text-gray-300">{{ field.hint || field.label || 'Enable this option' }}</span>
                            <div class="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" v-model="answers[field.name]" :disabled="isDone" class="sr-only peer">
                                <div class="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                            </div>
                        </label>

                        <!-- Resilient Fallback: Any unrecognized input type renders as standard text input -->
                        <input v-else
                               type="text"
                               v-model="answers[field.name]" 
                               :placeholder="field.placeholder || ''"
                               class="input-field text-xs py-2 px-3" 
                               :disabled="isDone">
                    </template>
                </div>
            </template>

            <!-- Graceful Fallback: Free-Form Response Input when fields are not pre-declared -->
            <div v-else-if="!form?.isLoading" class="space-y-2">
                <div class="flex items-center justify-between">
                    <label class="block text-xs font-bold text-gray-700 dark:text-gray-200">
                        Your Response
                    </label>
                    <span class="text-[10px] text-gray-400 italic">Enter parameters or response</span>
                </div>
                <textarea 
                    v-model="answers['response']" 
                    rows="3" 
                    class="input-field text-xs py-2.5 px-3.5 resize-none w-full" 
                    placeholder="Type your response or answers here..." 
                    :disabled="isDone"
                ></textarea>
            </div>
        </div>

        <!-- Form Footer -->
        <div v-if="!isDone" class="px-5 py-3 bg-gray-50 dark:bg-gray-950/40 border-t dark:border-gray-800 flex justify-end">
            <button @click="submitForm" 
                    class="btn btn-primary px-6 py-2 rounded-xl shadow-md font-bold text-xs uppercase tracking-wider transition-all" 
                    :disabled="isSubmitting">
                <IconAnimateSpin v-if="isSubmitting" class="w-3.5 h-3.5 mr-2 animate-spin" />
                {{ formSubmitLabel }}
            </button>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
.input-field {
    @apply w-full bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 transition-all outline-none;
}
.input-field:focus {
    @apply border-blue-500 bg-white dark:bg-gray-900 ring-2 ring-blue-500/20;
}
.input-field:disabled {
    @apply opacity-60 cursor-not-allowed;
}
</style>