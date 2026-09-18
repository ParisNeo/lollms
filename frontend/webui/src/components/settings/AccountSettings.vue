<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import { useTasksStore } from '../../stores/tasks';
import apiClient from '../../services/api';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

// Chart components for personal stats
import { Line, Doughnut } from 'vue-chartjs';
import {
  Chart as ChartJS, Title, Tooltip, Legend, LineElement, BarElement, ArcElement, CategoryScale, LinearScale, PointElement, TimeScale, Filler
} from 'chart.js';
import 'chartjs-adapter-date-fns';

ChartJS.register(Title, Tooltip, Legend, LineElement, BarElement, ArcElement, CategoryScale, LinearScale, PointElement, TimeScale, Filler);

const authStore = useAuthStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();

const user = computed(() => authStore.user);

const profileForm = ref({
    first_name: '',
    family_name: '',
    email: '',
    birth_date: '',
    receive_notification_emails: true,
    is_searchable: true,
});
const isProfileLoading = ref(false);
const isProfileDirty = ref(false);
let pristineProfileState = '{}';

const passwordForm = ref({
    current_password: '',
    new_password: ''
});
const confirmNewPassword = ref('');
const isPasswordLoading = ref(false);
const showCurrentPassword = ref(false);
const showNewPassword = ref(false);

const isUploadingIcon = ref(false);
const fileInput = ref(null);

// Personal Telemetry & Usage State
const personalStats = ref(null);
const isLoadingPersonalStats = ref(false);
const statsRangeDays = ref(30);

async function fetchPersonalStats() {
    isLoadingPersonalStats.value = true;
    try {
        const res = await apiClient.get('/api/users/me/stats', {
            params: { days: statsRangeDays.value }
        });
        personalStats.value = res.data;
    } catch (e) {
        console.error("Failed to load personal stats:", e);
    } finally {
        isLoadingPersonalStats.value = false;
    }
}

// Interactive curve toggles for personal chart
const personalCurves = ref({
    total: true,
    webui: true,
    api: true
});

const personalChartData = computed(() => {
    if (!personalStats.value) return { labels: [], datasets: [] };
    const datasets = [];

    const allDates = [
        ...(personalStats.value.tokens_per_day || []).map(t => t.date),
        ...(personalStats.value.messages_per_day || []).map(t => t.date)
    ];
    const uniqueDates = Array.from(new Set(allDates)).sort();

    if (personalCurves.value.total) {
        const tokens = personalStats.value.tokens_per_day || [];
        datasets.push({
            label: 'Total Tokens',
            data: tokens.map(t => ({ x: t.date, y: t.count })),
            borderColor: '#10B981',
            backgroundColor: 'rgba(16, 185, 129, 0.12)',
            fill: true,
            tension: 0.2,
            pointRadius: 3
        });
    }

    if (personalCurves.value.webui) {
        const webuiToks = personalStats.value.webui_tokens_per_day || [];
        datasets.push({
            label: 'WebUI Tokens',
            data: webuiToks.map(t => ({ x: t.date, y: t.count })),
            borderColor: '#3B82F6',
            fill: false,
            tension: 0.2,
            pointRadius: 3
        });
    }

    if (personalCurves.value.api) {
        const apiToks = personalStats.value.api_tokens_per_day || [];
        datasets.push({
            label: 'API Tokens',
            data: apiToks.map(t => ({ x: t.date, y: t.count })),
            borderColor: '#8B5CF6',
            fill: false,
            tension: 0.2,
            pointRadius: 3
        });
    }

    return {
        labels: uniqueDates,
        datasets
    };
});

