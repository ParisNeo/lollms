<template>
    <div :class="['markdown-editor-container flex flex-col h-full min-h-0 border border-gray-300 dark:border-gray-600 rounded-md', editorClass]">
        <Toolbar
            v-if="currentMode === 'edit'"
            :toolbarClass="[toolbarClass, 'shrink-0']"
            :buttonClass="buttonClass"
            :language="language"
            :currentMode="currentMode"
            :isWrappingEnabled="isWrappingEnabled"
            :showTokens="showTokens"
            :isTokenizing="isTokenizing"
            :isRunnable="isRunnable"
            :isRunningCode="isRunningCode"
            :isGeneratingAi="isGeneratingAi"
            :showMinimap="showMinimap"
            @format="handleFormat"
            @insert-link="handleInsertLink"
            @insert-image="handleInsertImage"
            @import="handleImport"
            @export="handleExport"
            @set-mode="setMode"
            @toggle-wrapping="toggleWrapping"
            @toggle-tokens="handleToggleTokens"
            @toggle-minimap="toggleMinimap"
            @run-code="handleRunCode"
            @format-doc="handleFormatDocument"
            @ai-action="handleAiAssist"
            @fold-all="handleFoldAll"
            @unfold-all="handleUnfoldAll"
            @open-ai-helper="openSelectionAiModal()"
            @ai-custom-prompt="openCustomPromptModal()"
        />

        <!-- AI Proposal Review Banner -->
        <div v-if="aiProposal" class="px-3 py-2 bg-purple-50 dark:bg-purple-950/50 border-b border-purple-200 dark:border-purple-800 flex items-center justify-between gap-3 text-xs z-20 animate-in fade-in shrink-0">
            <div class="flex items-center gap-2 min-w-0">
                <span class="px-1.5 py-0.5 rounded bg-purple-600 text-white font-black text-[9px] uppercase tracking-wider">LoLLMs Proposal</span>
                <span class="font-bold text-purple-900 dark:text-purple-200 truncate">{{ aiProposal.title }} ({{ aiProposal.isSelection ? 'Selection' : 'Document' }})</span>
            </div>
            <div class="flex items-center gap-2 shrink-0">
                <button @click="openDiffFromProposal" class="btn btn-secondary btn-xs flex items-center gap-1 font-bold text-purple-600 dark:text-purple-300" title="Inspect side-by-side split view diff">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path></svg>
                    <span>Inspect Split Diff</span>
                </button>
                <button @click="applyAiProposal" class="btn btn-primary btn-xs flex items-center gap-1 shadow-sm">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                    <span>Apply</span>
                </button>
                <button @click="insertAiProposalBelow" class="btn btn-secondary btn-xs">
                    <span>Insert Below</span>
                </button>
                <button @click="dismissAiProposal" class="p-1 text-gray-400 hover:text-red-500 rounded" title="Dismiss">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
        </div>

        <div class="editor-content-host flex-1 overflow-hidden relative min-h-[4.5rem] flex flex-row">
            <!-- Floating Selection AI Pill -->
            <div v-if="showFloatingPill" :style="floatingPillStyle" class="floating-ai-pill">
                <button 
                    @click.stop="openSelectionAiModal()" 
                    class="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white text-xs font-bold shadow-lg hover:scale-105 active:scale-95 transition-all cursor-pointer border border-white/20"
                    title="Ask LoLLMs about this selection (Ctrl+K)"
                >
                    <IconSparkles class="w-3.5 h-3.5 text-amber-300" />
                    <span>Ask LoLLMs</span>
                    <kbd class="text-[9px] bg-white/20 px-1 rounded font-mono font-normal">Ctrl+K</kbd>
                </button>
            </div>

            <!-- Main Editor Scroller -->
            <div ref="editorRef" v-show="currentMode === 'edit'" class="w-full h-full flex-1 overflow-hidden"></div>

            <!-- Interactive Minimap Panel -->
            <div 
                v-if="currentMode === 'edit' && showMinimap" 
                class="minimap-panel w-20 sm:w-24 shrink-0 h-full border-l border-gray-200 dark:border-gray-700/80 bg-gray-50/60 dark:bg-gray-900/60 relative overflow-hidden select-none cursor-pointer z-10"
                @mousedown="handleMinimapClick"
                title="Click to jump or drag viewport slider"
            >
                <canvas ref="minimapCanvasRef" class="w-full h-full block pointer-events-none"></canvas>
                <!-- Viewport Indicator Overlay -->
                <div 
                    class="minimap-viewport-slider absolute left-0 right-0 bg-blue-500/15 dark:bg-blue-400/20 border-y-2 border-blue-500/60 dark:border-blue-400/60 transition-colors pointer-events-auto cursor-grab active:cursor-grabbing hover:bg-blue-500/25"
                    :style="{
                        top: `${viewportTop}px`,
                        height: `${viewportHeight}px`
                    }"
                    @mousedown.stop="startViewportDrag"
                ></div>
            </div>

            <!-- Improved rendering container -->
            <div v-if="renderable && currentMode === 'view'" class="absolute inset-0 bg-white dark:bg-gray-800 z-10 overflow-y-auto">
                <div v-if="isRendering" class="flex flex-col items-center justify-center h-full text-gray-500 dark:text-gray-400">
                    <svg class="animate-spin h-8 w-8 mb-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    <span>Formatting Preview...</span>
                </div>
                <div v-else class="p-4 overflow-y-auto h-full">
                    <MessageContentRenderer :content="renderedContent" />
                </div>
            </div>
        </div>

        <!-- Code Execution Console Output Drawer -->
        <div v-if="showConsole" class="border-t border-gray-300 dark:border-gray-700 bg-gray-950 text-gray-200 flex flex-col z-20 shrink-0 max-h-56 min-h-[7rem] animate-in fade-in slide-in-from-bottom-2">
            <div class="px-3 py-1.5 bg-gray-900 border-b border-gray-800 flex items-center justify-between text-xs select-none">
                <div class="flex items-center gap-2 font-mono">
                    <span class="w-2 h-2 rounded-full" :class="isRunningCode ? 'bg-amber-400 animate-ping' : (executionStats?.success ? 'bg-emerald-400' : 'bg-rose-500')"></span>
                    <span class="font-bold text-[11px] uppercase tracking-wider text-gray-300">
                        {{ isPython ? 'Python Terminal (Pyodide)' : 'JavaScript Console Sandbox' }}
                    </span>
                    <span v-if="executionStats" class="text-[10px] text-gray-400 font-mono">
                        ({{ executionStats.time }})
                    </span>
                </div>
                <div class="flex items-center gap-1">
                    <button @click="consoleOutput = []" class="p-1 hover:bg-gray-800 rounded text-gray-400 hover:text-gray-200" title="Clear Console">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                    </button>
                    <button @click="showConsole = false" class="p-1 hover:bg-gray-800 rounded text-gray-400 hover:text-gray-200" title="Close Console">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                    </button>
                </div>
            </div>
            <div class="p-3 overflow-y-auto font-mono text-xs leading-relaxed space-y-1 grow custom-scrollbar">
                <div v-if="isRunningCode" class="text-amber-400 animate-pulse flex items-center gap-2">
                    <span>Executing code...</span>
                </div>
                <div v-else-if="consoleOutput.length === 0" class="text-gray-500 italic">
                    Console ready. No output.
                </div>
                <div v-for="(item, i) in consoleOutput" :key="i" :class="item.type === 'stderr' ? 'text-rose-400' : (item.type === 'result' ? 'text-blue-400 font-bold' : 'text-gray-200')">
                    {{ item.text }}
                </div>
            </div>
        </div>

        <StatusBar 
            :modelValue="modelValue" 
            :language="language"
            :allowedModes="allowedModes"
            :currentMode="currentMode"
            :tokenCount="tokenCount"
            :showTokens="showTokens"
            :isTokenizing="isTokenizing"
            :isRunnable="isRunnable"
            :showMinimap="showMinimap"
            @set-mode="setMode"
            @toggle-tokens="handleToggleTokens"
            @toggle-minimap="toggleMinimap"
            @run-code="handleRunCode"
            class="shrink-0"
        />

        <!-- Teleported Split-View & Unified Diff Modal -->
        <DiffViewerModal 
            :isOpen="isDiffModalOpen"
            :originalText="diffOriginalText"
            :modifiedText="diffModifiedText"
            :title="diffTitle"
            :language="language"
            :isSelection="diffIsSelection"
            @accept="handleAcceptDiff"
            @insert-below="handleInsertBelowDiff"
            @close="isDiffModalOpen = false"
        />

        <!-- Teleported Custom Prompt to Change Modal -->
        <Teleport to="body">
            <div 
                v-if="isCustomPromptModalOpen" 
                @click.self="closeCustomPromptModal" 
                @keydown.esc="closeCustomPromptModal"
                class="fixed inset-0 z-[105] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150"
            >
                <div class="bg-white dark:bg-gray-800 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden border border-gray-200 dark:border-gray-700 flex flex-col animate-in zoom-in-95 duration-150">

                    <!-- Modal Header -->
                    <div class="px-5 py-3.5 border-b dark:border-gray-700 flex items-center justify-between bg-gradient-to-r from-purple-600 to-indigo-600 text-white select-none">
                        <div class="flex items-center gap-2.5">
                            <div class="p-1.5 rounded-lg bg-white/20">
                                <IconSparkles class="w-4 h-4 text-amber-300" />
                            </div>
                            <div>
                                <h3 class="font-bold text-sm leading-tight flex items-center gap-2">
                                    <span>Prompt to Change</span>
                                    <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/20 uppercase tracking-wider font-bold">
                                        {{ language }}
                                    </span>
                                </h3>
                                <p class="text-[11px] opacity-80 mt-0.5">
                                    {{ editorView?.state?.selection?.main && (editorView.state.selection.main.to - editorView.state.selection.main.from) > 1 ? 'Targeting active selection' : 'Targeting entire file' }}
                                </p>
                            </div>
                        </div>
                        <button @click="closeCustomPromptModal" class="p-1 hover:bg-white/20 rounded-lg transition-colors" title="Close (Esc)">
                            <IconXMark class="w-5 h-5" />
                        </button>
                    </div>

                    <!-- Modal Body -->
                    <div class="p-5 space-y-4">
                        <div>
                            <label class="block text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-1.5">
                                What needs to be changed?
                            </label>
                            <textarea 
                                ref="customPromptInputRef"
                                v-model="customPromptInput"
                                @keydown.enter.exact.prevent="submitCustomPrompt"
                                rows="3"
                                class="input-field w-full text-xs leading-relaxed resize-none py-2.5"
                                placeholder="e.g. Add a button to reset orientation, improve colors, fix the animation glitch..."
                            ></textarea>
                            <p class="text-[10px] text-gray-400 mt-1 flex items-center justify-between">
                                <span>Press <kbd class="px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-700 font-mono">Enter</kbd> to generate</span>
                                <span><kbd class="px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-700 font-mono">Shift+Enter</kbd> for newline</span>
                            </p>
                        </div>

                        <!-- Suggestions / Quick Chips -->
                        <div>
                            <span class="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-1.5">Suggestions:</span>
                            <div class="flex flex-wrap gap-1.5">
                                <button 
                                    v-for="s in customPromptSuggestions" 
                                    :key="s"
                                    type="button"
                                    @click="customPromptInput = s; customPromptInputRef?.focus();"
                                    class="px-2 py-1 rounded-lg text-[11px] font-medium bg-gray-100 dark:bg-gray-700/60 hover:bg-purple-100 dark:hover:bg-purple-950/40 text-gray-700 dark:text-gray-300 hover:text-purple-700 dark:hover:text-purple-300 border border-gray-200 dark:border-gray-600 transition-colors"
                                >
                                    {{ s }}
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Modal Footer -->
                    <div class="px-5 py-3 border-t dark:border-gray-700 bg-gray-50/70 dark:bg-gray-850/70 flex items-center justify-between select-none">
                        <button 
                            type="button" 
                            @click="closeCustomPromptModal" 
                            class="btn btn-secondary btn-xs"
                        >
                            Cancel
                        </button>

                        <button 
                            type="button" 
                            @click="submitCustomPrompt" 
                            :disabled="!customPromptInput.trim() || isGeneratingAi"
                            class="btn btn-primary btn-xs px-4 flex items-center gap-1.5 shadow-sm bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 border-none text-white font-bold"
                        >
                            <IconAnimateSpin v-if="isGeneratingAi" class="w-3.5 h-3.5 animate-spin" />
                            <IconSparkles v-else class="w-3.5 h-3.5 text-amber-300" />
                            <span>Generate & View Diff</span>
                        </button>
                    </div>

                </div>
            </div>
        </Teleport>

        <!-- Teleported AI Selection Assistant Modal -->
        <Teleport to="body">
            <div 
                v-if="isAiModalOpen" 
                @click.self="closeAiModal" 
                @keydown.esc="closeAiModal" 
                class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150"
            >
                <div class="bg-white dark:bg-gray-800 w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden border border-gray-200 dark:border-gray-700 flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-150">

                    <!-- Header -->
                    <div class="px-5 py-3.5 border-b dark:border-gray-700 flex items-center justify-between bg-gradient-to-r from-purple-600 to-indigo-600 text-white">
                        <div class="flex items-center gap-2.5">
                            <div class="p-1.5 rounded-lg bg-white/20">
                                <IconSparkles class="w-4 h-4 text-amber-300" />
                            </div>
                            <div>
                                <h3 class="font-bold text-sm leading-tight flex items-center gap-2">
                                    <span>LoLLMs Copilot</span>
                                    <span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/20 uppercase tracking-wider font-bold">
                                        {{ language }}
                                    </span>
                                </h3>
                                <p class="text-[11px] opacity-80 mt-0.5">
                                    {{ savedSelectionRange && (savedSelectionRange.to - savedSelectionRange.from) > 1 ? `${selectionLineCount} lines selected with full file context` : 'Full document context' }}
                                </p>
                            </div>
                        </div>
                        <button @click="closeAiModal" class="p-1 hover:bg-white/20 rounded-lg transition-colors" title="Close (Esc)">
                            <IconXMark class="w-5 h-5" />
                        </button>
                    </div>

                    <!-- Modal Body -->
                    <div class="p-5 overflow-y-auto custom-scrollbar flex flex-col gap-4 grow">

                        <!-- Collapsible Selection Snippet Preview -->
                        <div class="rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/60 overflow-hidden text-xs">
                            <div @click="showFullSelectionPreview = !showFullSelectionPreview" class="px-3 py-2 flex items-center justify-between cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors select-none">
                                <span class="font-bold text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
                                    <svg class="w-3.5 h-3.5 transition-transform" :class="{'rotate-90': showFullSelectionPreview}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
                                    <span>Target Selection ({{ savedSelectedText.length }} chars)</span>
                                </span>
                                <span class="text-[10px] text-gray-400 font-mono">{{ showFullSelectionPreview ? 'Collapse' : 'Expand preview' }}</span>
                            </div>
                            <div v-if="showFullSelectionPreview" class="p-3 border-t dark:border-gray-700 font-mono text-[11px] leading-relaxed max-h-40 overflow-y-auto custom-scrollbar whitespace-pre-wrap text-gray-800 dark:text-gray-200">
                                {{ savedSelectedText }}
                            </div>
                        </div>

                        <!-- Quick Action Preset Chips -->
                        <div class="flex flex-wrap gap-1.5">
                            <button 
                                v-for="preset in quickAiPresets" 
                                :key="preset.label"
                                @click="handleRunAiQuery(preset.prompt)"
                                :disabled="isGeneratingSelectionAi"
                                class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-gray-100 dark:bg-gray-700/70 hover:bg-purple-100 dark:hover:bg-purple-950/50 text-gray-700 dark:text-gray-200 hover:text-purple-700 dark:hover:text-purple-300 border border-gray-200 dark:border-gray-600 transition-all flex items-center gap-1 disabled:opacity-50"
                            >
                                <span>{{ preset.icon }}</span>
                                <span>{{ preset.label }}</span>
                            </button>
                        </div>

                        <!-- Prompt Input Field -->
                        <div class="flex items-center gap-2">
                            <input 
                                ref="aiInputRef"
                                v-model="aiUserQuery"
                                @keyup.enter="handleRunAiQuery()"
                                :disabled="isGeneratingSelectionAi"
                                placeholder="Ask anything about this selection or specify changes..." 
                                class="input-field text-xs grow py-2"
                            />
                            <button 
                                @click="handleRunAiQuery()" 
                                :disabled="isGeneratingSelectionAi || !aiUserQuery.trim()" 
                                class="btn btn-primary btn-sm px-4 flex items-center gap-1.5 shrink-0 shadow-sm"
                            >
                                <IconAnimateSpin v-if="isGeneratingSelectionAi" class="w-3.5 h-3.5 animate-spin" />
                                <IconSend v-else class="w-3.5 h-3.5" />
                                <span>Ask</span>
                            </button>
                        </div>

                        <!-- Error Banner -->
                        <div v-if="aiError" class="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-xl text-xs text-red-700 dark:text-red-300">
                            {{ aiError }}
                        </div>

                        <!-- Loading State -->
                        <div v-if="isGeneratingSelectionAi" class="py-8 flex flex-col items-center justify-center text-gray-500 dark:text-gray-400 gap-2">
                            <IconAnimateSpin class="w-7 h-7 text-purple-600 animate-spin" />
                            <span class="text-xs font-bold">LoLLMs is analyzing selection and file context...</span>
                        </div>

                        <!-- AI Response Viewer -->
                        <div v-else-if="aiResponse" class="rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/40 p-4 space-y-3">
                            <div class="flex items-center justify-between border-b dark:border-gray-700 pb-2">
                                <span class="text-[10px] font-black uppercase tracking-wider text-purple-600 dark:text-purple-400">
                                    LoLLMs Response
                                </span>
                                <button @click="copyAiResponse(extractedResponseCode || aiResponse)" class="btn btn-secondary btn-xs flex items-center gap-1">
                                    <IconCheckCircle v-if="justCopiedResponse" class="w-3.5 h-3.5 text-emerald-500" />
                                    <IconCopy v-else class="w-3.5 h-3.5" />
                                    <span>{{ justCopiedResponse ? 'Copied!' : (extractedResponseCode ? 'Copy Code' : 'Copy') }}</span>
                                </button>
                            </div>

                            <div class="prose dark:prose-invert max-w-none text-xs leading-relaxed max-h-64 overflow-y-auto custom-scrollbar">
                                <MessageContentRenderer :content="aiResponse" />
                            </div>

                            <!-- Actions on Selection -->
                            <div class="pt-3 border-t dark:border-gray-700 flex items-center justify-end gap-2 flex-wrap">
                                <button 
                                    @click="openDiffFromSelectionModal" 
                                    class="btn btn-secondary btn-xs flex items-center gap-1.5 font-bold text-purple-600 dark:text-purple-300"
                                    title="Open side-by-side split diff comparison"
                                >
                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path></svg>
                                    <span>Compare Split Diff</span>
                                </button>
                                <button 
                                    v-if="extractedResponseCode" 
                                    @click="replaceSelectionWith(extractedResponseCode)" 
                                    class="btn btn-primary btn-xs flex items-center gap-1.5 shadow-sm"
                                    title="Replace selection with the extracted code block"
                                >
                                    <IconCheckCircle class="w-3.5 h-3.5" />
                                    <span>Replace Code</span>
                                </button>
                                <button 
                                    @click="replaceSelectionWith(aiResponse)" 
                                    class="btn btn-secondary btn-xs"
                                    title="Replace selection with the full response text"
                                >
                                    <span>Replace All</span>
                                </button>
                                <button 
                                    @click="insertBelowSelection(extractedResponseCode || aiResponse)" 
                                    class="btn btn-secondary btn-xs"
                                    title="Insert beneath current selection"
                                >
                                    <span>Insert Below</span>
                                </button>
                            </div>
                        </div>

                    </div>
                </div>
            </div>
        </Teleport>
    </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { basicSetup } from "codemirror";
