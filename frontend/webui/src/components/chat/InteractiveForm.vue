<script setup>
import { ref, reactive, onMounted } from 'vue';
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

onMounted(() => {
    // Initialize defaults
    props.form.fields.forEach(field => {
        if (field.default !== undefined) answers[field.name] = field.default;
        else if (field.type === 'checkbox') answers[field.name] = false;
        else if (field.type === 'checkbox_group') answers[field.name] = [];
        else if (field.type === 'rating') answers[field.name] = field.min || 1;
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
        uiStore.addNotification("Response submitted.", "success");
        
        // Format answers to send back to the AI
        const formattedAnswers = Object.entries(answers)
            .map(([k, v]) => `- **${k}**: ${v}`)
            .join('\n');
            
        const formTitle = props.form.title || 'Form';
        
        // Trigger the AI to process the submitted form
        discussionsStore.sendMessage({
            prompt: `I have submitted the form "${formTitle}". Here are my answers:\n${formattedAnswers}`
        });

    } catch (e) {
        uiStore.addNotification("Failed to submit form.", "error");
    } finally {
        isSubmitting.value = false;
    }
}
</script>

<template>
    <div class="my-6 border-2 border-blue-100 dark:border-blue-900/30 rounded-3xl overflow-hidden bg-white dark:bg-gray-900 shadow-xl transition-all">
        <!-- Form Header -->
        <div class="px-6 py-4 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 border-b dark:border-gray-800 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="p-2 bg-blue-500 text-white rounded-xl shadow-md">
                    <IconCheckCircle v-if="isDone" class="w-5 h-5" />
                    <IconPlus v-else class="w-5 h-5" />
                </div>
                <div>
                    <h4 class="font-black text-sm uppercase tracking-wider text-gray-800 dark:text-gray-100">{{ form.title }}</h4>
                    <p v-if="form.description" class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ form.description }}</p>
                </div>
            </div>
            <div v-if="isDone" class="text-[10px] font-black uppercase text-green-500 bg-green-500/10 px-2 py-1 rounded-full border border-green-500/20">Submitted</div>
        </div>

        <!-- Form Body -->
        <div class="p-6 space-y-6">
            <div v-for="field in form.fields" :key="field.name" class="space-y-2">
                <!-- Section Header -->
                <div v-if="field.type === 'section'" class="pt-4 border-t dark:border-gray-800">
                    <h5 class="text-xs font-black uppercase tracking-widest text-gray-400">{{ field.label }}</h5>
                </div>

                <template v-else>
                    <label class="block text-xs font-bold text-gray-700 dark:text-gray-300">
                        {{ field.label }}
                        <span v-if="field.required" class="text-red-500 ml-0.5">*</span>
                    </label>

                    <!-- Text / Textarea -->
                    <input v-if="field.type === 'text'" v-model="answers[field.name]" :placeholder="field.placeholder" class="input-field" :disabled="isDone">
                    <textarea v-else-if="field.type === 'textarea'" v-model="answers[field.name]" :rows="field.rows || 4" class="input-field" :disabled="isDone"></textarea>
                    
                    <!-- Select / Radio -->
                    <select v-else-if="field.type === 'select'" v-model="answers[field.name]" class="input-field" :disabled="isDone">
                        <option v-for="opt in field.options.split(',')" :key="opt" :value="opt.trim()">{{ opt.trim() }}</option>
                    </select>

                    <div v-else-if="field.type === 'radio'" class="flex flex-wrap gap-4 pt-1">
                        <label v-for="opt in field.options.split(',')" :key="opt" class="flex items-center gap-2 text-sm cursor-pointer">
                            <input type="radio" :name="field.name" :value="opt.trim()" v-model="answers[field.name]" :disabled="isDone" class="text-blue-600 focus:ring-blue-500">
                            <span>{{ opt.trim() }}</span>
                        </label>
                    </div>

                    <!-- Range / Number -->
                    <div v-else-if="field.type === 'range'" class="flex items-center gap-4">
                        <input type="range" :min="field.min" :max="field.max" :step="field.step" v-model.number="answers[field.name]" class="flex-grow" :disabled="isDone">
                        <span class="text-xs font-mono bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded w-10 text-center">{{ answers[field.name] }}</span>
                    </div>

                    <!-- Rating -->
                    <div v-else-if="field.type === 'rating'" class="flex gap-1">
                        <button v-for="i in (parseInt(field.max) || 5)" :key="i" @click="!isDone && (answers[field.name] = i)" 
                                class="text-2xl transition-all hover:scale-110" :class="answers[field.name] >= i ? 'text-yellow-400' : 'text-gray-300 dark:text-gray-700'">
                            ★
                        </button>
                    </div>

                    <!-- Checkbox -->
                    <label v-else-if="field.type === 'checkbox'" class="flex items-center gap-3 cursor-pointer group">
                        <input type="checkbox" v-model="answers[field.name]" :disabled="isDone" class="rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                        <span class="text-sm text-gray-600 dark:text-gray-400 group-hover:text-gray-900 dark:group-hover:text-gray-200 transition-colors">Enabled</span>
                    </label>
                </template>
            </div>
        </div>

        <!-- Footer -->
        <div v-if="!isDone" class="px-6 py-4 bg-gray-50 dark:bg-gray-950/40 border-t dark:border-gray-800 flex justify-end">
            <button @click="submitForm" class="btn btn-primary px-8 py-2 shadow-lg shadow-blue-500/20" :disabled="isSubmitting">
                <IconAnimateSpin v-if="isSubmitting" class="w-4 h-4 mr-2 animate-spin" />
                {{ form.submit_label || 'Submit Response' }}
            </button>
        </div>
    </div>
</template>