const personalChartOptions = computed(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { display: false },
        tooltip: { mode: 'index', intersect: false }
    },
    scales: {
        x: {
            type: 'time',
            time: { unit: 'day', tooltipFormat: 'MMM d, yyyy' },
            grid: { color: uiStore.currentTheme === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)' },
            ticks: { color: uiStore.currentTheme === 'dark' ? '#cbd5e1' : '#4b5563' }
        },
        y: {
            beginAtZero: true,
            grid: { color: uiStore.currentTheme === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)' },
            ticks: { color: uiStore.currentTheme === 'dark' ? '#cbd5e1' : '#4b5563' }
        }
    }
}));

const personalSourceDoughnutData = computed(() => {
    const sb = personalStats.value?.source_breakdown;
    const webui = sb?.webui_tokens || 0;
    const api = sb?.api_tokens || 0;

    return {
        labels: ['WebUI Chat', 'API Tokens'],
        datasets: [{
            data: [webui, api],
            backgroundColor: ['#3B82F6', '#8B5CF6'],
            borderWidth: 0
        }]
    };
});

const personalSourceDoughnutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '70%',
    plugins: {
        legend: { display: false },
        tooltip: {
            callbacks: {
                label: function(context) {
                    const label = context.label || '';
                    const val = context.raw || 0;
                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                    const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                    return ` ${label}: ${val.toLocaleString()} tokens (${pct}%)`;
                }
            }
        }
    }
};

const isAdmin = computed(() => authStore.isAdmin);
const isTtsConfigured = computed(() => !!user.value?.tts_binding_model_name);
const isSttConfigured = computed(() => !!user.value?.stt_binding_model_name);
const isTtiConfigured = computed(() => !!user.value?.tti_binding_model_name);

function populateProfileForm() {
    if (user.value) {
        profileForm.value.first_name = user.value.first_name || '';
        profileForm.value.family_name = user.value.family_name || '';
        profileForm.value.email = user.value.email || '';
        profileForm.value.birth_date = user.value.birth_date || '';
        profileForm.value.receive_notification_emails = user.value.receive_notification_emails;
        profileForm.value.is_searchable = user.value.is_searchable;
        pristineProfileState = JSON.stringify(profileForm.value);
    }
}

onMounted(() => {
    populateProfileForm();
    fetchPersonalStats();
});

watch(user, populateProfileForm, { deep: true });
watch(profileForm, (newVal) => {
    isProfileDirty.value = JSON.stringify(newVal) !== pristineProfileState;
}, { deep: true });

async function handleSaveProfile() {
    isProfileLoading.value = true;
    try {
        const pristine = JSON.parse(pristineProfileState);
        const dirtyFields = {};
        let hasChanges = false;
        for (const key in profileForm.value) {
            if (profileForm.value[key] !== pristine[key]) {
                dirtyFields[key] = profileForm.value[key];
                hasChanges = true;
            }
        }

        if (hasChanges) {
            const payload = { ...dirtyFields };
            
            if (payload.email === '') {
                payload.email = null;
            }
            if (payload.birth_date === '') {
                payload.birth_date = null;
            }

            await authStore.updateUserProfile(payload);
        } else {
            uiStore.addNotification("No changes to save.", "info");
        }
    } catch (error) {
        // Error is handled by the global interceptor
    } finally {
        isProfileLoading.value = false;
    }
}

async function handleChangePassword() {
    if (passwordForm.value.new_password !== confirmNewPassword.value) {
        uiStore.addNotification("New passwords do not match.", 'error');
        return;
    }
    if (passwordForm.value.new_password.length < 8) {
        uiStore.addNotification("New password must be at least 8 characters long.", 'error');
        return;
    }

    isPasswordLoading.value = true;
    try {
        await authStore.changePassword(passwordForm.value);
        passwordForm.value.current_password = '';
        passwordForm.value.new_password = '';
        confirmNewPassword.value = '';
    } catch (error) {
        // Error is handled by the global interceptor
    } finally {
        isPasswordLoading.value = false;
    }
}

const triggerFileInput = () => {
  fileInput.value?.click();
};

