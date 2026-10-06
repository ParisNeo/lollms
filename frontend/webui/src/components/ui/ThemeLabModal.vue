<script setup>
import { ref, computed, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';

const uiStore = useUiStore();

const emit = defineEmits(['close']);

const defaultColors = {
    primary: '#3b82f6',
    primaryHover: '#2563eb',
    accent: '#8b5cf6',
    bgApp: '#f8fafc',
    bgCard: '#ffffff',
    bgElevated: '#ffffff',
    borderMain: '#e2e8f0',
    borderStrong: '#cbd5e1',
    textMain: '#0f172a',
    textDim: '#64748b',
    inputBg: '#ffffff'
};

const themeName = ref('My Custom Theme');
const colors = ref({ ...defaultColors });
const borderRadius = ref(0.5);
const borderStrength = ref(1);
const cardOpacity = ref(100);
const isGenerating = ref(false);

const presets = [
    { name: 'Ocean', colors: { primary: '#0ea5e9', primaryHover: '#0284c7', accent: '#22d3ee', bgApp: '#f0f9ff', bgCard: '#ffffff', borderMain: '#bae6fd', textMain: '#0c4a6e', textDim: '#0369a1' } },
    { name: 'Sunset', colors: { primary: '#f97316', primaryHover: '#ea580c', accent: '#f59e0b', bgApp: '#fff7ed', bgCard: '#ffffff', borderMain: '#fed7aa', textMain: '#7c2d12', textDim: '#c2410c' } },
    { name: 'Lavender', colors: { primary: '#8b5cf6', primaryHover: '#7c3aed', accent: '#c084fc', bgApp: '#faf5ff', bgCard: '#ffffff', borderMain: '#e9d5ff', textMain: '#581c87', textDim: '#9333ea' } }
];

function applyPreset(preset) {
    colors.value = { ...preset.colors };
    themeName.value = preset.name + ' Custom';
}

function generateRandomTheme() {
    isGenerating.value = true;
    const hue = Math.floor(Math.random() * 360);
    const sat = 60 + Math.floor(Math.random() * 30);
    const isDark = Math.random() > 0.5;
    
    colors.value = {
        primary: `hsl(${hue}, ${sat}%, 55%)`,
        primaryHover: `hsl(${hue}, ${sat}%, 45%)`,
        accent: `hsl(${(hue + 60) % 360}, ${sat}%, 60%)`,
        bgApp: isDark ? `hsl(${hue}, 20%, 8%)` : `hsl(${hue}, ${sat}%, 98%)`,
        bgCard: isDark ? `hsl(${hue}, 20%, 12%)` : '#ffffff',
        bgElevated: isDark ? `hsl(${hue}, 20%, 16%)` : '#ffffff',
        borderMain: isDark ? `hsl(${hue}, 20%, 20%)` : `hsl(${hue}, ${sat}%, 90%)`,
        borderStrong: isDark ? `hsl(${hue}, 20%, 30%)` : `hsl(${hue}, ${sat}%, 80%)`,
        textMain: isDark ? '#f3f4f6' : `hsl(${hue}, 20%, 10%)`,
        textDim: isDark ? `hsl(${hue}, 15%, 60%)` : `hsl(${hue}, 15%, 40%)`,
        inputBg: isDark ? `hsl(${hue}, 20%, 12%)` : '#ffffff'
    };
    
    setTimeout(() => { isGenerating.value = false; }, 300);
}

function saveTheme() {
    const themeData = {
        name: themeName.value,
        colors: { ...colors.value },
        radius: borderRadius.value,
        borderStrength: borderStrength.value,
        cardOpacity: cardOpacity.value
    };
    uiStore.setCustomTheme(themeData);
    uiStore.addNotification(`Theme "${themeName.value}" applied`, 'success');
    emit('close');
}

onMounted(() => {
    if (uiStore.currentCustomTheme) {
        themeName.value = uiStore.currentCustomTheme.name;
        colors.value = { ...uiStore.currentCustomTheme.colors };
        borderRadius.value = uiStore.currentCustomTheme.radius || 0.5;
        borderStrength.value = uiStore.currentCustomTheme.borderStrength || 1;
        cardOpacity.value = uiStore.currentCustomTheme.cardOpacity || 100;
    }
});
</script>

<template>
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" @click.self="$emit('close')">
        <div class="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
            <!-- Header -->
            <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between bg-gray-50 dark:bg-gray-800/50">
                <div>
                    <h3 class="text-lg font-bold text-gray-900 dark:text-white">Theme Lab</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400">Design your own atmosphere</p>
                </div>
                <button @click="$emit('close')" class="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full transition-colors">
                    <IconXMark class="w-5 h-5 text-gray-500" />
                </button>
            </div>

            <!-- Content -->
            <div class="overflow-y-auto p-6 space-y-6">
                <!-- Name -->
                <div>
                    <label class="block text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">Theme Name</label>
                    <input v-model="themeName" type="text" class="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500" placeholder="My Awesome Theme">
                </div>

                <!-- Presets -->
                <div>
                    <label class="block text-xs font-bold uppercase tracking-wider text-gray-500 mb-2">Quick Presets</label>
                    <div class="flex flex-wrap gap-2">
                        <button v-for="preset in presets" :key="preset.name" 
                                @click="applyPreset(preset)"
                                class="px-3 py-1.5 text-xs font-medium rounded-full border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
                            {{ preset.name }}
                        </button>
                        <button @click="generateRandomTheme" 
                                :disabled="isGenerating"
                                class="px-3 py-1.5 text-xs font-medium rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 text-white hover:opacity-90 transition-opacity flex items-center gap-1">
                            <span v-if="isGenerating">Mixing...</span>
                            <span v-else>🎲 Surprise Me</span>
                        </button>
                    </div>
                </div>

                <!-- Color Grid -->
                <div class="grid grid-cols-2 gap-4">
                    <div v-for="(value, key) in colors" :key="key">
                        <label class="block text-xs font-bold uppercase tracking-wider text-gray-500 mb-2 capitalize">{{ key.replace(/([A-Z])/g, ' $1') }}</label>
                        <div class="flex items-center gap-2">
                            <input v-model="colors[key]" type="color" class="h-10 w-14 rounded cursor-pointer border border-gray-200 dark:border-gray-700 p-1 bg-white dark:bg-gray-800">
                            <input v-model="colors[key]" type="text" class="flex-1 px-2 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md text-xs font-mono focus:ring-1 focus:ring-blue-500">
                        </div>
                    </div>
                </div>

                <!-- Shape & Material -->
                <div class="space-y-4 border-t border-gray-200 dark:border-gray-800 pt-4">
                    <div>
                        <div class="flex items-center justify-between mb-2">
                            <label class="text-xs font-bold uppercase tracking-wider text-gray-500">Corner Radius</label>
                            <span class="text-xs font-mono text-gray-400">{{ borderRadius }}rem</span>
                        </div>
                        <input v-model.number="borderRadius" type="range" min="0" max="1.5" step="0.125" class="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                        <div class="flex justify-between text-[10px] text-gray-400 mt-1 uppercase font-bold">
                            <span>Sharp</span>
                            <span>Round</span>
                        </div>
                    </div>
                    
                    <div>
                        <div class="flex items-center justify-between mb-2">
                            <label class="text-xs font-bold uppercase tracking-wider text-gray-500">Border Width</label>
                            <span class="text-xs font-mono text-gray-400">{{ borderStrength }}px</span>
                        </div>
                        <input v-model.number="borderStrength" type="range" min="0" max="4" step="1" class="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                    </div>
                    
                    <div>
                        <div class="flex items-center justify-between mb-2">
                            <label class="text-xs font-bold uppercase tracking-wider text-gray-500">Surface Opacity</label>
                            <span class="text-xs font-mono text-gray-400">{{ cardOpacity }}%</span>
                        </div>
                        <input v-model.number="cardOpacity" type="range" min="50" max="100" step="5" class="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                    </div>
                </div>

                <!-- Preview Card -->
                <div class="border border-gray-200 dark:border-gray-800 rounded-xl p-4 bg-gray-50 dark:bg-gray-900/50">
                    <label class="block text-xs font-bold uppercase tracking-wider text-gray-500 mb-3">Preview</label>
                    <div class="rounded-lg p-4 border shadow-sm" 
                         :style="{ 
                             backgroundColor: colors.bgCard, 
                             borderColor: colors.borderMain,
                             borderRadius: borderRadius + 'rem'
                         }">
                        <div class="flex items-center gap-2 mb-2">
                            <div class="w-2 h-2 rounded-full" :style="{ backgroundColor: colors.primary }"></div>
                            <span class="text-sm font-medium" :style="{ color: colors.textMain }">Primary Content</span>
                        </div>
                        <div class="text-xs mb-3" :style="{ color: colors.textDim }">Secondary text information with dim color</div>
                        
                        <div class="grid grid-cols-2 gap-2 mb-3">
                            <input type="text" placeholder="Input" class="px-2 py-1.5 text-xs border text-black"
                                   :style="{ 
                                       backgroundColor: colors.inputBg, 
                                       borderColor: colors.borderMain,
                                       borderRadius: borderRadius + 'rem',
                                       borderWidth: borderStrength + 'px'
                                   }">
                            <div class="px-2 py-1.5 text-xs border" 
                                 :style="{ 
                                     backgroundColor: colors.bgElevated, 
                                     borderColor: colors.borderStrong,
                                     borderRadius: borderRadius + 'rem',
                                     color: colors.textMain,
                                     borderWidth: borderStrength + 'px'
                                 }">
                                Elevated
                            </div>
                        </div>
                        
                        <div class="h-8 rounded flex items-center justify-center text-white text-xs font-bold" 
                             :style="{ backgroundColor: colors.primary, borderRadius: borderRadius + 'rem' }">
                            Action Button
                        </div>
                    </div>
                </div>
            </div>

            <!-- Footer -->
            <div class="px-6 py-4 border-t border-gray-200 dark:border-gray-800 flex justify-end gap-3 bg-gray-50 dark:bg-gray-800/50">
                <button @click="$emit('close')" class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors">
                    Cancel
                </button>
                <button @click="saveTheme" class="px-4 py-2 text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-lg shadow-blue-500/30 transition-all flex items-center gap-2">
                    <IconCheckCircle class="w-4 h-4" />
                    Apply Theme
                </button>
            </div>
        </div>
    </div>
</template>