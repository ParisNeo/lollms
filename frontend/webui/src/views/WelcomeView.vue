<script setup>
import { computed } from 'vue';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import logoDefault from '../assets/logo.png';

const authStore = useAuthStore();
const uiStore = useUiStore();

const welcomeText = computed(() => authStore.welcomeText);
const welcomeSlogan = computed(() => authStore.welcomeSlogan);
const funFact = computed(() => authStore.funFact);
const logoSrc = computed(() => authStore.welcome_logo_url);
const funFactColor = computed(() => authStore.welcome_fun_fact_color || '#3B82F6');
const funFactCategory = computed(() => authStore.welcome_fun_fact_category);

// --- Contrast checker logic ---
function getContrastTextColor(hexColor) {
    if (!hexColor) return 'text-gray-800 dark:text-gray-100';
    try {
        const r = parseInt(hexColor.slice(1, 3), 16);
        const g = parseInt(hexColor.slice(3, 5), 16);
        const b = parseInt(hexColor.slice(5, 7), 16);
        const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
        return luminance > 0.5 ? 'text-gray-900' : 'text-white';
    } catch (e) {
        console.error("Invalid color format for contrast check:", hexColor);
        return 'text-gray-800 dark:text-gray-100';
    }
}

const funFactTextColorClass = computed(() => getContrastTextColor(funFactColor.value));

const funFactStyle = computed(() => ({
    '--fun-fact-color': funFactColor.value,
    'backgroundColor': `${funFactColor.value}20`,
    'borderColor': funFactColor.value,
}));

const funFactTextStyle = computed(() => ({
    color: funFactColor.value
}));
// --- End Contrast checker logic ---

function openLogin() {
  uiStore.openModal('login');
}
function openRegister() {
  uiStore.openModal('register');
}
</script>

<template>
  <div class="h-screen w-screen bg-gray-100 dark:bg-gray-900 text-gray-800 dark:text-gray-100 flex flex-col items-center justify-center p-6 relative">
    <div class="text-center w-full max-w-2xl">
      <div class="flex justify-center mb-6">
        <img 
          v-if="logoSrc" 
          :src="logoSrc" 
          alt="Custom Logo" 
          class="h-28 w-auto object-contain border-4 border-gray-200 dark:border-gray-700 rounded-lg shadow-md" 
          @error="($event.target.src=logoDefault)"
        />
        <img 
          v-else 
          :src="logoDefault" 
          alt="lollms Logo" 
          class="h-28 w-28 border-4 border-gray-200 dark:border-gray-700 rounded-lg shadow-md"
        >
      </div>
      
      <h1 class="text-6xl md:text-8xl font-bold text-yellow-600 dark:text-yellow-400 drop-shadow-lg" style="font-family: 'Exo 2', sans-serif;">
        {{ welcomeText }}
      </h1>
      <p class="mt-3 text-2xl md:text-3xl text-gray-600 dark:text-gray-300">
        {{ welcomeSlogan }}
      </p>

      <div v-if="funFact" :title="funFactCategory ? `Category: ${funFactCategory}` : 'Fun Fact'" class="mt-10 mx-auto max-w-md p-4 border-l-4 rounded-lg text-sm text-left" :style="funFactStyle" :class="funFactTextColorClass">
        <span class="font-bold" :style="funFactTextStyle">🤓 Fun Fact:</span> {{ funFact }}
      </div>

      <div class="mt-12 flex flex-col sm:flex-row justify-center items-center space-y-4 sm:space-y-0 sm:space-x-4">
        <button @click="openLogin" class="btn btn-primary btn-lg w-full sm:w-auto">
          Sign In
        </button>
        <button @click="openRegister" class="btn btn-secondary btn-lg w-full sm:w-auto">
          Register
        </button>
      </div>
    </div>
    <footer class="absolute bottom-4 w-full text-center text-xs text-gray-500 dark:text-gray-400">
      Powered by <a href="https://github.com/ParisNeo/lollms-webui" target="_blank" class="font-semibold hover:underline">lollms</a> by <a href="https://github.com/ParisNeo" target="_blank" class="font-semibold hover:underline">ParisNeo</a>
    </footer>
  </div>
</template>