const onIconFileChange = async (event) => {
  const file = event.target.files[0];
  if (!file) return;

  isUploadingIcon.value = true;
  uiStore.addNotification('Uploading icon...', 'info');

  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await apiClient.put('/api/auth/me/icon', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    
    if (authStore.user) {
      authStore.user.icon = response.data.icon_url;
    }
    
    uiStore.addNotification('Icon updated successfully!', 'success');
  } catch (error) {
    uiStore.addNotification('Icon upload failed.', 'error');
  } finally {
    isUploadingIcon.value = false;
    if (fileInput.value) {
      fileInput.value.value = '';
    }
  }
};

async function handleGenerateAvatar() {
    const { confirmed, value } = await uiStore.showConfirmation({
        title: 'Generate New Avatar',
        message: 'Enter an optional prompt to guide the AI. If left blank, a prompt will be generated from your profile information.',
        confirmText: 'Generate',
        inputType: 'textarea',
        inputPlaceholder: 'e.g., a professional photo, pixel art style...'
    });

    if (confirmed) {
        try {
            const task = await authStore.generateAvatar(value || null);
            if (task) {
                uiStore.openModal('tasksManager', { initialTaskId: task.id });
            } else {
                uiStore.addNotification('Failed to start avatar generation task. Check server logs for details.', 'error');
            }
        } catch (error) {
            console.error("Error during handleGenerateAvatar:", error);
            uiStore.addNotification('An unexpected error occurred while trying to generate the avatar.', 'error');
        }
    }
}
</script>