import { EditorView, keymap, placeholder as cmPlaceholder } from "@codemirror/view";
import { EditorState, Compartment, StateEffect, StateField } from "@codemirror/state";
import { Decoration } from "@codemirror/view";
import { insertNewline } from "@codemirror/commands";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { languages } from "@codemirror/language-data";
import { html } from "@codemirror/lang-html";
import { python } from "@codemirror/lang-python";
import { javascript } from "@codemirror/lang-javascript";
import { indentWithTab } from "@codemirror/commands";
import { search, searchKeymap } from "@codemirror/search";

import { useDiscussionsStore } from '../../../stores/discussions';
import { useUiStore } from '../../../stores/ui';
import { usePyodideStore } from '../../../stores/pyodide';
import { foldAll, unfoldAll } from "@codemirror/language";
import apiClient from '../../../services/api';

import Toolbar from './Toolbar.vue';
import StatusBar from './StatusBar.vue';
import MessageContentRenderer from '../MessageContentRenderer/MessageContentRenderer.vue';
import DiffViewerModal from './DiffViewerModal.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconCopy from '../../../assets/icons/IconCopy.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import IconXMark from '../../../assets/icons/IconXMark.vue';
import IconSend from '../../../assets/icons/IconSend.vue';

const props = defineProps({
    modelValue: { type: String, required: true },
    isChatMode: { type: Boolean, default: false },
    editorClass: { type: [String, Object, Array], default: '' },
    toolbarClass: { type: [String, Object,Array], default: '' },
    buttonClass: { type: [String, Object, Array], default: '' },
    theme: { type: Object, default: null },
    placeholder: { type: String, default: '' },
    autofocus: { type: Boolean, default: false },
    extensions: { type: Array, default: () => [] },
    language: { type: String, default: 'markdown' }, // 'markdown', 'python', 'html', 'svg', 'mermaid', 'latex'
    allowedModes: { type: String, default: 'both', validator: (val) => ['edit_only', 'render_only', 'both'].includes(val) },
    renderable: { type: Boolean, default: true },
    initialMode: { type: String, default: 'edit', validator: (val) => ['edit', 'view'].includes(val) },
    readOnly: { type: Boolean, default: false }
});

