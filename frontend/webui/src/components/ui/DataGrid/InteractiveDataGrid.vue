<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useUiStore } from '../../../stores/ui';
import apiClient from '../../../services/api';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';

const props = defineProps({
  discussionId: { type: String, required: true },
  title: { type: String, required: true },
  version: { type: Number, default: null }
});

const uiStore = useUiStore();
const isLoading = ref(true);
const isQuerying = ref(false);
const activeMode = ref(null); // null | 'sql' | 'ai'

const sqlQuery = ref('');
const aiQuestion = ref('');
const querySql = ref('');
const queryExplanation = ref('');

const searchTerm = ref('');
const gridData = ref(null);
const activeSheet = ref('');

const sheetsList = computed(() => {
  if (!gridData.value) return [];
  if (gridData.value.type === 'csv') return ['Data'];
  return Object.keys(gridData.value.sheets || {});
});

const currentSheetData = computed(() => {
  if (!gridData.value) return null;
  if (gridData.value.type === 'csv') return gridData.value;

  const sheets = gridData.value.sheets || {};
  const sheetNames = Object.keys(sheets);
  if (sheetNames.length === 0) return null;

  // Self-healing fallback: default to first sheet if activeSheet is empty or missing
  const targetSheet = activeSheet.value && sheets[activeSheet.value] 
    ? activeSheet.value 
    : sheetNames[0];

  return sheets[targetSheet] || null;
});

const filteredRows = computed(() => {
  const data = currentSheetData.value;
  if (!data || !data.rows) return [];
  if (!searchTerm.value.trim()) return data.rows;

  const query = searchTerm.value.toLowerCase().trim();
  return data.rows.filter(row => {
    return Object.values(row).some(val => String(val).toLowerCase().includes(query));
  });
});

function toggleMode(mode) {
  if (activeMode.value === mode) activeMode.value = null;
  else activeMode.value = mode;
  querySql.value = '';
  queryExplanation.value = '';
}

async function fetchGridData() {
  isLoading.value = true;
  gridData.value = null;
  querySql.value = '';
  queryExplanation.value = '';
  try {
    const response = await apiClient.get(
      `/api/discussions/${props.discussionId}/artefacts/${encodeURIComponent(props.title)}/grid-data`,
      { params: { version: props.version } }
    );
    gridData.value = response.data;

    // Safety check for tab selection
    const sheets = response.data?.sheets || {};
    const sheetNames = Object.keys(sheets);
    if (response.data?.type === 'csv') {
      activeSheet.value = 'Data';
    } else if (sheetNames.length > 0) {
      activeSheet.value = sheetNames[0];
    }
  } catch (error) {
    console.error(error);
    uiStore.addNotification("Failed to load spreadsheet data grid.", "error");
  } finally {
    isLoading.value = false;
  }
}

async function runSqlQuery() {
  if (!sqlQuery.value.trim() || isQuerying.value) return;
  isQuerying.value = true;
  try {
    const response = await apiClient.post(
      `/api/discussions/${props.discussionId}/artefacts/${encodeURIComponent(props.title)}/raw-query`,
      { sql_query: sqlQuery.value.trim() }
    );
    if (response.data.success) {
      gridData.value = {
        type: 'csv',
        columns: response.data.columns,
        rows: response.data.rows
      };
      querySql.value = sqlQuery.value.trim();
      uiStore.addNotification("SQL query executed successfully.", "success");
    } else {
      uiStore.addNotification(response.data.error || "Query execution failed.", "error");
    }
  } catch (error) {
    uiStore.addNotification("Failed to execute SQL query.", "error");
  } finally {
    isQuerying.value = false;
  }
}

async function runAiQuery() {
  if (!aiQuestion.value.trim() || isQuerying.value) return;
  isQuerying.value = true;
  try {
    const response = await apiClient.post(
      `/api/discussions/${props.discussionId}/artefacts/${encodeURIComponent(props.title)}/ai-query`,
      { question: aiQuestion.value.trim() }
    );
    if (response.data.success) {
      gridData.value = {
        type: 'csv',
        columns: response.data.columns,
        rows: response.data.rows
      };
      querySql.value = response.data.sql_query;
      queryExplanation.value = response.data.explanation;
      uiStore.addNotification("AI query evaluated successfully.", "success");
    } else {
      uiStore.addNotification(response.data.error || "AI query failed.", "error");
    }
  } catch (error) {
    uiStore.addNotification("Failed to run AI query.", "error");
  } finally {
    isQuerying.value = false;
  }
}

watch(() => [props.title, props.version], fetchGridData);
onMounted(fetchGridData);
</script>

