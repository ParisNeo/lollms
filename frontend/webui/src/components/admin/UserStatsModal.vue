<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { Line } from 'vue-chartjs';
import { Chart as ChartJS, Title, Tooltip, Legend, LineElement, CategoryScale, LinearScale, PointElement, TimeScale } from 'chart.js';
import 'chartjs-adapter-date-fns';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../modals/GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

ChartJS.register(Title, Tooltip, Legend, LineElement, CategoryScale, LinearScale, PointElement, TimeScale);

const props = defineProps({
  userId: {
    type: Number,
    required: true
  },
  username: {
    type: String,
    required: true
  }
});

const adminStore = useAdminStore();
const uiStore = useUiStore();
const stats = ref(null);
const isLoading = ref(true);
const chartRef = ref(null);

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    x: {
      type: 'time',
      time: {
        unit: 'day',
        tooltipFormat: 'MMM d, yyyy',
        displayFormats: {
          day: 'MMM d'
        }
      },
      grid: {
        color: uiStore.currentTheme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'
      },
      ticks: {
        color: uiStore.currentTheme === 'dark' ? '#cbd5e1' : '#4b5563'
      }
    },
    y: {
      beginAtZero: true,
      grid: {
        color: uiStore.currentTheme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'
      },
      ticks: {
        color: uiStore.currentTheme === 'dark' ? '#cbd5e1' : '#4b5563',
        stepSize: 1
      }
    }
  },
  plugins: {
    legend: {
      labels: {
        color: uiStore.currentTheme === 'dark' ? '#cbd5e1' : '#4b5563'
      }
    }
  }
}));

const chartData = computed(() => {
    if (!stats.value) {
        return {
            labels: [],
            datasets: []
        };
    }
    
    const dateMap = new Map();
    for (let i = 29; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        dateMap.set(d.toISOString().split('T')[0], { tasks: 0, messages: 0 });
    }

    stats.value.tasks_per_day.forEach(stat => {
        if (dateMap.has(stat.date)) {
            dateMap.get(stat.date).tasks = stat.count;
        }
    });
    stats.value.messages_per_day.forEach(stat => {
        if (dateMap.has(stat.date)) {
            dateMap.get(stat.date).messages = stat.count;
        }
    });

    const labels = Array.from(dateMap.keys());
    const taskData = Array.from(dateMap.values()).map(v => v.tasks);
    const messageData = Array.from(dateMap.values()).map(v => v.messages);

    return {
        labels,
        datasets: [
            {
                label: 'Tasks Created',
                backgroundColor: '#3b82f6',
                borderColor: '#3b82f6',
                data: taskData,
                tension: 0.1
            },
            {
                label: 'AI Generations',
                backgroundColor: '#10b981',
                borderColor: '#10b981',
                data: messageData,
                tension: 0.1
            }
        ]
    };
});

async function fetchStats() {
    isLoading.value = true;
    try {
        stats.value = await adminStore.fetchUserStats(props.userId);
    } finally {
        isLoading.value = false;
    }
}

function exportChart() {
    if (chartRef.value && chartRef.value.chart) {
        const link = document.createElement('a');
        link.href = chartRef.value.chart.toBase64Image('image/png', 1);
        link.download = `user_stats_${props.username}.png`;
        link.click();
    } else {
        uiStore.addNotification('Could not export chart.', 'error');
    }
}

watch(() => props.userId, (newId) => {
  if (newId) {
    fetchStats();
  }
}, { immediate: true });
</script>

<template>
  <GenericModal modalName="userStats" :title="`Usage Statistics for ${username}`" maxWidthClass="max-w-4xl">
    <template #body>
      <div v-if="isLoading" class="flex justify-center items-center h-96">
        <IconAnimateSpin class="w-8 h-8 text-blue-500" />
      </div>
      <div v-else-if="!stats" class="text-center h-96 flex items-center justify-center">
        <p class="text-gray-500">Could not load statistics for this user.</p>
      </div>
      <div v-else>
        <p class="text-sm text-gray-500 mb-4">Showing activity for the last 30 days.</p>
        <div class="h-96">
            <Line :data="chartData" :options="chartOptions" ref="chartRef"/>
        </div>
      </div>
    </template>
    <template #footer>
      <button @click="fetchStats" class="btn btn-secondary" :disabled="isLoading">
        {{ isLoading ? 'Reloading...' : 'Reload Data' }}
      </button>
      <button @click="exportChart" class="btn btn-secondary">Export Image</button>
      <div class="flex-grow"></div>
      <button @click="uiStore.closeModal('userStats')" class="btn btn-primary">Close</button>
    </template>
  </GenericModal>
</template>