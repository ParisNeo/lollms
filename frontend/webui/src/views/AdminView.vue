<script setup>
import { defineAsyncComponent } from 'vue';

const AdminPanel = defineAsyncComponent(() => import('../components/admin/AdminPanel.vue'));
</script>

<template>
  <div class="flex flex-col h-screen bg-gray-100 dark:bg-gray-900 overflow-hidden">
    <header class="bg-white dark:bg-gray-800 border-b dark:border-gray-700 p-4 flex items-center justify-between shadow-sm flex-shrink-0">
      <div class="flex items-center space-x-3">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-gray-500 dark:text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M15 21v-1.5a6.375 6.375 0 00-3.262-5.171M9 10a3 3 0 11-6 0 3 3 0 016 0zm3 2a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        <h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">Admin Panel</h1>
      </div>
      <router-link
        to="/"
        class="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M11 15l-3-3m0 0l3-3m-3 3h8a5 5 0 000-10H6" />
        </svg>
        <span>Back to App</span>
      </router-link>
    </header>

    <main class="flex-grow overflow-y-auto p-6">
      <Suspense>
        <template #default>
          <AdminPanel />
        </template>
        <template #fallback>
          <div class="flex items-center justify-center h-full">
            <p class="text-lg text-gray-500 dark:text-gray-400 italic">Loading admin panel...</p>
          </div>
        </template>
      </Suspense>
    </main>
  </div>
</template>