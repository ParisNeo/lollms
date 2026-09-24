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
    discussionId: { type: String, required: true }
});

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();
const answers = reactive({});
const isSubmitting = ref(false);
const isDone = ref(!!props.form?.submitted);

// Defensive Field Normalizer: Resolves fields across all library/event structures
const resolvedFields = computed(() => {
    if (!props.form) return [];

    let rawFields = null;

    // 1. Direct fields array or object
    if (props.form.fields !== undefined && props.form.fields !== null) {
        rawFields = props.form.fields;
    } else if (props.form.form && props.form.form.fields !== undefined && props.form.form.fields !== null) {
        rawFields = props.form.form.fields;
    } else if (props.form.form_fields !== undefined && props.form.form_fields !== null) {
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
    } else if (Array.isArray(props.form.form)) {
        rawFields = props.form.form;
    }

    // 2. Parse if serialized as a JSON string
    if (typeof rawFields === 'string') {
        const trimmed = rawFields.trim();
        if (trimmed.startsWith('[') || trimmed.startsWith('{')) {
            try {
                const parsed = JSON.parse(trimmed);
                if (Array.isArray(parsed) || (typeof parsed === 'object' && parsed !== null)) {
                    rawFields = parsed;
                }
            } catch (e) {
                // Not valid JSON, continue to XML check
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
        const rawXml = props.form.raw || props.form.content || props.form.raw_xml || (typeof props.form.form === 'string' ? props.form.form : '');
        if (typeof rawXml === 'string' && (rawXml.includes('<field') || rawXml.includes('<lollms_form'))) {
            const extracted = [];
            const fieldRegex = /<field\b([^>]*?)(?:>([\s\S]*?)<\/field>|\/>|\s*>)/gi;
            const matches = [...rawXml.matchAll(fieldRegex)];
            for (const m of matches) {
                const fieldAttrsStr = m[1] || '';
                const innerContent = m[2] || '';
                const fAttrs = {};
                const attrRegex = /(\w+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g;
                for (const ma of fieldAttrsStr.matchAll(attrRegex)) {
                    fAttrs[ma[1]] = ma[2] !== undefined ? ma[2] : ma[3];
                }
                if (innerContent) {
                    const options = [...innerContent.matchAll(/<option[^>]*>([\s\S]*?)<\/option>/gi)].map(om => om[1].trim());
                    if (options.length > 0) {
                        fAttrs.options = options;
                    }
                }
                if (fAttrs.name || fAttrs.label) {
                    extracted.push(fAttrs);
                }
            }
            if (extracted.length > 0) {
                rawFields = extracted;
            }
        }
    }

    return Array.isArray(rawFields) ? rawFields : [];
});

const formTitle = computed(() => {
    return props.form?.title || props.form?.form?.title || props.form?.name || 'Interactive Form';
});

const formDescription = computed(() => {
    return props.form?.description || props.form?.form?.description || '';
});

const formSubmitLabel = computed(() => {
    return props.form?.submit_label || props.form?.form?.submit_label || 'Send Response';
});

// Helper to parse options (handles comma-strings, arrays of strings/objects, and bracketed lists)
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
            console.warn("Failed to parse options string as JSON array:", e);
        }
    }

    if (Array.isArray(opts)) {
        return opts.map(o => {
            if (typeof o === 'object' && o !== null) {
                return o.label || o.value || o.text || o.name || Object.values(o)[0];
            }
            return String(o);
        });
    }

    if (typeof opts === 'string' && opts.trim().length > 0) {
        const separator = opts.includes('\n') ? /\n/ : ',';
        return opts.split(separator).map(o => o.trim()).filter(Boolean);
    }

    return [];
};