const emit = defineEmits(['update:modelValue', 'ready', 'submit']);

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const pyodideStore = usePyodideStore();
const editorRef = ref(null);
const editorView = ref(null);
let updatingFromSelf = false;

// Content Type Awareness
const langKey = computed(() => (props.language || '').toLowerCase().trim());
const isPython = computed(() => langKey.value === 'python' || langKey.value === 'py');
const isJs = computed(() => ['javascript', 'typescript', 'js', 'ts'].includes(langKey.value));
const isRunnable = computed(() => isPython.value || isJs.value);

// Console Execution Drawer State
const showConsole = ref(false);
const isRunningCode = ref(false);
const consoleOutput = ref([]);
const executionStats = ref(null);

// In-Editor AI Copilot State
const isGeneratingAi = ref(false);
const aiProposal = ref(null);

// Custom Prompt to Change Modal State
const isCustomPromptModalOpen = ref(false);
const customPromptInput = ref('');
const customPromptInputRef = ref(null);

// Split-View Diff Modal State
const isDiffModalOpen = ref(false);
const diffOriginalText = ref('');
const diffModifiedText = ref('');
const diffTitle = ref('Code Changes');
const diffIsSelection = ref(false);

// Interactive Selection Assistant Modal & Floating Pill State
const showFloatingPill = ref(false);
const floatingPillStyle = ref({ top: '0px', left: '0px' });
const isAiModalOpen = ref(false);
const savedSelectedText = ref('');
const savedSelectionRange = ref(null);
const fullFileContext = ref('');
const aiUserQuery = ref('');
const aiResponse = ref('');
const aiError = ref('');
const isGeneratingSelectionAi = ref(false);
const showFullSelectionPreview = ref(false);
const aiInputRef = ref(null);
const justCopiedResponse = ref(false);

// Determine start mode based on allowed modes
const getStartMode = () => {
    if (props.allowedModes === 'edit_only') return 'edit';
    if (props.allowedModes === 'render_only') return 'view';
    return props.initialMode;
};

const currentMode = ref(getStartMode());
const isWrappingEnabled = ref(true);
let wrappingCompartment = new Compartment();
let readOnlyCompartment = new Compartment();
const isRendering = ref(false);

// --- CODE MINIMAP STATE ---
const showMinimap = ref(localStorage.getItem('cm_show_minimap') !== 'false');
const minimapCanvasRef = ref(null);
const viewportTop = ref(0);
const viewportHeight = ref(30);
const isDraggingViewport = ref(false);
let minimapResizeObserver = null;

function toggleMinimap() {
    showMinimap.value = !showMinimap.value;
    localStorage.setItem('cm_show_minimap', showMinimap.value ? 'true' : 'false');
    if (showMinimap.value) {
        nextTick(() => {
            renderMinimap();
        });
    }
}

function renderMinimap() {
    if (!showMinimap.value || !minimapCanvasRef.value || !editorView.value) return;
    const canvas = minimapCanvasRef.value;
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const state = editorView.value.state;
    const doc = state.doc;
    const totalLines = doc.lines;
    if (totalLines === 0) return;

    const isDark = uiStore.currentTheme === 'dark';
    ctx.clearRect(0, 0, rect.width, rect.height);

    const maxLinesToRender = Math.min(totalLines, Math.floor(rect.height / 2));
    const lineStep = totalLines / Math.max(1, maxLinesToRender);
    const lineHeight = Math.max(1.2, rect.height / totalLines);

    for (let i = 0; i < maxLinesToRender; i++) {
        const lineNum = Math.min(totalLines, Math.floor(i * lineStep) + 1);
        const line = doc.line(lineNum);
        const text = line.text;
        if (!text || !text.trim()) continue;

        const leadingSpaces = text.match(/^\s*/)[0].length;
        const contentLen = Math.min(text.trim().length, 80);

        const y = (i / maxLinesToRender) * rect.height;
        const x = 4 + Math.min(leadingSpaces * 2.5, rect.width * 0.4);
        const w = Math.min(contentLen * 1.8, rect.width - x - 4);

        const trimmed = text.trim();
        if (trimmed.startsWith('//') || trimmed.startsWith('#') || trimmed.startsWith('/*') || trimmed.startsWith('*')) {
            ctx.fillStyle = isDark ? 'rgba(156, 163, 175, 0.4)' : 'rgba(156, 163, 175, 0.6)';
        } else if (/^(function|def|class|const|let|var|import|export|from|return|if|else|for|while|try|catch)\b/.test(trimmed)) {
            ctx.fillStyle = isDark ? 'rgba(147, 197, 253, 0.8)' : 'rgba(37, 99, 235, 0.7)';
        } else if (trimmed.startsWith('<') || trimmed.endsWith('>')) {
            ctx.fillStyle = isDark ? 'rgba(244, 114, 182, 0.7)' : 'rgba(219, 39, 119, 0.7)';
        } else {
            ctx.fillStyle = isDark ? 'rgba(229, 231, 235, 0.55)' : 'rgba(75, 85, 99, 0.65)';
        }

        ctx.fillRect(x, y, Math.max(2, w), Math.max(1, lineHeight - 0.5));
    }

    updateMinimapViewport();
}

function updateMinimapViewport() {
    if (!editorView.value || !minimapCanvasRef.value) return;
    const scroller = editorView.value.scrollDOM;
    const canvas = minimapCanvasRef.value;
    const rect = canvas.getBoundingClientRect();
    if (rect.height === 0) return;

    const scrollHeight = scroller.scrollHeight;
    const clientHeight = scroller.clientHeight;
    const scrollTop = scroller.scrollTop;

    if (scrollHeight <= clientHeight) {
        viewportTop.value = 0;
        viewportHeight.value = rect.height;
    } else {
        const ratio = rect.height / scrollHeight;
        viewportTop.value = scrollTop * ratio;
        viewportHeight.value = Math.max(16, clientHeight * ratio);
    }
}

function handleMinimapClick(e) {
    if (!editorView.value || !minimapCanvasRef.value) return;
    const canvas = minimapCanvasRef.value;
    const rect = canvas.getBoundingClientRect();
    const clickY = e.clientY - rect.top;

    const scroller = editorView.value.scrollDOM;
    const targetScrollTop = (clickY / rect.height) * scroller.scrollHeight - (scroller.clientHeight / 2);

    scroller.scrollTo({
        top: Math.max(0, targetScrollTop),
        behavior: 'smooth'
    });
}