<template>
  <div class="flex flex-col h-full overflow-hidden bg-white dark:bg-gray-900 rounded-lg">
    <!-- Controls Area -->
    <div class="p-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/50 space-y-3 shrink-0">
      <div class="flex flex-col sm:flex-row items-center gap-3">
        <!-- Search Field -->
        <div class="relative grow w-full">
          <input
            v-model="searchTerm"
            type="text"
            placeholder="🔍 Live filter visible rows..."
            class="input-field w-full pl-9 text-xs"
          />
        </div>
        <div class="flex gap-2 shrink-0">
          <button
            @click="toggleMode('sql')"
            class="px-3 py-1.5 text-xs font-bold rounded-lg border dark:border-gray-700 transition-colors"
            :class="activeMode === 'sql' ? 'bg-blue-600 text-white' : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300'"
          >
            Raw SQL Sandbox
          </button>
          <button
            @click="toggleMode('ai')"
            class="px-3 py-1.5 text-xs font-bold rounded-lg border dark:border-gray-700 transition-colors"
            :class="activeMode === 'ai' ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300'"
          >
            Ask AI Assistant
          </button>
        </div>
      </div>

      <!-- SQL Console -->
      <div v-if="activeMode === 'sql'" class="pt-2 border-t border-gray-200 dark:border-gray-700 space-y-2">
        <label class="block text-[10px] font-black uppercase text-gray-400">SQLite Query</label>
        <div class="flex gap-2">
          <input
            v-model="sqlQuery"
            type="text"
            placeholder="SELECT * FROM table_name LIMIT 10"
            class="input-field font-mono text-xs grow"
            @keyup.enter="runSqlQuery"
          />
          <button @click="runSqlQuery" class="btn btn-primary btn-sm h-10 px-4" :disabled="isQuerying">
            <span v-if="isQuerying" class="animate-spin">⌛</span>
            <span v-else>Execute</span>
          </button>
        </div>
      </div>

      <!-- AI Assistant -->
      <div v-if="activeMode === 'ai'" class="pt-2 border-t border-gray-200 dark:border-gray-700 space-y-2">
        <label class="block text-[10px] font-black uppercase text-gray-400">Ask Natural Language Question</label>
        <div class="flex gap-2">
          <input
            v-model="aiQuestion"
            type="text"
            placeholder="e.g., What was the average value in column X?"
            class="input-field text-xs grow"
            @keyup.enter="runAiQuery"
          />
          <button @click="runAiQuery" class="btn btn-primary btn-sm h-10 px-4" :disabled="isQuerying">
            <span v-if="isQuerying" class="animate-spin">⌛</span>
            <span v-else>Ask AI</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Multi-Sheet Tab bar (rendered if sheets exist, showing active selection style correctly) -->
    <div v-if="sheetsList.length > 0" class="sheet-tabs-container shrink-0 px-4 py-2 border-b border-gray-200 dark:border-gray-700 flex gap-1.5 overflow-x-auto bg-gray-50/50 dark:bg-gray-800/30">
      <button
        v-for="sheetName in sheetsList"
        :key="sheetName"
        @click="activeSheet = sheetName"
        class="px-3 py-1 text-xs font-semibold rounded-md transition-all border dark:border-gray-700 cursor-pointer"
        :class="(activeSheet === sheetName || (sheetsList.length === 1 && sheetName === 'Data')) ? 'bg-blue-600 text-white border-blue-600 shadow-sm' : 'bg-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
      >
        {{ sheetName }}
      </button>
    </div>

    <!-- Main Grid Target -->
    <div class="grow overflow-auto p-4 custom-scrollbar relative min-h-[300px]">
      <div v-if="isLoading" class="absolute inset-0 flex flex-col items-center justify-center bg-white/60 dark:bg-gray-900/60 backdrop-blur-sm">
        <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin mb-2" />
        <span class="text-xs text-gray-500">Loading Grid Data...</span>
      </div>

      <div v-else-if="currentSheetData" class="space-y-4">
        <!-- Rendered Code/Explanation Header for Queries -->
        <div v-if="queryExplanation || querySql" class="bg-gray-50 dark:bg-gray-850 border border-gray-200 dark:border-gray-700 p-4 rounded-xl space-y-2">
          <div v-if="querySql">
            <span class="text-[9px] font-black uppercase text-blue-500">Executed SQL</span>
            <pre class="text-xs font-mono text-amber-600 dark:text-amber-400 bg-black/5 dark:bg-black/30 p-2.5 rounded-lg mt-1 whitespace-pre-wrap">{{ querySql }}</pre>
          </div>
          <div v-if="queryExplanation">
            <span class="text-[9px] font-black uppercase text-blue-500">Insight</span>
            <p class="text-xs text-gray-600 dark:text-gray-300 mt-1 leading-relaxed">{{ queryExplanation }}</p>
          </div>
        </div>

        <!-- Spreadsheet Table Grid -->
        <div class="overflow-x-auto border dark:border-gray-700 rounded-xl shadow-sm">
          <table class="w-full text-left text-xs border-collapse">
            <thead>
              <tr class="bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-b dark:border-gray-700">
                <th v-for="col in currentSheetData.columns" :key="col" class="px-4 py-3 font-bold uppercase tracking-wider whitespace-nowrap">
                  {{ col }}
                </th>
              </tr>
            </thead>
            <tbody class="divide-y dark:divide-gray-800">
              <tr v-for="(row, idx) in filteredRows" :key="idx" class="hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
                <td v-for="col in currentSheetData.columns" :key="col" class="px-4 py-3 whitespace-nowrap">
                  {{ row[col] !== null ? row[col] : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; height: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>
