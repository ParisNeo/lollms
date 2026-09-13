<template>
  <Teleport to="body">
    <div 
      v-if="isOpen" 
      @click.self="handleClose" 
      @keydown.esc="handleClose"
      class="fixed inset-0 z-[110] flex items-center justify-center p-3 sm:p-6 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150"
    >
      <div class="bg-white dark:bg-gray-900 w-full max-w-6xl rounded-2xl shadow-2xl overflow-hidden border border-gray-200 dark:border-gray-700 flex flex-col max-h-[92vh] animate-in zoom-in-95 duration-150">
        
        <!-- Header Bar -->
        <div class="px-5 py-3.5 border-b border-gray-200 dark:border-gray-800 bg-gray-50/80 dark:bg-gray-850/80 flex items-center justify-between gap-4 flex-wrap select-none shrink-0">
          <div class="flex items-center gap-3 min-w-0">
            <div class="p-2 rounded-xl bg-purple-100 dark:bg-purple-950/60 text-purple-600 dark:text-purple-300 shrink-0">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path></svg>
            </div>
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <h3 class="font-bold text-sm text-gray-900 dark:text-white truncate">
                  {{ title || 'Code Comparison' }}
                </h3>
                <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 font-bold uppercase">
                  {{ language || 'text' }}
                </span>
              </div>
              <p class="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
                {{ isSelection ? 'Comparing selection with LoLLMs proposal' : 'Comparing full document with LoLLMs proposal' }}
              </p>
            </div>
          </div>

          <!-- Stats & View Mode Switcher -->
          <div class="flex items-center gap-3 shrink-0">
            <!-- Additions / Deletions Stats -->
            <div class="flex items-center gap-2 text-xs font-mono font-bold">
              <span class="text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded-md border border-emerald-200 dark:border-emerald-800/60">
                +{{ diffStats.added }}
              </span>
              <span class="text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40 px-2 py-0.5 rounded-md border border-rose-200 dark:border-rose-800/60">
                -{{ diffStats.removed }}
              </span>
            </div>

            <!-- View Mode Switcher (Split vs Unified) -->
            <div class="flex items-center rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 p-0.5 text-xs font-semibold">
              <button 
                type="button" 
                @click="diffMode = 'split'" 
                class="px-2.5 py-1 rounded-md transition-all flex items-center gap-1 cursor-pointer"
                :class="diffMode === 'split' ? 'bg-white dark:bg-gray-700 text-purple-600 dark:text-purple-300 shadow-xs font-bold' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-200'"
              >
                <span>Split View</span>
              </button>
              <button 
                type="button" 
                @click="diffMode = 'unified'" 
                class="px-2.5 py-1 rounded-md transition-all flex items-center gap-1 cursor-pointer"
                :class="diffMode === 'unified' ? 'bg-white dark:bg-gray-700 text-purple-600 dark:text-purple-300 shadow-xs font-bold' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-200'"
              >
                <span>Unified</span>
              </button>
            </div>

            <button @click="handleClose" class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-lg" title="Close (Esc)">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
            </button>
          </div>
        </div>

        <!-- Diff Body Viewer -->
        <div class="grow overflow-auto custom-scrollbar bg-gray-950 text-gray-200 font-mono text-xs leading-relaxed select-text">
          <!-- 1. SPLIT VIEW (Side-by-Side Synchronized Table) -->
          <table v-if="diffMode === 'split'" class="w-full border-collapse table-fixed">
            <colgroup>
              <col class="w-10 sm:w-12 border-r border-gray-800" />
              <col class="w-[calc(50%-2.5rem)] sm:w-[calc(50%-3rem)] border-r border-gray-800" />
              <col class="w-10 sm:w-12 border-r border-gray-800" />
              <col class="w-[calc(50%-2.5rem)] sm:w-[calc(50%-3rem)]" />
            </colgroup>
            <thead class="sticky top-0 bg-gray-900 text-gray-400 border-b border-gray-800 select-none z-10">
              <tr>
                <th class="py-1.5 px-2 text-center text-[10px] uppercase font-bold tracking-wider" colspan="2">
                  Original (Current)
                </th>
                <th class="py-1.5 px-2 text-center text-[10px] uppercase font-bold tracking-wider text-purple-300" colspan="2">
                  Proposed by LoLLMs
                </th>
              </tr>
            </thead>
            <tbody>
              <tr 
                v-for="(row, idx) in splitRows" 
                :key="idx" 
                class="hover:bg-gray-800/40 transition-colors"
              >
                <!-- Left Line Number -->
                <td class="py-0.5 px-1.5 text-right text-[10px] select-none text-gray-500 bg-gray-900/40"
                    :class="{ 'bg-rose-950/60 text-rose-300': row.left.type === 'removed' }">
                  {{ row.left.num || '' }}
                </td>
                <!-- Left Code -->
                <td class="py-0.5 px-2 overflow-hidden whitespace-pre font-mono"
                    :class="{
                      'bg-rose-950/40 text-rose-200': row.left.type === 'removed',
                      'bg-gray-900/20 text-gray-600': row.left.type === 'empty'
                    }">
                  <span v-if="row.left.type === 'removed'" class="text-rose-400 font-bold select-none mr-1">-</span>
                  <span>{{ row.left.text }}</span>
                </td>
                <!-- Right Line Number -->
                <td class="py-0.5 px-1.5 text-right text-[10px] select-none text-gray-500 bg-gray-900/40"
                    :class="{ 'bg-emerald-950/60 text-emerald-300': row.right.type === 'added' }">
                  {{ row.right.num || '' }}
                </td>
                <!-- Right Code -->
                <td class="py-0.5 px-2 overflow-hidden whitespace-pre font-mono"
                    :class="{
                      'bg-emerald-950/40 text-emerald-200': row.right.type === 'added',
                      'bg-gray-900/20 text-gray-600': row.right.type === 'empty'
                    }">
                  <span v-if="row.right.type === 'added'" class="text-emerald-400 font-bold select-none mr-1">+</span>
                  <span>{{ row.right.text }}</span>
                </td>
              </tr>
            </tbody>
          </table>

          <!-- 2. UNIFIED VIEW (Stacked Inline Diff) -->
          <div v-else class="py-2">
            <div 
              v-for="(item, idx) in unifiedRows" 
              :key="idx"
              class="flex items-start px-2 py-0.5 hover:bg-gray-800/40 transition-colors"
              :class="{
                'bg-rose-950/40 text-rose-200': item.type === 'removed',
                'bg-emerald-950/40 text-emerald-200': item.type === 'added',
                'text-gray-300': item.type === 'unchanged'
              }"
            >
              <span class="w-12 text-right text-[10px] text-gray-500 select-none shrink-0 pr-2 font-mono">
                {{ item.oldNum || '' }}
              </span>
              <span class="w-12 text-right text-[10px] text-gray-500 select-none shrink-0 pr-3 font-mono">
                {{ item.newNum || '' }}
              </span>
              <span class="w-4 select-none shrink-0 font-bold font-mono"
                    :class="{
                      'text-rose-400': item.type === 'removed',
                      'text-emerald-400': item.type === 'added',
                      'text-gray-600': item.type === 'unchanged'
                    }">
                {{ item.type === 'removed' ? '-' : (item.type === 'added' ? '+' : ' ') }}
              </span>
              <span class="whitespace-pre overflow-x-auto font-mono grow">
                {{ item.text }}
              </span>
            </div>
          </div>
        </div>

        <!-- Action Footer -->
        <div class="px-5 py-3.5 border-t border-gray-200 dark:border-gray-800 bg-gray-50/80 dark:bg-gray-850/80 flex items-center justify-between gap-3 flex-wrap select-none shrink-0">
          <button 
            type="button" 
            @click="copyModifiedCode" 
            class="btn btn-secondary btn-sm flex items-center gap-1.5"
            title="Copy modified code to clipboard"
          >
            <svg v-if="!justCopied" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
            <svg v-else class="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path></svg>
            <span>{{ justCopied ? 'Copied Code!' : 'Copy Proposal' }}</span>
          </button>

          <div class="flex items-center gap-2">
            <button 
              type="button" 
              @click="handleClose" 
              class="btn btn-secondary btn-sm"
            >
              Reject / Dismiss
            </button>
            <button 
              type="button" 
              @click="$emit('insert-below')" 
              class="btn btn-secondary btn-sm"
              title="Insert the modified code below without replacing"
            >
              Insert Below
            </button>
            <button 
              type="button" 
              @click="$emit('accept')" 
              class="btn btn-primary btn-sm flex items-center gap-1.5 shadow-md bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 border-none text-white font-bold"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"></path></svg>
              <span>Accept & Apply Changes</span>
            </button>
          </div>
        </div>

      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed } from 'vue';
