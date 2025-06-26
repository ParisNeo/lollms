<script setup>
import Sidebar from '../components/layout/Sidebar.vue';
import ChatView from '../components/chat/ChatView.vue';
</script>

<template>
  <div class="flex h-full w-full">
    <Sidebar />
    <main class="flex-1 flex flex-col overflow-hidden">
      <ChatView />
    </main>
  </div>
</template>
