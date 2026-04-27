<script setup>
import { markRaw } from 'vue';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import PersonalitiesSettings from '../components/settings/PersonalitiesSettings.vue';
import IconUserCircle from '../assets/icons/IconUserCircle.vue';

const titleIcon = markRaw(IconUserCircle);
</script>

<template>
    <PageViewLayout title="Personality Studio" :title-icon="titleIcon">
        <template #main>
            <div class="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
                <PersonalitiesSettings />
            </div>
        </template>
    </PageViewLayout>
</template>