const initAnswers = () => {
    const fieldsList = resolvedFields.value;
    if (!Array.isArray(fieldsList) || fieldsList.length === 0) return;

    fieldsList.forEach(field => {
        if (!field || !field.name) return;

        if (answers[field.name] !== undefined) return;

        if (field.default !== undefined) {
            if (field.type === 'checkbox') {
                answers[field.name] = (field.default === 'true' || field.default === true);
            } else if (field.type === 'number' || field.type === 'range') {
                answers[field.name] = Number(field.default);
            } else {
                answers[field.name] = field.default;
            }
        }
        else if (field.type === 'checkbox') answers[field.name] = false;
        else if (field.type === 'number' || field.type === 'range') answers[field.name] = Number(field.min) || 0;
        else if (field.type === 'rating') answers[field.name] = 3;
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

watch(() => props.form?.submitted, (newVal) => {
    isDone.value = Boolean(newVal);
});

async function submitForm() {
    if (resolvedFields.value.length === 0) return;
    isSubmitting.value = true;
    try {
        const formId = props.form.id || props.form.form_id || props.form.form?.id || props.form.form?.form_id || formTitle.value;
        await apiClient.post(`/api/discussions/${props.discussionId}/forms/${encodeURIComponent(formId)}/submit`, {
            answers: { ...answers }
        });
        isDone.value = true;
        uiStore.addNotification("Response submitted successfully.", "success");

        const formattedAnswers = Object.entries(answers)
            .map(([k, v]) => `- **${k}**: ${v}`)
            .join('\n');

        const titleText = formTitle.value;

        discussionsStore.sendMessage({
            prompt: `[FORM_SUBMISSION: ${titleText}]\nUser provided the following data:\n${formattedAnswers}\n\nPlease analyze this data and continue your task.`
        });

    } catch (e) {
        uiStore.addNotification("Failed to submit form data.", "error");
    } finally {
        isSubmitting.value = false;
    }
}
</script>

<template>
    <div class="my-8 border border-gray-200 dark:border-gray-700 rounded-3xl overflow-hidden bg-white dark:bg-gray-900 shadow-2xl transition-all max-w-2xl mx-auto">
        <!-- Form Header -->
        <div class="px-8 py-6 bg-gray-50 dark:bg-gray-800/50 border-b dark:border-gray-800 flex items-center justify-between">
            <div class="flex items-center gap-4">
                <div class="p-3 bg-blue-600 text-white rounded-2xl shadow-lg ring-4 ring-blue-500/10">
                    <IconCheckCircle v-if="isDone" class="w-6 h-6" />
                    <IconPlus v-else class="w-6 h-6" />
                </div>
                <div>
                    <h4 class="font-black text-lg uppercase tracking-tight text-gray-900 dark:text-white">{{ formTitle }}</h4>
                    <p v-if="formDescription" class="text-sm text-gray-500 dark:text-gray-400 mt-1 font-medium">{{ formDescription }}</p>
                </div>
            </div>
            <div v-if="isDone" class="flex items-center gap-2 px-3 py-1.5 bg-green-500/10 text-green-600 dark:text-green-400 rounded-full border border-green-500/20">
                <IconCheckCircle class="w-4 h-4" />
                <span class="text-[10px] font-black uppercase tracking-widest">Locked</span>
            </div>
        </div>

        <!-- Form Fields -->
        <div class="p-8 space-y-8">
            <div v-if="resolvedFields.length === 0" class="text-center py-6 text-xs text-gray-400 italic">
                <IconAnimateSpin v-if="form?.isLoading" class="w-5 h-5 mx-auto mb-2 text-blue-500 animate-spin" />
                <span>{{ form?.isLoading ? 'Loading form fields...' : 'No fields defined for this form.' }}</span>
            </div>

            <div v-for="field in resolvedFields" :key="field.name || field.id" class="group/field transition-all">
                <!-- TYPE: Section / Header -->
                <div v-if="field.type === 'section'" class="pt-6 pb-2 border-b-2 border-gray-100 dark:border-gray-800">
                    <h5 class="text-xs font-black uppercase tracking-[0.2em] text-blue-500">{{ field.label || field.name }}</h5>
                </div>

                <!-- INPUT FIELDS -->
                <template v-else>
                    <div class="flex justify-between items-baseline mb-2">
                        <label class="block text-sm font-black text-gray-700 dark:text-gray-200 uppercase tracking-wide">
                            {{ field.label || field.name }}
                            <span v-if="field.required" class="text-red-500 ml-1">*</span>
                        </label>
                        <span v-if="field.hint" class="text-[10px] font-medium text-gray-400 italic">{{ field.hint }}</span>
                    </div>

                    <!-- TYPE: Text -->
                    <input v-if="field.type === 'text' || !field.type" 
                           v-model="answers[field.name]" 
                           :placeholder="field.placeholder" 
                           class="input-field focus:ring-4 focus:ring-blue-500/10" 
                           :disabled="isDone">

                    <!-- TYPE: Textarea -->
                    <textarea v-else-if="field.type === 'textarea'" 
                              v-model="answers[field.name]" 
                              :rows="field.rows || 4" 
                              class="input-field focus:ring-4 focus:ring-blue-500/10 resize-none" 
                              :disabled="isDone"></textarea>

                    <!-- TYPE: Select (Dropdown) -->
                    <div v-else-if="field.type === 'select'" class="relative">
                        <select v-model="answers[field.name]" 
                                class="input-field appearance-none pr-10 focus:ring-4 focus:ring-blue-500/10" 
                                :disabled="isDone">
                            <option value="" disabled>Select an option...</option>
                            <option v-for="opt in getOptions(field)" :key="opt" :value="opt">{{ opt }}</option>
                        </select>
                        <div class="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none text-gray-400">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                        </div>
                    </div>

                    <!-- TYPE: Radio Buttons -->
                    <div v-else-if="field.type === 'radio'" class="flex flex-wrap gap-6 pt-2">
                        <label v-for="opt in getOptions(field)" :key="opt" class="flex items-center gap-3 cursor-pointer group/radio">
                            <div class="relative flex items-center justify-center">
                                <input type="radio" :name="field.name" :value="opt" v-model="answers[field.name]" :disabled="isDone" class="peer h-5 w-5 border-2 border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500/20 bg-transparent transition-all">
                                <div class="absolute h-2 w-2 rounded-full bg-blue-500 scale-0 peer-checked:scale-100 transition-transform"></div>
                            </div>
                            <span class="text-sm font-bold text-gray-600 dark:text-gray-400 peer-checked:text-gray-900 dark:peer-checked:text-white transition-colors">{{ opt }}</span>
                        </label>
                    </div>

                    <!-- TYPE: Range (Slider) -->
                    <div v-else-if="field.type === 'range'" class="pt-2">
                        <div class="flex items-center gap-6">
                            <input type="range" :min="field.min || 0" :max="field.max || 100" :step="field.step || 1" 
                                   v-model.number="answers[field.name]" 
                                   class="grow h-2 bg-gray-200 dark:bg-gray-800 rounded-lg appearance-none cursor-pointer accent-blue-600" 
                                   :disabled="isDone">
                            <div class="min-w-[4rem] text-center px-3 py-1.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-xl font-mono font-black text-sm border border-blue-100 dark:border-blue-800">
                                {{ answers[field.name] }}
                            </div>
                        </div>
                        <div class="flex justify-between mt-2 text-[10px] font-black uppercase text-gray-400 tracking-widest">
                            <span>{{ field.min || 0 }}</span>
                            <span>{{ field.max || 100 }}</span>
                        </div>
                    </div>

                    <!-- TYPE: Rating (Stars) -->
                    <div v-else-if="field.type === 'rating'" class="flex items-center gap-2 pt-1">
                        <button v-for="i in (Number(field.max) || 5)" :key="i" 
                                @click="!isDone && (answers[field.name] = i)" 
                                type="button"
                                class="text-3xl transition-all transform hover:scale-125" 
                                :class="[
                                    answers[field.name] >= i ? 'text-yellow-400 drop-shadow-sm' : 'text-gray-200 dark:text-gray-700',
                                    isDone ? 'cursor-default' : 'cursor-pointer'
                                ]">
                            ★
                        </button>
                        <span class="ml-4 font-mono font-black text-gray-400 dark:text-gray-500">{{ answers[field.name] }} / {{ field.max || 5 }}</span>
                    </div>

                    <!-- TYPE: Checkbox (Toggle Style) -->
                    <label v-else-if="field.type === 'checkbox'" class="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800/40 rounded-2xl cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors border border-transparent hover:border-blue-200 dark:hover:border-blue-900/30">
                        <span class="text-sm font-bold text-gray-600 dark:text-gray-300">Enable this option</span>
                        <div class="relative inline-flex items-center cursor-pointer">
                            <input type="checkbox" v-model="answers[field.name]" :disabled="isDone" class="sr-only peer">
                            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
                        </div>
                    </label>
                </template>
            </div>
        </div>

        <!-- Form Footer -->
        <div v-if="!isDone" class="px-8 py-6 bg-gray-50 dark:bg-gray-950/40 border-t dark:border-gray-800 flex justify-end">
            <button @click="submitForm" 
                    class="btn btn-primary px-10 py-3 rounded-2xl shadow-xl shadow-blue-500/20 font-black uppercase text-xs tracking-[0.2em] transition-all hover:-translate-y-0.5 active:translate-y-0" 
                    :disabled="isSubmitting">
                <IconAnimateSpin v-if="isSubmitting" class="w-4 h-4 mr-3 animate-spin" />
                {{ form.submit_label || 'Send Response' }}
            </button>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
.input-field {
    @apply w-full px-5 py-3.5 bg-gray-50 dark:bg-gray-800 border-2 border-gray-100 dark:border-gray-700 rounded-2xl text-gray-900 dark:text-white placeholder-gray-400 transition-all outline-none;
}
.input-field:focus {
    @apply border-blue-500 bg-white dark:bg-gray-900;
}
.input-field:disabled {
    @apply opacity-60 grayscale cursor-not-allowed border-gray-200 dark:border-gray-800;
}
</style>