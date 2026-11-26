<script setup>
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import ServiceAccountsPanel from '../components/admin/ServiceAccountsPanel.vue';
import IconUserGroup from '../assets/icons/IconUserGroup.vue';
</script>

<template>
  <PageViewLayout title="Service Accounts" :title-icon="IconUserGroup" :show-sidebar="true">
    <template #main>
      <div class="p-4 sm:p-6 max-w-5xl mx-auto w-full">
        <ServiceAccountsPanel />
      </div>
    </template>
  </PageViewLayout>
</template>