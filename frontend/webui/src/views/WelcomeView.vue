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

const funFactStyle = computed(() => ({
    '--fun-fact-color': funFactColor.value,
    'backgroundColor': `${funFactColor.value}20`,
    'borderColor': funFactColor.value,
}));

const funFactTextStyle = computed(() => ({
    color: funFactColor.value
}));

function openLogin() {
  uiStore.openModal('login');
}
function openRegister() {
  uiStore.openModal('register');
}
</script>

<template>
  <div class="h-screen w-screen bg-gray-100 dark:bg-gray-900 flex flex-col items-center justify-center p-6 relative">
    <div class="text-center w-full max-w-2xl">
      <div class="flex justify-center mb-6">
        <img 
          v-if="logoSrc" 
          :src="logoSrc" 
          alt="Custom Logo" 
          class="h-24 sm:h-28 w-auto object-contain border-4 border-gray-200 dark:border-gray-700 rounded-lg shadow-md" 
          @error="($event.target.src=logoDefault)"
        />
        <img 
          v-else 
          :src="logoDefault" 
          alt="lollms Logo" 
          class="h-24 sm:h-28 w-auto border-4 border-gray-200 dark:border-gray-700 rounded-lg shadow-md"
        >
      </div>
      
      <h1 class="text-5xl sm:text-6xl md:text-8xl font-bold text-yellow-600 dark:text-yellow-400 drop-shadow-lg" style="font-family: 'Exo 2', sans-serif;">
        {{ welcomeText }}
      </h1>
      <p class="mt-3 text-xl sm:text-2xl md:text-3xl text-gray-600 dark:text-gray-300">
        {{ welcomeSlogan }}
      </p>

      <div v-if="funFact" :title="funFactCategory ? `Category: ${funFactCategory}` : 'Fun Fact'" class="mt-10 mx-auto max-w-md p-4 border-l-4 rounded-lg text-sm text-left text-gray-900 dark:text-gray-100" :style="funFactStyle">
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
      Powered by <a href="https://github.com/ParisNeo/lollms-webui" target="_blank" class="font-semibold hover:underline">LoLLMs</a> by <a href="https://github.com/ParisNeo" target="_blank" class="font-semibold hover:underline">ParisNeo</a>
    </footer>
  </div>
</template>