function startViewportDrag(e) {
    if (!editorView.value || !minimapCanvasRef.value) return;
    isDraggingViewport.value = true;
    const startY = e.clientY;
    const scroller = editorView.value.scrollDOM;
    const initialScroll = scroller.scrollTop;
    const rect = minimapCanvasRef.value.getBoundingClientRect();
    const ratio = scroller.scrollHeight / rect.height;

    const onMouseMove = (moveEvent) => {
        if (!isDraggingViewport.value) return;
        const deltaY = moveEvent.clientY - startY;
        scroller.scrollTop = Math.max(0, Math.min(scroller.scrollHeight - scroller.clientHeight, initialScroll + (deltaY * ratio)));
    };

    const onMouseUp = () => {
        isDraggingViewport.value = false;
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
}

// --- TOKEN VISUALIZER STATE & DECORATIONS ---
const showTokens = ref(false);
const isTokenizing = ref(false);
const tokenCount = ref(null);
let tokenizeDebounceTimer = null;

const setTokenDecorations = StateEffect.define();

const tokenField = StateField.define({
    create() {
        return Decoration.none;
    },
    update(decorations, tr) {
        for (let e of tr.effects) {
            if (e.is(setTokenDecorations)) {
                return e.value;
            }
        }
        return decorations.map(tr.changes);
    },
    provide: f => EditorView.decorations.from(f)
});

function buildTokenDecorations(tokens, docLength) {
    if (!tokens || !tokens.length) return Decoration.none;
    const decos = [];
    const colorsCount = 8;
    for (const tok of tokens) {
        if (tok.start >= tok.end || tok.end > docLength || tok.start < 0) continue;
        const colorIdx = tok.index % colorsCount;
        decos.push(
            Decoration.mark({
                class: `cm-token cm-token-${colorIdx}`,
                attributes: {
                    title: `Token #${tok.id} ("${tok.text.replace(/"/g, '&quot;')}") • #${tok.index + 1}`
                }
            }).range(tok.start, tok.end)
        );
    }
    return Decoration.set(decos, true);
}

async function updateTokenBreakdown() {
    const text = props.modelValue || '';
    if (!text.trim()) {
        clearTokenBreakdown();
        return;
    }
    isTokenizing.value = true;
    try {
        const res = await apiClient.post('/api/discussions/tokenize-details', { text });
        tokenCount.value = res.data.token_count;
        if (editorView.value && showTokens.value) {
            const decos = buildTokenDecorations(res.data.tokens, editorView.value.state.doc.length);
            editorView.value.dispatch({
                effects: setTokenDecorations.of(decos)
            });
        }
    } catch (e) {
        console.error("Tokenization visualizer error:", e);
    } finally {
        isTokenizing.value = false;
    }
}

function clearTokenBreakdown() {
    if (editorView.value) {
        editorView.value.dispatch({
            effects: setTokenDecorations.of(Decoration.none)
        });
    }
    tokenCount.value = null;
}

async function handleToggleTokens() {
    showTokens.value = !showTokens.value;
    if (showTokens.value) {
        await updateTokenBreakdown();
    } else {
        clearTokenBreakdown();
    }
}

// --- CODE FOLDING CONTROLS ---
function handleFoldAll() {
    if (editorView.value) foldAll(editorView.value);
}

function handleUnfoldAll() {
    if (editorView.value) unfoldAll(editorView.value);
}

// --- SMART ADAPTIVE DOCUMENT FORMATTING ---
function formatMarkdownTables(text) {
    const tableRegex = /((?:^[ \t]*\|[^\n]+\|[ \t]*(?:\r?\n|$))+)/gm;
    return text.replace(tableRegex, (rawTable) => {
        const lines = rawTable.trim().split(/\r?\n/).map(l => l.trim());
        if (lines.length < 2) return rawTable;

        const rows = lines.map(line => {
            return line.replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
        });

        const numCols = Math.max(...rows.map(r => r.length));
        const colWidths = new Array(numCols).fill(3);

        rows.forEach((row, rowIdx) => {
            if (rowIdx === 1) return;
            row.forEach((cell, colIdx) => {
                colWidths[colIdx] = Math.max(colWidths[colIdx], cell.length);
            });
        });

        const formattedLines = rows.map((row, rowIdx) => {
            const cells = [];
            for (let c = 0; c < numCols; c++) {
                const val = row[c] || '';
                const w = colWidths[c];
                if (rowIdx === 1) {
                    const isLeft = val.startsWith(':');
                    const isRight = val.endsWith(':');
                    let sep = '-'.repeat(w);
                    if (isLeft && isRight) sep = ':' + '-'.repeat(Math.max(1, w - 2)) + ':';
                    else if (isLeft) sep = ':' + '-'.repeat(Math.max(1, w - 1));
                    else if (isRight) sep = '-'.repeat(Math.max(1, w - 1)) + ':';
                    cells.push(sep);
                } else {
                    cells.push(val.padEnd(w, ' '));
                }
            }
            return '| ' + cells.join(' | ') + ' |';
        });

        return formattedLines.join('\n') + '\n';
    });
}

function formatXmlHtml(text) {
    let formatted = '';
    let indent = 0;
    const tab = '  ';
    const tokens = text.replace(/>\s*</g, '><').split(/(<[^>]+>)/g).filter(Boolean);

    for (let token of tokens) {
        token = token.trim();
        if (!token) continue;

        if (token.startsWith('</')) {
            indent = Math.max(0, indent - 1);
            formatted += tab.repeat(indent) + token + '\n';
        } else if (token.startsWith('<') && !token.startsWith('<!') && !token.startsWith('<?') && !token.endsWith('/>') && !token.includes('</')) {
            formatted += tab.repeat(indent) + token + '\n';
            const voidTags = ['<area', '<base', '<br', '<col', '<embed', '<hr', '<img', '<input', '<link', '<meta', '<param', '<source', '<track', '<wbr'];
            const isVoid = voidTags.some(vt => token.toLowerCase().startsWith(vt));
            if (!isVoid) indent++;
        } else if (token.startsWith('<')) {
            formatted += tab.repeat(indent) + token + '\n';
        } else {
            formatted += tab.repeat(indent) + token + '\n';
        }
    }
    return formatted.trim();
}

function handleFormatDocument() {
    const text = props.modelValue || '';
    if (!text.trim()) return;

    const lang = langKey.value;
    let formatted = null;

    if (lang === 'json' || text.startsWith('{') || text.startsWith('[')) {
        try {
            const parsed = JSON.parse(text);
            formatted = JSON.stringify(parsed, null, 2);
            uiStore.addNotification('JSON formatted successfully.', 'success', 2000);
        } catch (e) {
            uiStore.addNotification(`JSON syntax error: ${e.message}`, 'error', 4000);
            return;
        }
    } else if (lang === 'markdown' || lang === 'md' || !lang) {
        formatted = formatMarkdownTables(text);
        uiStore.addNotification('Markdown formatted & tables aligned.', 'success', 2000);
    } else if (['html', 'xml', 'svg'].includes(lang)) {
        formatted = formatXmlHtml(text);
        uiStore.addNotification(`${lang.toUpperCase()} formatted.`, 'success', 2000);
    } else {
        formatted = text
            .split('\n')
            .map(l => l.trimEnd())
            .join('\n')
            .replace(/\n{3,}/g, '\n\n');
        uiStore.addNotification('Document formatted.', 'success', 2000);
    }

    if (formatted !== null && formatted !== text) {
        emit('update:modelValue', formatted);
    }
}

// --- IN-BROWSER CODE EXECUTION (PYODIDE & JS) ---
async function handleRunCode() {
    if (!editorView.value || isRunningCode.value) return;
    const code = props.modelValue || '';
    if (!code.trim()) {
        uiStore.addNotification('Editor is empty. Nothing to execute.', 'warning');
        return;
    }

    if (isPython.value) {
        await executePythonCode(code);
    } else if (isJs.value) {
        executeJsCode(code);
    }
}

async function executePythonCode(code) {
    isRunningCode.value = true;
    showConsole.value = true;
    consoleOutput.value = [];
    executionStats.value = null;

    if (!pyodideStore.isPyodideReady && !pyodideStore.isLoading) {
        consoleOutput.value.push({ type: 'stdout', text: 'Initializing in-browser Pyodide Python runtime...' });
        await pyodideStore.initialize();
    }

    try {
        const result = await pyodideStore.runPython(
            code,
            (stdout) => { consoleOutput.value.push({ type: 'stdout', text: stdout }); },
            (stderr) => { consoleOutput.value.push({ type: 'stderr', text: stderr }); }
        );
        if (result.results !== undefined && result.results !== null) {
            consoleOutput.value.push({ type: 'result', text: `=> ${result.results}` });
        }
        executionStats.value = {
            time: `${result.executionTime}ms`,
            success: !result.stderr
        };
    } catch (err) {
        consoleOutput.value.push({ type: 'stderr', text: err.message || String(err) });
        executionStats.value = { time: '0ms', success: false };
    } finally {
        isRunningCode.value = false;
    }
}

function executeJsCode(code) {
    isRunningCode.value = true;
    showConsole.value = true;
    consoleOutput.value = [];

    const origLog = console.log;
    const origErr = console.error;
    const origWarn = console.warn;

    console.log = (...args) => consoleOutput.value.push({ 
        type: 'stdout', 
        text: args.map(a => typeof a === 'object' ? JSON.stringify(a, null, 2) : String(a)).join(' ') 
    });
    console.error = (...args) => consoleOutput.value.push({ 
        type: 'stderr', 
        text: args.map(a => typeof a === 'object' ? JSON.stringify(a, null, 2) : String(a)).join(' ') 
    });
    console.warn = (...args) => consoleOutput.value.push({ 
        type: 'stderr', 
        text: args.map(a => typeof a === 'object' ? JSON.stringify(a, null, 2) : String(a)).join(' ') 
    });

    const start = performance.now();
    try {
        const fn = new Function(code);
        const res = fn();
        if (res !== undefined) {
            consoleOutput.value.push({ type: 'result', text: `=> ${typeof res === 'object' ? JSON.stringify(res, null, 2) : String(res)}` });
        }
        executionStats.value = { time: `${Math.round(performance.now() - start)}ms`, success: true };
    } catch (err) {
        consoleOutput.value.push({ type: 'stderr', text: err.message || String(err) });
        executionStats.value = { time: `${Math.round(performance.now() - start)}ms`, success: false };
    } finally {
        console.log = origLog;
        console.error = origErr;
        console.warn = origWarn;
        isRunningCode.value = false;
    }
}

// --- ADAPTIVE AI COPILOT ---
function getAiInstruction(lang, actionKey) {
    const instructions = {
        python: {
            refactor: "Refactor the following Python code adhering strictly to PEP 8, clean code (SOLID, DRY, KISS), and modern type hints. Output ONLY the updated Python code enclosed in a ```python ... ``` block without conversational preamble.",
            docstrings: "Add comprehensive PEP-257 docstrings and type annotations to all functions and classes in the following Python code. Output ONLY the updated code in ```python ... ```.",
            fix: "Analyze the following Python code for potential bugs, security issues, and edge cases. Provide the corrected Python code enclosed in a ```python ... ``` block.",
            explain: "Explain the following Python code concisely, breaking down its logic, time/space complexity, and key functions."
        },
        javascript: {
            refactor: "Refactor the following JavaScript/TypeScript code using modern ES6+ idioms, async/await, and clean code principles. Output ONLY the code in a ```javascript ... ``` block.",
            typescript: "Convert the following JavaScript code to clean TypeScript with strict interface and type definitions. Output ONLY the TypeScript code in a ```typescript ... ``` block.",
            fix: "Audit and fix bugs, unhandled promise rejections, or type mismatches in the following JavaScript/TypeScript code. Output the corrected code in a ```javascript ... ``` block.",
            explain: "Explain the following JavaScript/TypeScript code, focusing on async behavior, logic flow, and data transformations."
        },
        html: {
            refactor: "Clean up and optimize the following HTML/SVG markup. Output ONLY the updated markup in a ```html ... ``` block.",
            accessibility: "Audit and enhance the following HTML markup for accessibility (WCAG 2.1 compliance, ARIA attributes, semantic tags). Output ONLY the updated markup in a ```html ... ``` block.",
            explain: "Explain the structure, components, and layout of the following HTML/SVG markup."
        },
        json: {
            fix: "The following JSON might be malformed or invalid. Repair it to be 100% valid JSON syntax. Output ONLY the raw valid JSON inside a ```json ... ``` block.",
            schema: "Generate a comprehensive JSON Schema (draft-07) that validates the following JSON data. Output ONLY the schema inside a ```json ... ``` block."
        },
        markdown: {
            polish: "Polish and enhance the following Markdown text, improving clarity, flow, and phrasing while preserving all markdown structures. Output ONLY the polished Markdown in a ```markdown ... ``` block.",
            toc: "Generate a markdown Table of Contents with working anchor links based on the headings in the following text. Output ONLY the Table of Contents.",
            summary: "Provide a concise executive summary of the following Markdown document in bullet points."
        }
    };

    const group = instructions[lang] || instructions['markdown'];
    return group[actionKey] || "Improve and optimize this content. Output the result clearly.";
}

function getActionTitle(actionKey) {
    const titles = {
        refactor: 'Refactor Code',
        docstrings: 'Add Docstrings',
        fix: 'Bug Fix & Security',
        explain: 'Code Explanation',
        typescript: 'Convert to TypeScript',
        accessibility: 'Accessibility (ARIA)',
        schema: 'JSON Schema',
        polish: 'Polish Writing',
        toc: 'Table of Contents',
        summary: 'Executive Summary'
    };
    return titles[actionKey] || 'AI Proposal';
}

function extractCodeFromMarkdown(raw, lang) {
    if (!raw) return '';
    const match = raw.match(/```(?:\w+)?\r?\n([\s\S]*?)```/);
    if (match) return match[1].trimEnd();
    return raw.trim();
}

// Parse Search/Replace patches (both Aider format and XML tag format)
function parseSearchReplaceBlocks(rawText) {
    if (!rawText) return [];
    const blocks = [];

    // Format 1: Aider diff markers
    const aiderRegex = /<<<<<<< SEARCH\r?\n([\s\S]*?)\r?\n=======\r?\n([\s\S]*?)\r?\n>>>>>>> (?:REPLACE|)/gi;
    let match;
    while ((match = aiderRegex.exec(rawText)) !== null) {
        blocks.push({
            search: match[1],
            replace: match[2],
            raw: match[0]
        });
    }

    // Format 2: Structured XML tag fallback (<patch><search>...</search><replace>...</replace></patch>)
    if (blocks.length === 0) {
        const xmlRegex = /<patch>\s*<search>([\s\S]*?)<\/search>\s*<replace>([\s\S]*?)<\/replace>\s*<\/patch>/gi;
        while ((match = xmlRegex.exec(rawText)) !== null) {
            blocks.push({
                search: match[1],
                replace: match[2],
                raw: match[0]
            });
        }
    }

    return blocks;
}

// Apply patches sequentially with character-for-character verification & whitespace tolerance
function applySearchReplacePatches(originalText, patches) {
    let current = (originalText || '').replace(/\r\n/g, '\n');
    const applied = [];
    const failed = [];

    for (let i = 0; i < patches.length; i++) {
        const patch = patches[i];
        const searchNorm = patch.search.replace(/\r\n/g, '\n');
        const replaceNorm = patch.replace.replace(/\r\n/g, '\n');

        let idx = current.indexOf(searchNorm);

        if (idx !== -1) {
            current = current.slice(0, idx) + replaceNorm + current.slice(idx + searchNorm.length);
            applied.push(i + 1);
        } else {
            // Secondary attempt: trimmed line-by-line matching
            const trimmedSearch = searchNorm.trim();
            const trimmedIdx = current.indexOf(trimmedSearch);

            if (trimmedSearch.length > 0 && trimmedIdx !== -1) {
                current = current.slice(0, trimmedIdx) + replaceNorm.trim() + current.slice(trimmedIdx + trimmedSearch.length);
                applied.push(i + 1);
            } else {
                failed.push({
                    index: i + 1,
                    search: patch.search,
                    replace: patch.replace
                });
            }
        }
    }

    return {
        success: failed.length === 0,
        resultText: current,
        appliedCount: applied.length,
        failedPatches: failed
    };
}

// Self-healing execution loop: Validates patches and asks LLM to retry on mismatch
async function executeAiGenerationWithSelfHealing(initialPrompt, originalText, lang, maxRetries = 2) {
    let currentPrompt = initialPrompt;
    let attempts = 0;

    while (attempts <= maxRetries) {
        attempts++;
        const res = await apiClient.post('/api/lollms/generate', {
            prompt: currentPrompt,
            max_new_tokens: 4096,
            temperature: 0.2
        }, {
            timeout: 300000 // 5 minutes timeout
        });

        const rawResult = res.data?.generated_text || '';
        const patches = parseSearchReplaceBlocks(rawResult);

        if (patches.length > 0) {
            const patchResult = applySearchReplacePatches(originalText, patches);
            if (patchResult.success) {
                return {
                    code: patchResult.resultText,
                    isPatch: true,
                    appliedCount: patchResult.appliedCount
                };
            }

            // Patch verification failed
            console.warn(`[AI Copilot] Patch mismatch on attempt ${attempts}:`, patchResult.failedPatches);

            if (attempts <= maxRetries) {
                uiStore.addNotification(`Patch mismatch on attempt ${attempts}. Asking model to heal...`, 'info', 2500);

                const failedDetails = patchResult.failedPatches.map(f =>
                    `Block #${f.index} failed to match:\n<<<<<<< SEARCH\n${f.search}\n=======\n`
                ).join('\n');

                currentPrompt = `The previous SEARCH/REPLACE patch could not be applied because the SEARCH block(s) did not match the original text character-for-character:

${failedDetails}

Original Content:
<file_context>
${originalText}
</file_context>

Please re-inspect the exact original code lines and return corrected <<<<<<< SEARCH / ======= / >>>>>>> REPLACE blocks (or output the complete updated file in a single \`\`\`${lang} ... \`\`\` block).`;
                continue;
            } else {
                // Fallback attempt: check if full code block was included
                const fallbackCode = extractCodeFromMarkdown(rawResult, lang);
                if (fallbackCode && fallbackCode !== rawResult) {
                    return { code: fallbackCode, isPatch: false, appliedCount: 0 };
                }
                throw new Error(`Failed to apply ${patchResult.failedPatches.length} patch block(s) after ${attempts} attempts. Please try again with a more specific instruction.`);
            }
        } else {
            // Full rewrite or raw code returned
            const cleanCode = extractCodeFromMarkdown(rawResult, lang) || rawResult.trim();
            return {
                code: cleanCode,
                isPatch: false,
                appliedCount: 0
            };
        }
    }
}

async function handleAiAssist(actionKey, customInstruction = null) {
    if (!editorView.value || isGeneratingAi.value) return;

    const view = editorView.value;
    const state = view.state;
    const selection = state.selection.main;
    const hasSelection = !selection.empty && (selection.to - selection.from) > 1;

    const targetText = hasSelection 
        ? state.doc.sliceString(selection.from, selection.to)
        : state.doc.toString();

    if (!targetText.trim()) {
        uiStore.addNotification('No code or text to analyze.', 'warning');
        return;
    }

    const lang = langKey.value || 'markdown';
    const isCustom = actionKey === 'custom';
    const instruction = isCustom ? customInstruction : getAiInstruction(lang, actionKey);
    const actionTitle = isCustom 
        ? (customInstruction.length > 35 ? customInstruction.substring(0, 35) + '...' : customInstruction) 
        : getActionTitle(actionKey);

    const prompt = `You are LoLLMs AI Senior Code Copilot.
Content Type: ${lang}
Action: ${isCustom ? 'Custom User Request' : actionKey}

<file_context>
${state.doc.toString()}
</file_context>

${hasSelection ? `<selected_code>\n${targetText}\n</selected_code>\n` : ''}

Instruction:
${instruction}

OUTPUT FORMAT RULES (CRITICAL):
Prefer using SEARCH/REPLACE patch blocks to make fast, targeted, minimal edits without rewriting unchanged code.
Use the following format for each modification:
<<<<<<< SEARCH
[Exact lines currently in the file to replace]
=======
[New replacement lines]
>>>>>>> REPLACE

RULES FOR PATCHES:
1. Every SEARCH block MUST match the character-for-character, whitespace-perfect lines from the original file. Include 1-3 lines of context if necessary for uniqueness.
2. You can provide multiple SEARCH/REPLACE blocks in sequence for different parts of the file.
3. If a complete file rewrite (>60% of code changes) is necessary, you may output the full code inside a single \`\`\`${lang} ... \`\`\` block.
4. Do NOT output conversational chatter or explanations outside the patch blocks.`;

    isGeneratingAi.value = true;
    try {
        uiStore.addNotification(`LoLLMs is generating: ${actionTitle}...`, 'info', 3000);
        
        const executionResult = await executeAiGenerationWithSelfHealing(prompt, targetText, lang, 2);

        aiProposal.value = {
            action: actionKey,
            title: actionTitle,
            originalText: targetText,
            proposedCode: executionResult.code,
            isSelection: hasSelection,
            range: hasSelection ? { from: selection.from, to: selection.to } : { from: 0, to: state.doc.length }
        };

        // Automatically open the Split Diff viewer so user can immediately inspect before applying
        openDiffFromProposal();
        const msg = executionResult.isPatch 
            ? `Applied ${executionResult.appliedCount} verified patch(es)! Inspect split diff to accept.`
            : 'Changes generated! Inspect split diff to accept.';
        uiStore.addNotification(msg, 'success', 3500);
    } catch (e) {
        console.error("AI Assist failed:", e);
        if (e.code === 'ECONNABORTED' || e.message?.includes('timeout')) {
            uiStore.addNotification('AI generation timed out. The model took too long to complete.', 'error');
        } else {
            uiStore.addNotification(e.message || e.response?.data?.detail || 'AI code generation failed.', 'error');
        }
    } finally {
        isGeneratingAi.value = false;
    }
}

// --- PROMPT TO CHANGE MODAL CONTROLS ---
function openCustomPromptModal() {
    customPromptInput.value = '';
    isCustomPromptModalOpen.value = true;
    nextTick(() => {
        customPromptInputRef.value?.focus();
    });
}

function closeCustomPromptModal() {
    isCustomPromptModalOpen.value = false;
}

async function submitCustomPrompt() {
    const promptText = customPromptInput.value.trim();
    if (!promptText || isGeneratingAi.value) return;

    closeCustomPromptModal();
    await handleAiAssist('custom', promptText);
}

const customPromptSuggestions = computed(() => {
    const lang = langKey.value;
    if (['html', 'xml', 'svg'].includes(lang)) {
        return [
            'Add a reset button',
            'Improve colors and visual styling',
            'Make layout responsive for mobile',
            'Add smooth animations and transitions',
            'Fix layout glitches'
        ];
    }
    if (isPython.value) {
        return [
            'Add comprehensive error handling',
            'Optimize algorithmic efficiency',
            'Refactor into modular functions',
            'Add type annotations and docstrings',
            'Add unit tests'
        ];
    }
    if (isJs.value) {
        return [
            'Refactor using async/await',
            'Convert to TypeScript with interfaces',
            'Add input validation',
            'Add event listeners with cleanup',
            'Modernize to ES6+'
        ];
    }
    if (lang === 'json') {
        return [
            'Fix syntax and format',
            'Sort keys alphabetically',
            'Add mock sample data'
        ];
    }
    return [
        'Improve clarity and flow',
        'Format with clean headings and lists',
        'Fix grammar and spelling',
        'Add an executive summary section'
    ];
});

function applyAiProposal() {
    if (!aiProposal.value || !editorView.value) return;
    const { proposedCode, range } = aiProposal.value;
    editorView.value.dispatch({
        changes: { from: range.from, to: range.to, insert: proposedCode }
    });
    aiProposal.value = null;
    uiStore.addNotification('AI changes applied.', 'success', 2000);
}

function insertAiProposalBelow() {
    if (!aiProposal.value || !editorView.value) return;
    const { proposedCode, range } = aiProposal.value;
    const insertPos = range.to;
    editorView.value.dispatch({
        changes: { from: insertPos, insert: '\n\n' + proposedCode }
    });
    aiProposal.value = null;
    uiStore.addNotification('Inserted AI output below.', 'success', 2000);
}

function dismissAiProposal() {
    aiProposal.value = null;
}

// --- SPLIT VIEW DIFF LAUNCHERS & HANDLERS ---
function openDiffFromProposal() {
    if (!aiProposal.value) return;
    diffOriginalText.value = aiProposal.value.originalText || '';
    diffModifiedText.value = aiProposal.value.proposedCode || '';
    diffTitle.value = `${aiProposal.value.title} Diff`;
    diffIsSelection.value = Boolean(aiProposal.value.isSelection);
    isDiffModalOpen.value = true;
}

function openDiffFromSelectionModal() {
    if (!aiResponse.value) return;
    const targetCode = extractedResponseCode.value || aiResponse.value;
    diffOriginalText.value = savedSelectedText.value || '';
    diffModifiedText.value = targetCode;
    diffTitle.value = 'Selection vs Proposed Code';
    diffIsSelection.value = true;
    isDiffModalOpen.value = true;
}

function handleAcceptDiff() {
    if (aiProposal.value) {
        applyAiProposal();
    } else if (savedSelectionRange.value && diffModifiedText.value) {
        replaceSelectionWith(diffModifiedText.value);
    }
    isDiffModalOpen.value = false;
}

function handleInsertBelowDiff() {
    if (aiProposal.value) {
        insertAiProposalBelow();
    } else if (savedSelectionRange.value && diffModifiedText.value) {
        insertBelowSelection(diffModifiedText.value);
    }
    isDiffModalOpen.value = false;
}

// --- INTERACTIVE SELECTION ASSISTANT & FLOATING PILL ---
function updateSelectionState() {
    if (!editorView.value || currentMode.value !== 'edit') {
        showFloatingPill.value = false;
        return;
    }
    const state = editorView.value.state;
    const sel = state.selection.main;
    if (sel.empty || (sel.to - sel.from) < 2) {
        showFloatingPill.value = false;
        return;
    }

    try {
        const headCoords = editorView.value.coordsAtPos(sel.to);
        const hostEl = editorRef.value;
        if (headCoords && hostEl) {
            const hostRect = hostEl.getBoundingClientRect();
            const topPos = headCoords.bottom - hostRect.top + 6;
            const leftPos = Math.max(10, Math.min(headCoords.left - hostRect.left, hostRect.width - 150));

            floatingPillStyle.value = {
                top: `${topPos}px`,
                left: `${leftPos}px`
            };
            showFloatingPill.value = true;
        }
    } catch (e) {
        showFloatingPill.value = false;
    }
}

function openSelectionAiModal(presetAction = null) {
    if (!editorView.value) return;
    const state = editorView.value.state;
    const sel = state.selection.main;
    const isSelection = !sel.empty && (sel.to - sel.from) > 1;

    savedSelectionRange.value = isSelection 
        ? { from: sel.from, to: sel.to }
        : { from: 0, to: state.doc.length };

    savedSelectedText.value = isSelection
        ? state.doc.sliceString(sel.from, sel.to)
        : state.doc.toString();

    fullFileContext.value = state.doc.toString();
    showFloatingPill.value = false;
    isAiModalOpen.value = true;
    aiUserQuery.value = '';
    aiResponse.value = '';
    aiError.value = '';
    showFullSelectionPreview.value = false;

    if (presetAction) {
        nextTick(() => {
            handleRunAiQuery(presetAction);
        });
    } else {
        nextTick(() => {
            aiInputRef.value?.focus();
        });
    }
}

function closeAiModal() {
    isAiModalOpen.value = false;
    if (editorView.value) {
        nextTick(() => editorView.value.focus());
    }
}

const selectionLineCount = computed(() => {
    if (!savedSelectedText.value) return 0;
    return savedSelectedText.value.split('\n').length;
});

const extractedResponseCode = computed(() => {
    if (!aiResponse.value) return null;
    const match = aiResponse.value.match(/```(?:\w+)?\r?\n([\s\S]*?)```/);
    return match ? match[1].trimEnd() : null;
});

const quickAiPresets = computed(() => {
    const lang = langKey.value;
    if (lang === 'python' || lang === 'py') {
        return [
            { label: 'Explain Logic', icon: '💡', prompt: 'Explain the logic, time complexity, and data structures used in this selection.' },
            { label: 'Refactor (PEP 8)', icon: '⚡', prompt: 'Refactor this selection using PEP 8 standards, clean architecture, and type annotations.' },
            { label: 'Fix Bugs', icon: '🐛', prompt: 'Audit this selection for potential bugs, edge cases, and exceptions, and provide the fixed code.' },
            { label: 'Write Tests', icon: '🧪', prompt: 'Write comprehensive pytest unit tests covering happy paths and edge cases for this selection.' },
            { label: 'Add Docstrings', icon: '📝', prompt: 'Add clean PEP-257 docstrings and type hints to this selection.' }
        ];
    }
    if (['javascript', 'typescript', 'js', 'ts'].includes(lang)) {
        return [
            { label: 'Explain Flow', icon: '💡', prompt: 'Explain the logic and asynchronous flow of this selection.' },
            { label: 'To TypeScript', icon: '🏷️', prompt: 'Convert this JavaScript selection to TypeScript with strict interfaces and types.' },
            { label: 'Refactor ES6+', icon: '⚡', prompt: 'Refactor this selection using modern ES6+ syntax, destructuring, and clean code.' },
            { label: 'Fix Bugs', icon: '🐛', prompt: 'Find and fix bugs, unhandled promise rejections, or type issues in this selection.' },
            { label: 'Write Tests', icon: '🧪', prompt: 'Write unit tests (Jest/Vitest) for this selection.' }
        ];
    }
    if (['html', 'xml', 'svg'].includes(lang)) {
        return [
            { label: 'Clean Markup', icon: '⚡', prompt: 'Optimize, indent, and clean up this markup selection.' },
            { label: 'Accessibility', icon: '♿', prompt: 'Enhance this markup for accessibility (ARIA labels, semantic tags, keyboard navigation).' },
            { label: 'Explain Structure', icon: '💡', prompt: 'Explain the DOM structure and layout hierarchy of this selection.' }
        ];
    }
    if (lang === 'json') {
        return [
            { label: 'Repair JSON', icon: '🛠️', prompt: 'Fix any syntax or delimiter errors in this JSON selection and ensure it is valid.' },
            { label: 'Generate Schema', icon: '📋', prompt: 'Generate a JSON Schema (draft-07) that validates this JSON data.' },
            { label: 'Explain Structure', icon: '💡', prompt: 'Explain the schema and data fields in this JSON selection.' }
        ];
    }
    return [
        { label: 'Polish Phrasing', icon: '✨', prompt: 'Polish and improve the clarity, tone, and flow of this text selection.' },
        { label: 'Summarize', icon: '📋', prompt: 'Provide a clear, concise bulleted summary of this selection.' },
        { label: 'Explain Concept', icon: '💡', prompt: 'Explain the concepts discussed in this selection in simple terms.' },
        { label: 'Fix Grammar', icon: '✍️', prompt: 'Fix all grammar, spelling, and punctuation errors in this selection.' }
    ];
});

async function handleRunAiQuery(customInstruction = null) {
    const instruction = customInstruction || aiUserQuery.value.trim();
    if (!instruction || isGeneratingSelectionAi.value) return;

    isGeneratingSelectionAi.value = true;
    aiError.value = '';

    const lang = langKey.value || 'text';
    const selText = savedSelectedText.value || '';
    const fullText = fullFileContext.value || '';

    const prompt = `You are LoLLMs AI Senior Code and Writing Assistant.
Language/Format: ${lang}

<file_context>
${fullText}
</file_context>

<selected_text>
${selText}
</selected_text>

User Request:
${instruction}

Instructions:
1. You have access to both the entire file context and the highlighted selection.
2. If the user asks a question, explain or analyze the code clearly with precision.
3. If the user asks for code changes, refactoring, or additions, output the updated code inside a \`\`\`${lang} ... \`\`\` block, followed by a concise bulleted summary of changes.`;

    try {
        const res = await apiClient.post('/api/lollms/generate', {
            prompt,
            max_new_tokens: 2048,
            temperature: 0.2
        }, {
            timeout: 300000 // 5 minutes timeout for selection assistant queries
        });
        aiResponse.value = res.data?.generated_text || 'No response generated.';
    } catch (e) {
        console.error("AI selection assistant error:", e);
        if (e.code === 'ECONNABORTED' || e.message?.includes('timeout')) {
            aiError.value = 'AI generation timed out. The model took too long to respond.';
        } else {
            aiError.value = e.response?.data?.detail || e.message || 'AI request failed.';
        }
    } finally {
        isGeneratingSelectionAi.value = false;
    }
}

function replaceSelectionWith(textToInsert) {
    if (!editorView.value || !savedSelectionRange.value) return;
    const { from, to } = savedSelectionRange.value;
    editorView.value.dispatch({
        changes: { from, to, insert: textToInsert },
        selection: { anchor: from + textToInsert.length }
    });
    closeAiModal();
    uiStore.addNotification('Selection replaced with AI result.', 'success', 2500);
}

function insertBelowSelection(textToInsert) {
    if (!editorView.value || !savedSelectionRange.value) return;
    const { to } = savedSelectionRange.value;
    const text = '\n\n' + textToInsert;
    editorView.value.dispatch({
        changes: { from: to, insert: text },
        selection: { anchor: to + text.length }
    });
    closeAiModal();
    uiStore.addNotification('Inserted AI output below selection.', 'success', 2500);
}

async function copyAiResponse(textToCopy) {
    const success = await uiStore.copyToClipboard(textToCopy);
    if (success) {
        justCopiedResponse.value = true;
        setTimeout(() => justCopiedResponse.value = false, 2000);
    }
}

// Computed property for rendered content - Automatic language awareness
const renderedContent = computed(() => {
    const lang = props.language ? props.language.toLowerCase() : 'markdown';

    // If it's markdown, we return raw text (which might contain its own blocks)
    if (lang === 'markdown') return props.modelValue;

    // [FIX] For mermaid, ensure we wrap in fences so MessageContentRenderer identifies it
    if (lang === 'mermaid') return `\`\`\`mermaid\n${props.modelValue}\n\`\`\``;

    // If it's a specific language, we wrap it so the MessageContentRenderer treats it as a block
    // This allows the renderer to provide "Copy", "Run", or "SVG Preview" UI automatically.
    return `\`\`\`${lang}\n${props.modelValue}\n\`\`\``;
});

defineExpose({ editorView });

// --- MODE & WRAPPING ---
const setMode = (mode) => {
    if (['edit', 'view'].includes(mode)) currentMode.value = mode;
};

const toggleWrapping = () => {
    isWrappingEnabled.value = !isWrappingEnabled.value;
    if (editorView.value) {
        editorView.value.dispatch({
            effects: wrappingCompartment.reconfigure(isWrappingEnabled.value ? EditorView.lineWrapping : [])
        });
        editorView.value.focus();
    }
};

watch(currentMode, async (newMode) => {
    const canRender = props.renderable && props.allowedModes !== 'edit_only';
    
    if (newMode === 'view' && canRender) {
        isRendering.value = true;
        await nextTick();
        // Give the UI thread a moment to clear the editor before mounting the renderer
        await new Promise(resolve => setTimeout(resolve, 100));
        isRendering.value = false;
    }
    
    if (newMode === 'edit' && editorView.value) {
        nextTick(() => editorView.value.focus());
    }
});

watch(() => props.initialMode, (newMode) => {
    if (['edit', 'view'].includes(newMode)) currentMode.value = newMode;
});

// --- EDITOR LOGIC ---
const getLanguageExtension = () => {
    const lang = props.language ? props.language.toLowerCase() : '';
    switch (lang) {
        case 'html':
        case 'xml': return html();
        case 'python': return python();
        case 'javascript': return javascript();
        case 'mermaid': 
            // Mermaid source is essentially text/markdown with specific keywords
            return markdown({ base: markdownLanguage, codeLanguages: languages });
        default: return markdown({ base: markdownLanguage, codeLanguages: languages });
    }
};
const getSelectedLines = (state) => {
    let lines = [];
    for (let range of state.selection.ranges) {
        const fromLine = state.doc.lineAt(range.from);
        const toLine = state.doc.lineAt(range.to);
        for (let i = fromLine.number; i <= toLine.number; i++) {
            if (!lines.some(l => l.number === i)) lines.push(state.doc.line(i));
        }
    }
    return lines;
};

const needsNewline = (state, pos, isBefore) => {
    if ((isBefore && pos === 0) || (!isBefore && pos === state.doc.length)) return false;
    const surroundingChar = isBefore ? state.doc.sliceString(pos - 1, pos) : state.doc.sliceString(pos, pos + 1);
    return surroundingChar !== '\n';
};

const handleFormat = (type, options = {}) => {
    if (!editorView.value) return;
    const view = editorView.value;
    const state = view.state;
    let changes = [];
    const selection = state.selection.main;
    const selectedText = state.doc.sliceString(selection.from, selection.to);
    
    if (type === 'insert') {
        const snippet = options.code || '';
        view.dispatch({
            changes: { from: selection.from, to: selection.to, insert: snippet },
            selection: { anchor: selection.from + snippet.length }
        });
        view.focus();
        return;
    }

    if (type === 'codeblock') {
        const lang = options.language || '';
        const startTag = '```' + lang + '\n';
        const endTag = '\n```';
        
        let textToInsert;
        let selectionStart, selectionEnd;

        if (selectedText) {
            textToInsert = startTag + selectedText + endTag;
            selectionStart = selection.from;
            selectionEnd = selection.from + textToInsert.length;
        } else {
            const placeholder = 'code here';
            textToInsert = startTag + placeholder + endTag;
            selectionStart = selection.from + startTag.length;
            selectionEnd = selectionStart + placeholder.length;
        }
        
        let finalInsertion = textToInsert;
        if (needsNewline(state, selection.from, true) && selection.from > 0) {
            finalInsertion = '\n' + finalInsertion;
            selectionStart += 1;
            selectionEnd += 1;
        }
        if (needsNewline(state, selection.to, false) && selection.to < state.doc.length) {
            finalInsertion += '\n';
        }
        
        view.dispatch({
            changes: { from: selection.from, to: selection.to, insert: finalInsertion },
            selection: { anchor: selectionStart, head: selectionEnd }
        });
        view.focus();
        return;
    }

    let prefix = '', suffix = '', blockPrefix = '';
    let isBlockEnv = false;

    switch (type) {
        case 'bold': prefix = '**'; suffix = '**'; break;
        case 'italic': prefix = '_'; suffix = '_'; break;
        case 'strikethrough': prefix = '~~'; suffix = '~~'; break;
        case 'inlinecode': prefix = '`'; suffix = '`'; break;
        case 'latex': prefix = '$'; suffix = '$'; break;
        case 'h1': blockPrefix = '# '; break;
        case 'h2': blockPrefix = '## '; break;
        case 'h3': blockPrefix = '### '; break;
        case 'blockquote': blockPrefix = '> '; break;
        case 'ul': blockPrefix = '- '; break;
        case 'ol': blockPrefix = '1. '; break;
        case 'latexBlock': prefix = '$$\n'; suffix = '\n$$'; isBlockEnv = true; break;
        case 'hr': changes.push({ from: selection.from, insert: (needsNewline(state, selection.from, true) ? '\n' : '') + '---\n' }); break;
    }

    let effectivePrefix = prefix;
    let effectiveSuffix = suffix;

    if (isBlockEnv) {
        if (needsNewline(state, selection.from, true)) effectivePrefix = '\n' + prefix;
        if (needsNewline(state, selection.to, false)) effectiveSuffix = suffix + '\n';
    }

    if (blockPrefix) {
        const lines = getSelectedLines(state);
        lines.forEach(line => {
            const currentPrefixMatch = line.text.match(/^([#>\-\*]|\d+\.)\s*/);
            const prefixLen = currentPrefixMatch ? currentPrefixMatch[0].length : 0;
            if (currentPrefixMatch && currentPrefixMatch[0].trim() === blockPrefix.trim()) {
                changes.push({ from: line.from, to: line.from + prefixLen, insert: '' });
            } else {
                changes.push({ from: line.from, to: line.from + prefixLen, insert: blockPrefix });
            }
        });
        if (changes.length > 0) view.dispatch({ changes });
    } else if (prefix || suffix) {
        const insert = effectivePrefix + selectedText + effectiveSuffix;
        view.dispatch({
            changes: { from: selection.from, to: selection.to, insert: insert },
            selection: { anchor: selection.from + effectivePrefix.length, head: selection.to + effectivePrefix.length }
        });
    } else if (type === 'hr' && changes.length > 0) {
        view.dispatch({ changes, selection: { anchor: selection.from + changes[0].insert.length } });
    }

    view.focus();
};

const handleInsertLink = () => {
    if (!editorView.value) return;
    const url = prompt("Enter link URL:", "https://");
    if (!url) return;

    const view = editorView.value, state = view.state, selection = state.selection.main;
    const selectedText = state.doc.sliceString(selection.from, selection.to);
    const linkText = selectedText || 'link text';
    const textToInsert = `[${linkText}](${url})`;

    view.dispatch({
        changes: { from: selection.from, to: selection.to, insert: textToInsert },
        selection: selection.empty
            ? { anchor: selection.from + 1, head: selection.from + 1 + linkText.length }
            : { anchor: selection.from + textToInsert.length }
    });
    view.focus();
};

const handleInsertImage = () => {
    if (!editorView.value) return;
    const url = prompt("Enter image URL:", "https://");
    if (!url) return;
    const altText = prompt("Enter alt text:", "image");

    const view = editorView.value, state = view.state, selection = state.selection.main;
    const textToInsert = `![${altText || ''}](${url})`;
    let effectiveInsert = textToInsert;
    if (needsNewline(state, selection.from, true)) effectiveInsert = '\n' + effectiveInsert;
    if (needsNewline(state, selection.to, false) || (selection.empty && needsNewline(state, selection.from, false))) effectiveInsert += '\n';

    view.dispatch({
        changes: { from: selection.from, to: selection.to, insert: effectiveInsert },
        selection: { anchor: selection.from + effectiveInsert.length }
    });
    view.focus();
};

const handleImport = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.md,.txt,text/markdown,text/plain';
    input.onchange = e => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = re => {
            const content = re.target.result;
            emit('update:modelValue', content);
        };
        reader.readAsText(file);
    };
    input.click();
};

const handleExport = (format) => discussionsStore.exportRawContent({ content: props.modelValue, format });

// --- LIFECYCLE ---
const initializeEditor = () => {
    if (editorView.value) {
        editorView.value.destroy();
        editorView.value = null;
    }

    const baseExtensions = [
        basicSetup,
        keymap.of([
            indentWithTab, 
            ...searchKeymap,
            {
                key: "Ctrl-Enter",
                mac: "Cmd-Enter",
                run: () => {
                    if (isRunnable.value) {
                        handleRunCode();
                        return true;
                    }
                    return false;
                }
            },
            {
                key: "Ctrl-k",
                mac: "Cmd-k",
                run: () => {
                    openSelectionAiModal();
                    return true;
                }
            }
        ]),
        search({
            top: true,
            caseSensitive: false,
            scrollToMatch: (range) => EditorView.scrollIntoView(range, { y: 'center', x: 'nearest' })
        }),
        getLanguageExtension(),
        wrappingCompartment.of(isWrappingEnabled.value ? EditorView.lineWrapping : []),
        readOnlyCompartment.of(props.readOnly ? [EditorState.readOnly.of(true), EditorView.editable.of(false)] : []),
        tokenField,
        EditorView.theme({
            "&": { height: "100%" },
            ".cm-scroller": { overflow: "auto", height: "100%" }
        }),
        EditorView.updateListener.of((update) => {
            if (update.docChanged && !updatingFromSelf) {
                const newContent = update.state.doc.toString();
                emit('update:modelValue', newContent);
                renderMinimap();
            }
            if (update.selectionSet || update.docChanged) {
                updateSelectionState();
                updateMinimapViewport();
            }
            if (update.geometryChanged) {
                updateMinimapViewport();
            }
        }),
        EditorView.contentAttributes.of({ 'aria-label': 'Markdown editor content' })
    ];

    if (props.placeholder) {
        baseExtensions.push(cmPlaceholder(props.placeholder));
    }

    if (props.isChatMode) {
        baseExtensions.push(keymap.of([
            {
                key: "Enter",
                run: (view) => {
                    emit('submit');
                    return true;
                }
            },
            {
                key: "Shift-Enter",
                run: insertNewline
            }
        ]));
    }

    if (props.theme) {
        baseExtensions.push(props.theme);
    }
    
    const finalExtensions = [...baseExtensions, ...props.extensions];

    // Only set initial doc if it's not undefined/null
    const initialDoc = props.modelValue ?? '';
    
    const state = EditorState.create({
        doc: initialDoc,
        extensions: finalExtensions,
    });
    
    // Assign to .value
    editorView.value = new EditorView({ state, parent: editorRef.value });

    // Attach scroll listener for synchronous minimap updates
    editorView.value.scrollDOM.addEventListener('scroll', updateMinimapViewport, { passive: true });

    if (props.autofocus) {
        nextTick(() => {
            editorView.value?.focus();
        });
    }

    nextTick(() => {
        renderMinimap();
    });

    emit('ready', { view: editorView.value, state: editorView.value.state });
};

watch(() => props.readOnly, (isReadOnly) => {
    if (editorView.value) {
        editorView.value.dispatch({
            effects: readOnlyCompartment.reconfigure(isReadOnly ? [EditorState.readOnly.of(true), EditorView.editable.of(false)] : [])
        });
    }
});

// More selective sync: only update if content actually differs AND we're not currently editing
watch(() => props.modelValue, (newValue) => {
    // Skip if editor destroyed or value matches current content
    if (!editorView.value) return;
    
    const currentContent = editorView.value.state.doc.toString();
    const safeNewValue = newValue ?? '';
    
    // Only sync if external value differs from editor content
    if (safeNewValue !== currentContent) {
        updatingFromSelf = true;
        editorView.value.dispatch({
            changes: { from: 0, to: editorView.value.state.doc.length, insert: safeNewValue }
        });
        updatingFromSelf = false;
    }

    if (showTokens.value) {
        clearTimeout(tokenizeDebounceTimer);
        tokenizeDebounceTimer = setTimeout(() => {
            if (showTokens.value) updateTokenBreakdown();
        }, 400);
    }
}, { flush: 'sync' });

watch(() => props.theme, initializeEditor);
watch(() => props.language, initializeEditor);
onMounted(() => {
    initializeEditor();
    if (window.ResizeObserver) {
        minimapResizeObserver = new ResizeObserver(() => {
            renderMinimap();
        });
        if (editorRef.value) {
            minimapResizeObserver.observe(editorRef.value);
        }
    }
});
onBeforeUnmount(() => {
    if (editorView.value) {
        editorView.value.scrollDOM.removeEventListener('scroll', updateMinimapViewport);
        editorView.value.destroy();
        editorView.value = null;
    }
    if (minimapResizeObserver) {
        minimapResizeObserver.disconnect();
    }
});
</script>

<style scoped>
.editor-content-host :deep(.cm-editor) {
    height: 100%;
}
.editor-content-host :deep(.cm-scroller) {
    height: 100%;
    overflow: auto;
}

/* Floating AI Pill */
.floating-ai-pill {
    position: absolute;
    z-index: 40;
    pointer-events: auto;
    animation: fadeIn 0.15s ease-out;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
}

/* --- Token Visualizer Marks --- */
.editor-content-host :deep(.cm-token) {
    border-radius: 2px;
    margin: 0 0.5px;
    transition: background-color 0.15s ease, opacity 0.15s ease;
    cursor: default;
}
.editor-content-host :deep(.cm-token:hover) {
    outline: 1.5px solid currentColor;
    z-index: 5;
    position: relative;
}

/* 8 cycling pastel colors for token boundaries */
.editor-content-host :deep(.cm-token-0) { background-color: rgba(59, 130, 246, 0.28); color: #1d4ed8; }
.editor-content-host :deep(.cm-token-1) { background-color: rgba(16, 185, 129, 0.28); color: #047857; }
.editor-content-host :deep(.cm-token-2) { background-color: rgba(245, 158, 11, 0.28); color: #b45309; }
.editor-content-host :deep(.cm-token-3) { background-color: rgba(168, 85, 247, 0.28); color: #7e22ce; }
.editor-content-host :deep(.cm-token-4) { background-color: rgba(236, 72, 153, 0.28); color: #be185d; }
.editor-content-host :deep(.cm-token-5) { background-color: rgba(6, 182, 212, 0.28); color: #0e7490; }
.editor-content-host :deep(.cm-token-6) { background-color: rgba(249, 115, 22, 0.28); color: #c2410c; }
.editor-content-host :deep(.cm-token-7) { background-color: rgba(139, 92, 246, 0.28); color: #6d28d9; }

/* Dark mode token colors */
.dark .editor-content-host :deep(.cm-token-0) { background-color: rgba(59, 130, 246, 0.35); color: #93c5fd; }
.dark .editor-content-host :deep(.cm-token-1) { background-color: rgba(16, 185, 129, 0.35); color: #6ee7b7; }
.dark .editor-content-host :deep(.cm-token-2) { background-color: rgba(245, 158, 11, 0.35); color: #fcd34d; }
.dark .editor-content-host :deep(.cm-token-3) { background-color: rgba(168, 85, 247, 0.35); color: #d8b4fe; }
.dark .editor-content-host :deep(.cm-token-4) { background-color: rgba(236, 72, 153, 0.35); color: #f472b6; }
.dark .editor-content-host :deep(.cm-token-5) { background-color: rgba(6, 182, 212, 0.35); color: #67e8f9; }
.dark .editor-content-host :deep(.cm-token-6) { background-color: rgba(249, 115, 22, 0.35); color: #fdba74; }
.dark .editor-content-host :deep(.cm-token-7) { background-color: rgba(139, 92, 246, 0.35); color: #c4b5fd; }
</style>