<template>
    <div v-if="user" class="space-y-10">
        <!-- ── PERSONAL USAGE & ENVIRONMENTAL TELEMETRY SECTION ── -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-3xl border border-gray-100 dark:border-gray-700/80 p-6 space-y-6">
            <div class="flex items-center justify-between flex-wrap gap-4 border-b dark:border-gray-700 pb-4">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-2xl bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 flex items-center justify-center font-bold">
                        <IconSparkles class="w-5 h-5" />
                    </div>
                    <div>
                        <h2 class="text-xl font-black text-gray-900 dark:text-white">Your AI Usage & Eco Footprint</h2>
                        <p class="text-xs text-gray-500 dark:text-gray-400">Track your personal token volume, compute energy, and estimated carbon impact.</p>
                    </div>
                </div>

                <div class="flex items-center gap-1 bg-gray-100 dark:bg-gray-900/60 p-1 rounded-xl text-xs font-bold">
                    <button @click="statsRangeDays = 7; fetchPersonalStats();" class="px-3 py-1 rounded-lg transition-all" :class="statsRangeDays === 7 ? 'bg-white dark:bg-gray-700 text-purple-600 shadow-xs' : 'text-gray-500'">7D</button>
                    <button @click="statsRangeDays = 30; fetchPersonalStats();" class="px-3 py-1 rounded-lg transition-all" :class="statsRangeDays === 30 ? 'bg-white dark:bg-gray-700 text-purple-600 shadow-xs' : 'text-gray-500'">30D</button>
                    <button @click="statsRangeDays = 90; fetchPersonalStats();" class="px-3 py-1 rounded-lg transition-all" :class="statsRangeDays === 90 ? 'bg-white dark:bg-gray-700 text-purple-600 shadow-xs' : 'text-gray-500'">90D</button>
                </div>
            </div>

            <!-- Metric Cards Grid -->
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div class="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-2xl border dark:border-gray-700">
                    <span class="text-[10px] font-black uppercase text-gray-400 tracking-wider">Total Sum Tokens</span>
                    <p class="text-xl font-black font-mono text-purple-600 dark:text-purple-400 mt-1">
                        {{ (personalStats?.total_tokens || 0).toLocaleString() }}
                    </p>
                    <p class="text-[10px] text-gray-400 mt-0.5">{{ personalStats?.total_prompt_tokens?.toLocaleString() || 0 }} in / {{ personalStats?.total_completion_tokens?.toLocaleString() || 0 }} out</p>
                </div>

                <div class="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-2xl border dark:border-gray-700">
                    <span class="text-[10px] font-black uppercase text-gray-400 tracking-wider">Energy Used</span>
                    <p class="text-xl font-black font-mono text-emerald-600 dark:text-emerald-400 mt-1">
                        {{ personalStats?.total_energy_kwh ?? 0 }} <span class="text-xs font-normal text-gray-500">kWh</span>
                    </p>
                    <p class="text-[10px] text-gray-400 mt-0.5">GPU Compute draw</p>
                </div>

                <div class="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-2xl border dark:border-gray-700">
                    <span class="text-[10px] font-black uppercase text-gray-400 tracking-wider">Estimated CO2</span>
                    <p class="text-xl font-black font-mono text-teal-600 dark:text-teal-400 mt-1">
                        {{ personalStats?.total_co2_g ?? 0 }} <span class="text-xs font-normal text-gray-500">g</span>
                    </p>
                    <p class="text-[10px] text-gray-400 mt-0.5">~{{ personalStats?.co2_equivalents?.car_km ?? 0 }} km in car</p>
                </div>

                <div class="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-2xl border dark:border-gray-700">
                    <span class="text-[10px] font-black uppercase text-gray-400 tracking-wider">Phone Charges</span>
                    <p class="text-xl font-black font-mono text-blue-600 dark:text-blue-400 mt-1">
                        {{ personalStats?.co2_equivalents?.smartphone_charges ?? 0 }}
                    </p>
                    <p class="text-[10px] text-gray-400 mt-0.5">Charge cycles</p>
                </div>
            </div>

            <!-- WebUI vs. API Source Ratio Breakdown Section -->
            <div class="p-5 bg-gray-50/70 dark:bg-gray-900/40 rounded-2xl border dark:border-gray-700/80">
                <div class="flex items-center justify-between border-b dark:border-gray-700 pb-3 mb-4">
                    <span class="text-xs font-black uppercase tracking-wider text-gray-700 dark:text-gray-300">Consumption Channels & Ratio</span>
                    <span class="text-xs font-mono text-gray-400">WebUI {{ personalStats?.source_breakdown?.webui_ratio || 0 }}% / API {{ personalStats?.source_breakdown?.api_ratio || 0 }}%</span>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 items-center">
                    <div class="h-36 relative flex items-center justify-center">
                        <Doughnut :data="personalSourceDoughnutData" :options="personalSourceDoughnutOptions" />
                        <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center">
                            <span class="text-[8px] font-bold uppercase text-gray-400">Ratio</span>
                            <span class="text-xs font-bold font-mono">{{ personalStats?.source_breakdown?.webui_ratio || 0 }}% / {{ personalStats?.source_breakdown?.api_ratio || 0 }}%</span>
                        </div>
                    </div>

                    <div class="sm:col-span-2 grid grid-cols-2 gap-3">
                        <div class="p-3 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700">
                            <div class="flex items-center gap-1.5 text-xs font-bold text-blue-600">
                                <span class="w-2.5 h-2.5 rounded-full bg-blue-500"></span>
                                WebUI Chat
                            </div>
                            <p class="text-lg font-black font-mono mt-1">{{ (personalStats?.source_breakdown?.webui_tokens || 0).toLocaleString() }} <span class="text-[10px] font-normal text-gray-400">tokens</span></p>
                            <p class="text-[10px] text-gray-400">{{ personalStats?.source_breakdown?.webui_requests || 0 }} messages</p>
                        </div>

                        <div class="p-3 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700">
                            <div class="flex items-center gap-1.5 text-xs font-bold text-purple-600">
                                <span class="w-2.5 h-2.5 rounded-full bg-purple-500"></span>
                                API Calls
                            </div>
                            <p class="text-lg font-black font-mono mt-1">{{ (personalStats?.source_breakdown?.api_tokens || 0).toLocaleString() }} <span class="text-[10px] font-normal text-gray-400">tokens</span></p>
                            <p class="text-[10px] text-gray-400">{{ personalStats?.source_breakdown?.api_requests || 0 }} requests</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Usage Plot with Curve Selector -->
            <div class="space-y-3 pt-2">
                <div class="flex items-center justify-between flex-wrap gap-2 text-xs">
                    <div class="flex items-center gap-3 select-none">
                        <label class="flex items-center gap-1 font-bold text-emerald-600 dark:text-emerald-400 cursor-pointer">
                            <input type="checkbox" v-model="personalCurves.total" class="rounded text-emerald-600 w-3.5 h-3.5">
                            <span>Total</span>
                        </label>
                        <label class="flex items-center gap-1 font-bold text-blue-600 dark:text-blue-400 cursor-pointer">
                            <input type="checkbox" v-model="personalCurves.webui" class="rounded text-blue-600 w-3.5 h-3.5">
                            <span>WebUI</span>
                        </label>
                        <label class="flex items-center gap-1 font-bold text-purple-600 dark:text-purple-400 cursor-pointer">
                            <input type="checkbox" v-model="personalCurves.api" class="rounded text-purple-600 w-3.5 h-3.5">
                            <span>API</span>
                        </label>
                    </div>
                </div>

                <div class="h-64">
                    <div v-if="isLoadingPersonalStats" class="h-full flex items-center justify-center">
                        <IconAnimateSpin class="w-8 h-8 text-purple-500 animate-spin" />
                    </div>
                    <div v-else-if="!personalStats || personalStats.tokens_per_day.length === 0" class="h-full flex flex-col items-center justify-center text-center p-4 border-2 border-dashed rounded-2xl border-gray-200 dark:border-gray-700">
                        <p class="text-xs text-gray-400">No token activity recorded in the selected time range.</p>
                    </div>
                    <Line v-else :data="personalChartData" :options="personalChartOptions" />
                </div>
            </div>
        </div>

        <!-- User Profile Section -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
            <div class="p-4 sm:p-6">
                <h2 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">Profile</h2>
                <p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">Manage your public profile and personal information.</p>
            </div>
            <div class="border-t border-gray-200 dark:border-gray-700 p-4 sm:p-6">
                <form @submit.prevent="handleSaveProfile" class="flex flex-col md:flex-row gap-8">
                    <!-- Avatar Section -->
                    <div class="shrink-0 flex flex-col items-center space-y-2 w-full md:w-40">
                        <UserAvatar :icon="user.icon" :username="user.username" size-class="h-28 w-28" />
                        <input
                            type="file"
                            ref="fileInput"
                            @change="onIconFileChange"
                            accept="image/png, image/jpeg, image/webp"
                            class="hidden"
                        />
                        <button
                            type="button"
                            @click="triggerFileInput"
                            :disabled="isUploadingIcon"
                            class="btn btn-secondary w-full"
                        >
                            {{ isUploadingIcon ? 'Uploading...' : 'Change Icon' }}
                        </button>
                        <button
                            v-if="isTtiConfigured"
                            type="button"
                            @click="handleGenerateAvatar"
                            class="btn btn-secondary-outline w-full"
                        >
                            Generate Avatar
                        </button>
                        <p class="text-xs text-center text-gray-500 dark:text-gray-400">Max 5MB (JPG, PNG, WEBP)</p>
                    </div>

                    <!-- Profile Info Form -->
                    <div class="grow space-y-6">
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
                            <div>
                                <label for="firstName" class="block text-sm font-medium text-gray-700 dark:text-gray-300">First Name</label>
                                <input type="text" id="firstName" v-model="profileForm.first_name" class="input-field mt-1" placeholder="Jane">
                            </div>
                            <div>
                                <label for="familyName" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Family Name</label>
                                <input type="text" id="familyName" v-model="profileForm.family_name" class="input-field mt-1" placeholder="Doe">
                            </div>
                        </div>
                        <div>
                            <label for="email" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Email Address</label>
                            <input type="email" id="email" v-model="profileForm.email" class="input-field mt-1" placeholder="you@example.com">
                        </div>
                        <div>
                            <label for="birthDate" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Birth Date</label>
                            <input type="date" id="birthDate" v-model="profileForm.birth_date" class="input-field mt-1">
                        </div>
                        
                         <div class="space-y-4 pt-4 border-t dark:border-gray-600">
                            <div class="relative flex items-start">
                                <div class="flex h-6 items-center">
                                    <input id="is_searchable" v-model="profileForm.is_searchable" type="checkbox" class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-600">
                                </div>
                                <div class="ml-3 text-sm leading-6">
                                    <label for="is_searchable" class="font-medium text-gray-900 dark:text-gray-100">Profile Searchability</label>
                                    <p class="text-gray-500 dark:text-gray-400">Allow other users to find your profile in searches.</p>
                                </div>
                            </div>
                             <div class="relative flex items-start">
                                <div class="flex h-6 items-center">
                                    <input id="receive_notification_emails" v-model="profileForm.receive_notification_emails" type="checkbox" class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-600">
                                </div>
                                <div class="ml-3 text-sm leading-6">
                                    <label for="receive_notification_emails" class="font-medium text-gray-900 dark:text-gray-100">Notification Emails</label>
                                    <p class="text-gray-500 dark:text-gray-400">Receive emails for important events like password resets.</p>
                                </div>
                            </div>
                        </div>

                        <div class="flex justify-end">
                            <button type="submit" class="btn btn-primary" :disabled="isProfileLoading || !isProfileDirty">
                                {{ isProfileLoading ? 'Saving...' : 'Save Profile' }}
                            </button>
                        </div>
                    </div>
                </form>
            </div>
        </div>

        <!-- Change Password Section -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
             <div class="px-4 py-5 sm:p-6">
                <h2 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">Change Password</h2>
                <p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">Ensure your account is using a long, random password to stay secure.</p>
            </div>
             <div class="border-t border-gray-200 dark:border-gray-700">
                <form @submit.prevent="handleChangePassword" class="p-4 sm:p-6 space-y-6">
                    <div>
                        <label for="currentPassword" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Current Password</label>
                        <div class="mt-1 relative">
                            <input :type="showCurrentPassword ? 'text' : 'password'" id="currentPassword" v-model="passwordForm.current_password" required class="input-field pr-10" autocomplete="current-password">
                            <button type="button" @click="showCurrentPassword = !showCurrentPassword" class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                                <IconEyeOff v-if="showCurrentPassword" class="w-5 h-5" />
                                <IconEye v-else class="w-5 h-5" />
                            </button>
                        </div>
                    </div>
                    <div>
                        <label for="newPassword" class="block text-sm font-medium text-gray-700 dark:text-gray-300">New Password</label>
                         <div class="mt-1 relative">
                            <input :type="showNewPassword ? 'text' : 'password'" id="newPassword" v-model="passwordForm.new_password" required minlength="8" class="input-field pr-10" autocomplete="new-password">
                            <button type="button" @click="showNewPassword = !showNewPassword" class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                                <IconEyeOff v-if="showNewPassword" class="w-5 h-5" />
                                <IconEye v-else class="w-5 h-5" />
                            </button>
                        </div>
                    </div>
                    <div>
                        <label for="confirmPassword" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Confirm New Password</label>
                        <div class="mt-1 relative">
                            <input :type="showNewPassword ? 'text' : 'password'" id="confirmPassword" v-model="confirmNewPassword" required class="input-field pr-10" autocomplete="new-password">
                        </div>
                    </div>
                    <div class="flex justify-end">
                        <button type="submit" class="btn btn-primary" :disabled="isPasswordLoading">
                            {{ isPasswordLoading ? 'Changing...' : 'Change Password' }}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</template>