import { useUiStore } from '../../../stores/ui';

const props = defineProps({
  isOpen: { type: Boolean, default: false },
  originalText: { type: String, default: '' },
  modifiedText: { type: String, default: '' },
  title: { type: String, default: 'Code Changes' },
  language: { type: String, default: 'markdown' },
  isSelection: { type: Boolean, default: false }
});

const emit = defineEmits(['accept', 'insert-below', 'close']);

const uiStore = useUiStore();
const diffMode = ref('split');
const justCopied = ref(false);

function handleClose() {
  emit('close');
}

async function copyModifiedCode() {
  if (!props.modifiedText) return;
  const ok = await uiStore.copyToClipboard(props.modifiedText);
  if (ok) {
    justCopied.value = true;
    setTimeout(() => justCopied.value = false, 2000);
  }
}

// Prefix/suffix trimmed LCS line diff engine
function computeLineDiff(oldStr, newStr) {
  const origLines = (oldStr || '').split('\n');
  const newLines = (newStr || '').split('\n');
  const m = origLines.length;
  const n = newLines.length;

  let start = 0;
  while (start < m && start < n && origLines[start] === newLines[start]) {
    start++;
  }

  let endOld = m - 1;
  let endNew = n - 1;
  while (endOld >= start && endNew >= start && origLines[endOld] === newLines[endNew]) {
    endOld--;
    endNew--;
  }

  const rawDiff = [];

  for (let i = 0; i < start; i++) {
    rawDiff.push({ type: 'unchanged', oldLine: origLines[i], newLine: newLines[i], oldNum: i + 1, newNum: i + 1 });
  }

  const sliceOldLen = endOld - start + 1;
  const sliceNewLen = endNew - start + 1;

  if (sliceOldLen > 0 && sliceNewLen > 0) {
    const dp = Array.from({ length: sliceOldLen + 1 }, () => new Int32Array(sliceNewLen + 1));
    for (let i = 1; i <= sliceOldLen; i++) {
      for (let j = 1; j <= sliceNewLen; j++) {
        if (origLines[start + i - 1] === newLines[start + j - 1]) {
          dp[i][j] = dp[i - 1][j - 1] + 1;
        } else {
          dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
        }
      }
    }

    let i = sliceOldLen, j = sliceNewLen;
    const sliceDiff = [];
    while (i > 0 || j > 0) {
      const oldIdx = start + i - 1;
      const newIdx = start + j - 1;
      if (i > 0 && j > 0 && origLines[oldIdx] === newLines[newIdx]) {
        sliceDiff.push({ type: 'unchanged', oldLine: origLines[oldIdx], newLine: newLines[newIdx], oldNum: oldIdx + 1, newNum: newIdx + 1 });
        i--;
        j--;
      } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
        sliceDiff.push({ type: 'added', oldLine: null, newLine: newLines[newIdx], oldNum: null, newNum: newIdx + 1 });
        j--;
      } else if (i > 0 && (j === 0 || dp[i][j - 1] < dp[i - 1][j])) {
        sliceDiff.push({ type: 'removed', oldLine: origLines[oldIdx], newLine: null, oldNum: oldIdx + 1, newNum: null });
        i--;
      }
    }
    sliceDiff.reverse();
    rawDiff.push(...sliceDiff);
  } else if (sliceOldLen > 0) {
    for (let i = start; i <= endOld; i++) {
      rawDiff.push({ type: 'removed', oldLine: origLines[i], newLine: null, oldNum: i + 1, newNum: null });
    }
  } else if (sliceNewLen > 0) {
    for (let j = start; j <= endNew; j++) {
      rawDiff.push({ type: 'added', oldLine: null, newLine: newLines[j], oldNum: null, newNum: j + 1 });
    }
  }

  const trailingCount = m - 1 - endOld;
  for (let k = 0; k < trailingCount; k++) {
    const oNum = endOld + 1 + k;
    const nNum = endNew + 1 + k;
    rawDiff.push({ type: 'unchanged', oldLine: origLines[oNum], newLine: newLines[nNum], oldNum: oNum + 1, newNum: nNum + 1 });
  }

  return rawDiff;
}

