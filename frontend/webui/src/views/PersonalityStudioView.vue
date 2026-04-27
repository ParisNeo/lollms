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
                <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
                    <PersonalitiesSettings />
                </div>
            </div>
        </template>
    </PageViewLayout>
</template>