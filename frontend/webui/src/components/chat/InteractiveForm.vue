<script setup>
import { ref, reactive, onMounted, computed } from 'vue';
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
const isDone = ref(!!props.form.submitted);

// Helper to parse options (handles both comma-strings and nested tag arrays)
const getOptions = (field) => {
    // Audit of all possible keys used by various library versions and parsers
    let opts = field.options || field.choices || field.values || field.items || field.content || [];

    // If the field object ITSELF has the options (happens if the parser is flat)
    if ((!opts || opts.length === 0) && field.value && Array.isArray(field.value)) {
        opts = field.value;
    }

    // Handle Array of Objects or Strings
    if (Array.isArray(opts)) {
        return opts.map(o => {
            if (typeof o === 'object' && o !== null) {
                // Return first available text property
                return o.label || o.value || o.text || o.name || Object.values(o)[0];
            }
            return String(o);
        });
    }

    // Handle Comma-Separated Strings (Fallback for less capable parsers)
    if (typeof opts === 'string' && opts.trim().length > 0) {
        // If the string contains newlines, split by line, otherwise by comma
        const separator = opts.includes('\n') ? /\n/ : ',';
        return opts.split(separator).map(o => o.trim()).filter(Boolean);
    }

    return [];
};

onMounted(() => {
    // Initialize defaults based on field types
    props.form.fields.forEach(field => {
        if (field.default !== undefined) {
            // Correctly handle boolean defaults for checkboxes
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

    if (props.form.submitted && props.form.answers) {
        Object.assign(answers, props.form.answers);
    }
});

async function submitForm() {
    isSubmitting.value = true;
    try {
        const formId = props.form.id || props.form.form_id;
        await apiClient.post(`/api/discussions/${props.discussionId}/forms/${formId}/submit`, {
            answers: { ...answers }
        });
        isDone.value = true;
        uiStore.addNotification("Response submitted successfully.", "success");

        // Format the confirmation message for the AI's thread
        const formattedAnswers = Object.entries(answers)
            .map(([k, v]) => `- **${k}**: ${v}`)
            .join('\n');

        const formTitle = props.form.title || 'Form';

        // Send a silent system prompt to trigger AI continuation
        discussionsStore.sendMessage({
            prompt: `[FORM_SUBMISSION: ${formTitle}]\nUser provided the following data:\n${formattedAnswers}\n\nPlease analyze this data and continue your task.`
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
                    <h4 class="font-black text-lg uppercase tracking-tight text-gray-900 dark:text-white">{{ form.title }}</h4>
                    <p v-if="form.description" class="text-sm text-gray-500 dark:text-gray-400 mt-1 font-medium">{{ form.description }}</p>
                </div>
            </div>
            <div v-if="isDone" class="flex items-center gap-2 px-3 py-1.5 bg-green-500/10 text-green-600 dark:text-green-400 rounded-full border border-green-500/20">
                <IconCheckCircle class="w-4 h-4" />
                <span class="text-[10px] font-black uppercase tracking-widest">Locked</span>
            </div>
        </div>

        <!-- Form Fields -->
        <div class="p-8 space-y-8">
            <div v-for="field in form.fields" :key="field.name" class="group/field transition-all">
                <!-- TYPE: Section / Header -->
                <div v-if="field.type === 'section'" class="pt-6 pb-2 border-b-2 border-gray-100 dark:border-gray-800">
                    <h5 class="text-xs font-black uppercase tracking-[0.2em] text-blue-500">{{ field.label }}</h5>
                </div>

                <!-- INPUT FIELDS -->
                <template v-else>
                    <div class="flex justify-between items-baseline mb-2">
                        <label class="block text-sm font-black text-gray-700 dark:text-gray-200 uppercase tracking-wide">
                            {{ field.label }}
                            <span v-if="field.required" class="text-red-500 ml-1">*</span>
                        </label>
                        <span v-if="field.hint" class="text-[10px] font-medium text-gray-400 italic">{{ field.hint }}</span>
                    </div>

                    <!-- TYPE: Text -->
                    <input v-if="field.type === 'text'" 
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