const rawDiffResult = computed(() => {
  return computeLineDiff(props.originalText, props.modifiedText);
});

const diffStats = computed(() => {
  let added = 0;
  let removed = 0;
  for (const item of rawDiffResult.value) {
    if (item.type === 'added') added++;
    else if (item.type === 'removed') removed++;
  }
  return { added, removed };
});

const splitRows = computed(() => {
  const diff = rawDiffResult.value;
  const rows = [];
  let k = 0;

  while (k < diff.length) {
    const item = diff[k];
    if (item.type === 'unchanged') {
      rows.push({
        type: 'unchanged',
        left: { text: item.oldLine, num: item.oldNum, type: 'unchanged' },
        right: { text: item.newLine, num: item.newNum, type: 'unchanged' }
      });
      k++;
    } else {
      const removedChunk = [];
      const addedChunk = [];
      while (k < diff.length && diff[k].type !== 'unchanged') {
        if (diff[k].type === 'removed') removedChunk.push(diff[k]);
        else if (diff[k].type === 'added') addedChunk.push(diff[k]);
        k++;
      }
      const maxLen = Math.max(removedChunk.length, addedChunk.length);
      for (let idx = 0; idx < maxLen; idx++) {
        const rem = removedChunk[idx];
        const add = addedChunk[idx];
        rows.push({
          type: 'modified',
          left: rem 
            ? { text: rem.oldLine, num: rem.oldNum, type: 'removed' } 
            : { text: '', num: null, type: 'empty' },
          right: add 
            ? { text: add.newLine, num: add.newNum, type: 'added' } 
            : { text: '', num: null, type: 'empty' }
        });
      }
    }
  }

  return rows;
});

const unifiedRows = computed(() => {
  const diff = rawDiffResult.value;
  const rows = [];
  for (const item of diff) {
    if (item.type === 'unchanged') {
      rows.push({ type: 'unchanged', text: item.oldLine, oldNum: item.oldNum, newNum: item.newNum });
    } else if (item.type === 'removed') {
      rows.push({ type: 'removed', text: item.oldLine, oldNum: item.oldNum, newNum: null });
    } else if (item.type === 'added') {
      rows.push({ type: 'added', text: item.newLine, oldNum: null, newNum: item.newNum });
    }
  }
  return rows;
});
</script>

<style scoped>
@reference "tailwindcss";

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  @apply bg-gray-400 dark:bg-gray-700 rounded-full;
}
</style>