<!-- [UPDATE] frontend/webui/src/views/ImageStudioView.vue -->
<template>
    <!-- 1. Header Title Portal: Studio Status, Album & Selection Toggle -->
    <Teleport to="#global-header-title-target">
        <div class="flex items-center gap-2 sm:gap-3 pointer-events-auto bg-gray-100/80 dark:bg-gray-800/80 px-3 py-1.5 rounded-xl border dark:border-gray-700/50 backdrop-blur-md max-w-[220px] sm:max-w-md transition-all shadow-inner">
            <div class="flex items-center gap-2 min-w-0">
                <input 
                    type="checkbox" 
                    v-model="areAllSelected" 
                    class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer shrink-0" 
                    title="Select / Deselect All in View" 
                />
                <div class="flex flex-col min-w-0">
                    <span class="text-[9px] font-black uppercase tracking-widest text-primary leading-none">Studio Gallery</span>
                    <h2 class="font-bold text-gray-800 dark:text-gray-200 text-xs truncate">
                        {{ currentAlbumName }}
                    </h2>
                </div>
                <span class="text-[10px] font-mono font-bold text-gray-500 bg-gray-200 dark:bg-gray-700 px-2 py-0.5 rounded-md hidden sm:inline-block">
                    {{ filteredImages.length }}
                </span>
            </div>
        </div>
    </Teleport>

    <!-- 2. Header Actions Portal: Tools, Batch Drawer & Execution -->
    <Teleport to="#global-header-actions-target">
        <div class="flex items-center gap-1 sm:gap-2 pointer-events-auto">
            <!-- Selection Mode Active Banner -->
            <div v-if="isSelectionMode" class="flex items-center gap-1 bg-blue-50 dark:bg-blue-900/30 px-3 py-1 rounded-xl border border-blue-200 dark:border-blue-800 mr-2 animate-in fade-in slide-in-from-right-4 shadow-sm">
                <span class="text-[10px] font-black text-blue-700 dark:text-blue-300 uppercase tracking-wider mr-2 hidden sm:inline">
                    {{ selectedImages.length }} Selected
                </span>

                <button @click="handleBatchZipDownload" class="btn-icon p-1.5 text-blue-600 hover:bg-blue-100 dark:hover:bg-blue-800/50" title="Download Selected as ZIP">
                    <IconArrowDownTray class="w-4 h-4" />
                </button>
                <button @click="handleMoveToDiscussion" class="btn-icon p-1.5 text-blue-600 hover:bg-blue-100 dark:hover:bg-blue-800/50" title="Send to Chat Workspace">
                    <IconSend class="w-4 h-4" />
                </button>
                <button @click="handleMoveToAlbum" class="btn-icon p-1.5 text-purple-600 hover:bg-purple-100 dark:hover:bg-purple-800/50" title="Move to Album">
                    <IconFolder class="w-4 h-4" />
                </button>
                <button v-if="selectedImages.length === 2" @click="openCompareModal" class="btn-icon p-1.5 text-emerald-600 hover:bg-emerald-100 dark:hover:bg-emerald-800/50" title="Compare Side-by-Side">
                    <IconArrowsUpDown class="w-4 h-4 rotate-90" />
                </button>
                <button @click="handleDeleteSelected" class="btn-icon p-1.5 text-red-500 hover:bg-red-100 dark:hover:bg-red-900/50" title="Delete Selected">
                    <IconTrash class="w-4 h-4" />
                </button>

                <div class="h-4 w-px bg-blue-200 dark:bg-blue-800 mx-1"></div>
            </div>

            <!-- Standard Quick Actions -->
            <div v-else class="flex items-center gap-1 mr-1">
                <button @click="handleRefresh" class="btn-icon p-1.5 text-gray-500 hover:text-blue-600" title="Refresh Gallery">
                    <IconRefresh class="w-4.5 h-4.5" :class="{'animate-spin': isLoading}" />
                </button>
                <label class="btn-icon p-1.5 text-gray-500 hover:text-blue-600 cursor-pointer" title="Upload Image File(s)">
                    <IconArrowUpTray class="w-4.5 h-4.5" />
                    <input type="file" @change="handleUpload" class="hidden" accept="image/*" multiple>
                </label>
                <button @click="openCameraModal" class="btn-icon p-1.5 text-gray-500 hover:text-blue-600" title="Capture from Webcam">
                    <IconCamera class="w-4.5 h-4.5" />
                </button>
                <button @click="handleNewBlankImage" class="btn-icon p-1.5 text-gray-500 hover:text-blue-600" title="Open Layer Canvas Studio">
                    <IconPlus class="w-4.5 h-4.5" />
                </button>
            </div>

            <!-- Primary Generate Button -->
            <button @click="handleGenerateOrApply" class="btn btn-primary whitespace-nowrap shadow-lg shadow-blue-500/20 px-4 py-2 font-bold flex items-center gap-2" :disabled="isGenerating || isAnyEnhancing">
                <IconAnimateSpin v-if="isGenerating" class="w-4 h-4 animate-spin" />
                <IconSparkles v-else class="w-4 h-4" />
                <span class="hidden sm:inline">{{ isSelectionMode ? 'Apply Edit' : 'Generate' }}</span>
            </button>

            <!-- Mobile Settings Drawer Button -->
            <button @click="showMobileSidebar = !showMobileSidebar" class="lg:hidden btn btn-secondary p-2 ml-1" title="Studio Controls">
                <IconAdjustmentsHorizontal class="w-5 h-5" />
            </button>
        </div>
    </Teleport>

    <div 
        class="h-full flex flex-col bg-gray-50 dark:bg-gray-950 overflow-hidden relative selection:bg-blue-500 selection:text-white" 
        @dragover.prevent="handleDragOver"
        @dragleave.prevent="handleDragLeave"
        @drop.prevent="handleDrop"
    >
        <!-- Drag and drop ingestion overlay -->
        <div v-if="isDraggingOver" class="absolute inset-0 bg-blue-500/20 backdrop-blur-sm border-4 border-dashed border-blue-500 rounded-3xl z-50 flex flex-col items-center justify-center m-6 pointer-events-none animate-in fade-in zoom-in-95">
            <IconPhoto class="w-16 h-16 text-blue-600 mb-2 animate-bounce" />
            <p class="text-2xl font-black uppercase tracking-widest text-blue-600">Drop Images to Ingest</p>
            <p class="text-xs text-blue-500 font-bold uppercase mt-1">Automatic placement in current album</p>
        </div>

        <div class="grow min-h-0 flex relative overflow-hidden">
            <!-- ── LEFT CONTROL DOCK (STUDIO WORKSTATION) ── -->
            <aside 
                class="absolute inset-y-0 left-0 z-30 bg-white dark:bg-gray-900 border-r dark:border-gray-800 transform transition-transform duration-300 ease-in-out lg:relative lg:translate-x-0 flex flex-col shrink-0 shadow-2xl"
                :class="showMobileSidebar ? 'translate-x-0' : '-translate-x-full'"
                :style="sidebarStyle"
            >
                <!-- Resizer Handle -->
                <div 
                    @mousedown.prevent="startResizing"
                    class="hidden lg:block absolute top-0 right-0 bottom-0 w-1.5 cursor-col-resize z-50 hover:bg-blue-500 transition-colors"
                ></div>

                <!-- Dock Navigation Header -->
                <div class="p-3 border-b dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50 flex items-center justify-between">
                    <div class="flex items-center gap-1 bg-gray-200/60 dark:bg-gray-800 p-1 rounded-xl w-full">
                        <button 
                            @click="activeDockTab = 'prompt'" 
                            class="flex-1 py-1.5 text-[10px] font-black uppercase tracking-wider rounded-lg transition-all"
                            :class="activeDockTab === 'prompt' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                        >
                            Prompt & Styles
                        </button>
                        <button 
                            @click="activeDockTab = 'parameters'" 
                            class="flex-1 py-1.5 text-[10px] font-black uppercase tracking-wider rounded-lg transition-all"
                            :class="activeDockTab === 'parameters' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                        >
                            Parameters
                        </button>
                    </div>

                    <button @click="showMobileSidebar = false" class="lg:hidden p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg ml-2">
                        <IconXMark class="w-5 h-5 text-gray-500" />
                    </button>
                </div>

                <!-- Dock Body -->
                <div class="grow p-4 space-y-5 overflow-y-auto custom-scrollbar">

                    <!-- TAB 1: PROMPT & STYLE PRESETS -->
                    <div v-show="activeDockTab === 'prompt'" class="space-y-4">
                        <!-- Positive Prompt Area -->
                        <div class="space-y-1.5">
                            <div class="flex justify-between items-center">
                                <label for="prompt" class="text-[10px] font-black uppercase tracking-widest text-gray-400">
                                    Positive Prompt
                                </label>
                                <div class="flex items-center gap-1">
                                    <button @click="clearPrompt" class="text-[9px] font-bold text-gray-400 hover:text-red-500 px-1.5 py-0.5 rounded transition-colors uppercase">
                                        Clear
                                    </button>
                                    <button @click="openEnhanceModal('prompt')" class="btn-icon p-1 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30" :disabled="isAnyEnhancing" title="AI Enhance Prompt">
                                        <IconSparkles class="w-4 h-4" />
                                    </button>
                                </div>
                            </div>
                            <div class="relative">
                                <textarea 
                                    id="prompt" 
                                    v-model="prompt" 
                                    rows="4" 
                                    class="input-field w-full resize-none !text-sm leading-relaxed" 
                                    :disabled="isEnhancingPrompt" 
                                    placeholder="Describe your subject, scene, mood, details, and environment..."
                                ></textarea>
                                <div v-if="isEnhancingPrompt" class="absolute inset-0 flex flex-col items-center justify-center bg-white/60 dark:bg-black/60 backdrop-blur-sm rounded-xl animate-in fade-in">
                                    <IconAnimateSpin class="w-6 h-6 text-blue-500 animate-spin mb-1" />
                                    <span class="text-[10px] font-black uppercase tracking-widest text-blue-600">AI Prompt Engineer...</span>
                                </div>
                            </div>
                        </div>

                        <!-- Negative Prompt Library Quick Tags -->
                        <div class="space-y-1.5">
                            <div class="flex justify-between items-center">
                                <label for="negative-prompt" class="text-[10px] font-black uppercase tracking-widest text-gray-400">
                                    Negative Filter (Avoid)
                                </label>
                                <button @click="openEnhanceModal('negative_prompt')" class="btn-icon p-1 text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30" :disabled="isAnyEnhancing" title="AI Enhance Negative">
                                    <IconSparkles class="w-4 h-4" />
                                </button>
                            </div>
                            <textarea 
                                id="negative-prompt" 
                                v-model="negativePrompt" 
                                rows="2" 
                                class="input-field w-full resize-none !text-xs opacity-85" 
                                placeholder="e.g., blurry, mutated hands, distorted, artifacts..."
                            ></textarea>

                            <div class="flex items-center gap-1 overflow-x-auto no-scrollbar py-1">
                                <button 
                                    v-for="negTag in quickNegativePresets" 
                                    :key="negTag.label"
                                    @click="appendNegative(negTag.value)"
                                    class="px-2 py-0.5 rounded-full text-[9px] font-bold bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 whitespace-nowrap transition-colors"
                                >
                                    + {{ negTag.label }}
                                </button>
                            </div>
                        </div>

                        <!-- Categorized Style Library -->
                        <div class="space-y-3 pt-2">
                            <span class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Style Presets</span>

                            <div v-for="(group, category) in styleLibrary" :key="category" class="rounded-xl border dark:border-gray-800 overflow-hidden bg-gray-50/50 dark:bg-gray-900/30">
                                <button 
                                    @click="collapsedStyles[category] = !collapsedStyles[category]" 
                                    class="w-full flex items-center justify-between p-2.5 hover:bg-gray-100/50 dark:hover:bg-gray-800/50 transition-colors select-none"
                                >
                                    <span class="text-[10px] font-black text-gray-600 dark:text-gray-300 uppercase tracking-widest">{{ category }}</span>
                                    <IconChevronUp class="w-3.5 h-3.5 text-gray-400 transition-transform" :class="{'rotate-180': collapsedStyles[category]}" />
                                </button>

                                <div v-show="!collapsedStyles[category]" class="p-2 grid grid-cols-3 gap-1.5 border-t dark:border-gray-800 animate-in fade-in">
                                    <button 
                                        v-for="style in group" 
                                        :key="style.name" 
                                        @click="applyStyle(style)"
                                        class="flex flex-col items-center p-2 rounded-xl border transition-all hover:scale-102"
                                        :class="selectedStyle === style.name ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 ring-1 ring-blue-500' : 'border-gray-200 dark:border-gray-700/50 bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300'"
                                        :title="style.prompt"
                                    >
                                        <span class="text-xl mb-1">{{ style.emoji }}</span>
                                        <span class="text-[9px] font-bold truncate w-full text-center uppercase tracking-tight">{{ style.name }}</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- TAB 2: GENERATION PARAMETERS & RATIOS -->
                    <div v-show="activeDockTab === 'parameters'" class="space-y-5 animate-in fade-in">
                        <!-- Aspect Ratios -->
                        <div class="space-y-2">
                            <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">
                                Aspect Ratio & Orientation
                            </label>
                            <div class="grid grid-cols-3 gap-2">
                                <button 
                                    v-for="ratio in aspectRatios" 
                                    :key="ratio.name"
                                    @click="imageSize = ratio.value"
                                    class="p-2.5 rounded-2xl border flex flex-col items-center justify-center transition-all"
                                    :class="imageSize === ratio.value ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 shadow-sm ring-1 ring-blue-500' : 'border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-800 text-gray-500 hover:border-gray-300'"
                                >
                                    <div class="border-2 border-current rounded-md mb-1.5" :style="ratio.style"></div>
                                    <span class="text-[10px] font-black uppercase">{{ ratio.name }}</span>
                                    <span class="text-[8px] opacity-60 font-mono">{{ ratio.value }}</span>
                                </button>
                            </div>
                        </div>

                        <!-- Generation Count & Seed -->
                        <div class="grid grid-cols-2 gap-3 pt-2 border-t dark:border-gray-800">
                            <div>
                                <label class="label text-[10px] font-black text-gray-400 uppercase tracking-widest">Images (n)</label>
                                <div class="flex items-center gap-1 mt-1">
                                    <button 
                                        v-for="num in [1, 2, 4]" 
                                        :key="num"
                                        @click="nImages = num"
                                        class="flex-1 py-1.5 text-xs font-bold rounded-xl border transition-all"
                                        :class="nImages === num ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600' : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-500'"
                                    >
                                        {{ num }}
                                    </button>
                                </div>
                            </div>

                            <div>
                                <div class="flex justify-between items-center">
                                    <label class="label text-[10px] font-black text-gray-400 uppercase tracking-widest">Seed</label>
                                    <button @click="seed = -1" class="text-[8px] font-bold text-blue-500 uppercase hover:underline">Random</button>
                                </div>
                                <input 
                                    v-model.number="seed" 
                                    type="number" 
                                    class="input-field mt-1 !text-xs font-mono" 
                                    placeholder="-1"
                                />
                            </div>
                        </div>

                        <!-- Dynamic Model Config Parameters -->
                        <div v-if="modelConfigurableParameters.length > 0" class="pt-3 border-t dark:border-gray-800 space-y-3">
                            <span class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Model Advanced Settings</span>

                            <div v-for="param in modelConfigurableParameters" :key="param.name" class="space-y-1">
                                <label class="text-xs font-bold text-gray-600 dark:text-gray-300">{{ param.name.replace(/_/g, ' ') }}</label>
                                <input 
                                    v-if="['int', 'float'].includes(param.type)"
                                    type="number" 
                                    v-model.number="generationParams[param.name]" 
                                    :step="param.type === 'float' ? '0.1' : '1'"
                                    class="input-field w-full text-xs font-mono"
                                />
                                <select 
                                    v-else-if="param.options && param.options.length > 0" 
                                    v-model="generationParams[param.name]"
                                    class="input-field w-full text-xs"
                                >
                                    <option v-for="opt in param.options" :key="opt" :value="opt">{{ opt }}</option>
                                </select>
                                <input 
                                    v-else 
                                    type="text" 
                                    v-model="generationParams[param.name]" 
                                    class="input-field w-full text-xs"
                                />
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Dock Footer: Action Trigger -->
                <div class="p-4 border-t dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50">
                    <button 
                        @click="handleGenerateOrApply" 
                        class="btn btn-primary w-full py-3 text-xs font-black uppercase tracking-widest shadow-xl shadow-blue-500/20 flex items-center justify-center gap-2"
                        :disabled="isGenerating || isAnyEnhancing"
                    >
                        <IconAnimateSpin v-if="isGenerating" class="w-4 h-4 animate-spin" />
                        <IconSparkles v-else class="w-4 h-4" />
                        <span>{{ isSelectionMode ? `Apply Edit to (${selectedImages.length})` : 'Start Generation' }}</span>
                    </button>
                </div>
            </aside>

            <!-- Backdrop for mobile drawer -->
            <div v-if="showMobileSidebar" @click="showMobileSidebar = false" class="absolute inset-0 bg-black/40 z-20 lg:hidden backdrop-blur-sm"></div>

            <!-- ── MAIN GALLERY VIEWPORT ── -->
            <main class="grow flex flex-col min-w-0 h-full relative overflow-hidden">

                <!-- Filter & Navigation Bar -->
                <div class="p-3 bg-white/70 dark:bg-gray-900/70 backdrop-blur-md border-b dark:border-gray-800 flex flex-wrap items-center justify-between gap-3 shrink-0">
                    <div class="relative grow max-w-sm">
                        <input 
                            type="text" 
                            v-model="searchQuery" 
                            @input="onSearchInput"
                            placeholder="Filter creations by prompt keywords..." 
                            class="input-field !py-1.5 !pl-8 !text-xs w-full"
                        />
                        <IconMagnifyingGlass class="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                        <button v-if="searchQuery" @click="clearSearch" class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-red-500">
                            <IconXMark class="w-3.5 h-3.5" />
                        </button>
                    </div>

                    <div class="flex items-center gap-2">
                        <!-- Quick Orientation Filter -->
                        <select v-model="filterOrientation" class="input-field !py-1.5 !text-xs font-medium border dark:border-gray-700 bg-transparent cursor-pointer">
                            <option value="all">All Sizes</option>
                            <option value="square">Square (1:1)</option>
                            <option value="landscape">Landscape (Wide)</option>
                            <option value="portrait">Portrait (Tall)</option>
                        </select>

                        <!-- Thumbnail Resolution Toggle -->
                        <button 
                            @click="useFullResThumbnails = !useFullResThumbnails" 
                            class="px-2.5 py-1 text-[10px] font-bold rounded-lg border dark:border-gray-700 transition-colors"
                            :class="useFullResThumbnails ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30' : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'"
                            title="Toggle between fast compressed thumbnails and full resolution"
                        >
                            {{ useFullResThumbnails ? 'Full HD Quality' : '⚡ Fast Mode' }}
                        </button>
                    </div>
                </div>

                <!-- Gallery Stream -->
                <div class="grow overflow-y-auto p-4 sm:p-6 custom-scrollbar flex flex-col justify-between">

                    <div>
                        <!-- SPECIAL STAGED SELECTION SHELF WITH REORDERING -->
                        <transition
                            enter-active-class="transition ease-out duration-300"
                            enter-from-class="opacity-0 -translate-y-4"
                            enter-to-class="opacity-100 translate-y-0"
                            leave-active-class="transition ease-in duration-200"
                            leave-from-class="opacity-100 translate-y-0"
                            leave-to-class="opacity-0 -translate-y-4"
                        >
                            <div v-if="selectedImages.length > 0" class="sticky top-0 z-20 mb-6 bg-white/95 dark:bg-gray-900/95 backdrop-blur-xl rounded-2xl border border-blue-500/30 shadow-2xl p-4 space-y-3">
                                <div class="flex justify-between items-center">
                                    <div class="flex items-center gap-2">
                                        <span class="w-2 h-2 rounded-full bg-blue-500 animate-ping"></span>
                                        <h3 class="text-xs font-black uppercase tracking-widest text-gray-800 dark:text-gray-200">
                                            Staged for Processing ({{ selectedImages.length }})
                                        </h3>
                                        <span class="text-[10px] text-gray-400 font-medium italic hidden md:inline">
                                            (Drag items or use arrows to change sequence order)
                                        </span>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        <button @click="handleBatchZipDownload" class="btn btn-secondary btn-xs flex items-center gap-1.5">
                                            <IconArrowDownTray class="w-3.5 h-3.5" />
                                            <span>Download ZIP</span>
                                        </button>
                                        <button @click="selectedImages = []" class="text-[10px] font-bold text-red-500 hover:underline uppercase">
                                            Deselect All
                                        </button>
                                    </div>
                                </div>

                                <!-- Draggable Staged Carousel -->
                                <div class="flex gap-3 overflow-x-auto custom-scrollbar p-1 items-center">
                                    <div 
                                        v-for="(img, idx) in selectedImageObjects" 
                                        :key="'staged-'+img.id" 
                                        draggable="true"
                                        @dragstart="onStagedDragStart(idx, $event)"
                                        @dragover="onStagedDragOver(idx, $event)"
                                        @drop="onStagedDrop(idx, $event)"
                                        @dragend="onStagedDragEnd"
                                        class="relative w-24 h-24 shrink-0 group rounded-2xl overflow-hidden border-2 transition-all duration-200 shadow-md cursor-grab active:cursor-grabbing select-none"
                                        :class="[
                                            dragOverStagedIndex === idx ? 'border-amber-500 scale-105 ring-4 ring-amber-500/20' : 'border-blue-500 hover:border-blue-400',
                                            draggedStagedIndex === idx ? 'opacity-40' : ''
                                        ]"
                                    >
                                         <AuthenticatedImage :src="`/api/image-studio/${img.id}/thumbnail?size=256`" class="w-full h-full object-cover pointer-events-none" />

                                         <!-- Order Tag Badge -->
                                         <div class="absolute top-1.5 left-1.5 bg-blue-600 text-white font-mono text-[10px] font-black px-1.5 py-0.5 rounded-lg shadow-lg border border-white/20">
                                             #{{ idx + 1 }}
                                         </div>

                                         <!-- Shift Left / Right Controls -->
                                         <div class="absolute top-1.5 right-1.5 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                             <button 
                                                v-if="idx > 0" 
                                                @click.stop="moveStagedItem(idx, -1)" 
                                                class="w-5 h-5 rounded-md bg-black/70 hover:bg-blue-600 text-white text-[10px] flex items-center justify-center backdrop-blur transition-all active:scale-90" 
                                                title="Move Left"
                                             >
                                                 ◀
                                             </button>
                                             <button 
                                                v-if="idx < selectedImages.length - 1" 
                                                @click.stop="moveStagedItem(idx, 1)" 
                                                class="w-5 h-5 rounded-md bg-black/70 hover:bg-blue-600 text-white text-[10px] flex items-center justify-center backdrop-blur transition-all active:scale-90" 
                                                title="Move Right"
                                             >
                                                 ▶
                                             </button>
                                         </div>

                                         <!-- Remove Action Overlay -->
                                         <div 
                                            @click.stop="toggleSelection(img.id)"
                                            class="absolute inset-x-0 bottom-0 py-1 bg-red-600/90 text-white text-[9px] font-black uppercase text-center tracking-wider opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer backdrop-blur-sm"
                                            title="Click to remove from staged processing"
                                         >
                                             Remove
                                         </div>
                                    </div>
                                </div>
                            </div>
                        </transition>

                        <!-- Active Background Progress Cards -->
                        <div v-if="imageGenerationTasksCount > 0" class="mb-8 grid grid-cols-1 xs:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-6 animate-in fade-in zoom-in-95">
                             <div v-for="task in imageGenerationTasks" :key="task.id" class="relative aspect-square rounded-[2rem] bg-white dark:bg-gray-900 border border-blue-200 dark:border-blue-900/50 shadow-xl flex flex-col items-center justify-center p-6 overflow-hidden">
                                <div class="absolute inset-0 bg-blue-500/5 animate-pulse"></div>
                                <IconAnimateSpin class="w-10 h-10 text-blue-500 mb-4 animate-spin" />
                                <p class="text-xs font-black text-blue-600 dark:text-blue-400 uppercase tracking-widest">{{ task.progress }}% IN PROGRESS</p>
                                <p class="text-[10px] text-gray-400 text-center truncate max-w-full px-4 mt-1">{{ task.description }}</p>
                                <div class="absolute bottom-0 left-0 right-0 h-1.5 bg-gray-100 dark:bg-gray-800">
                                    <div class="h-full bg-gradient-to-r from-blue-500 to-indigo-600 transition-all duration-500" :style="{ width: `${task.progress}%` }"></div>
                                </div>
                            </div>
                        </div>

                        <!-- Loading / Empty States -->
                        <div v-if="isLoading && images.length === 0" class="h-96 flex flex-col items-center justify-center opacity-50">
                            <IconAnimateSpin class="w-12 h-12 mb-4 text-blue-500 animate-spin" />
                            <p class="text-xs font-black uppercase tracking-widest text-gray-400">Loading Thumbnails...</p>
                        </div>

                        <div v-else-if="filteredImages.length === 0 && imageGenerationTasksCount === 0" class="h-96 flex flex-col items-center justify-center text-gray-400">
                            <IconPhoto class="w-20 h-20 mb-4 opacity-20" />
                            <p class="text-base font-black uppercase tracking-widest text-gray-500">No creations found</p>
                            <p class="text-xs text-gray-400 mt-1">{{ searchQuery ? 'Try adjusting your search terms' : 'Type a prompt and start generating' }}</p>
                        </div>

                        <!-- Gallery Grid with Fast Cached Thumbnails & Order Numbers -->
                        <div v-else class="grid grid-cols-1 xs:grid-cols-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-6 pb-12">
                            <div 
                                v-for="(image, index) in filteredImages" 
                                :key="image.id" 
                                @click="toggleSelection(image.id)" 
                                class="relative aspect-square rounded-3xl overflow-hidden group cursor-pointer border-2 transition-all duration-300 bg-white dark:bg-gray-900 shadow-md hover:shadow-2xl" 
                                :class="isSelected(image.id) ? 'border-blue-500 ring-4 ring-blue-500/20 scale-[0.98]' : 'border-transparent hover:border-gray-200 dark:hover:border-gray-700'"
                            >
                                <!-- Fast Thumbnail URL (fallback to full-res only if toggled) -->
                                <AuthenticatedImage 
                                    :src="useFullResThumbnails ? `/api/image-studio/${image.id}/file` : `/api/image-studio/${image.id}/thumbnail?size=384`" 
                                    class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" 
                                />

                                <!-- Selection Badge + Synchronized Stage Order Indicator -->
                                <div class="absolute top-3 left-3 z-10 flex items-center gap-1.5">
                                    <div class="w-6 h-6 rounded-full border-2 border-white dark:border-gray-800 bg-white/80 dark:bg-gray-900/80 backdrop-blur flex items-center justify-center shadow-lg transition-opacity duration-200" :class="isSelected(image.id) ? '!bg-blue-600 !border-blue-600 opacity-100' : 'opacity-0 group-hover:opacity-100'">
                                        <IconCheckCircle v-if="isSelected(image.id)" class="w-4 h-4 text-white" />
                                    </div>
                                    <span 
                                        v-if="isSelected(image.id)" 
                                        class="px-2 py-0.5 rounded-md bg-blue-600 text-[10px] font-mono font-black text-white shadow-lg border border-white/20 animate-in fade-in"
                                    >
                                        #{{ getSelectionIndex(image.id) }}
                                    </span>
                                    <span 
                                        v-else 
                                        class="px-2 py-0.5 rounded-md bg-black/60 backdrop-blur text-[9px] font-mono font-bold text-white shadow"
                                    >
                                        #{{ (currentPage - 1) * pageSize + index + 1 }}
                                    </span>
                                </div>

                                <!-- Resolution Pill -->
                                <div class="absolute top-3 right-3 z-10 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                                    <span class="px-2 py-1 rounded-full bg-black/60 backdrop-blur-md text-[9px] font-mono text-white font-bold shadow-lg">
                                        {{ image.width }}×{{ image.height }}
                                    </span>
                                </div>

                                <!-- Editorial Hover Action Overlay -->
                                <div class="absolute inset-0 bg-gradient-to-t from-black/95 via-black/40 to-transparent flex flex-col justify-end p-4 transition-opacity duration-300 opacity-0 group-hover:opacity-100" :class="{'!opacity-100': isSelected(image.id)}">
                                    <p class="text-white text-xs font-medium line-clamp-2 drop-shadow-md mb-3 opacity-90 leading-relaxed font-serif italic">
                                        "{{ image.prompt || 'No description recorded' }}"
                                    </p>

                                    <div class="flex items-center justify-between pt-3 border-t border-white/15">
                                        <div class="flex items-center gap-1">
                                            <button @click.stop="copyPrompt(image.prompt)" class="p-2 bg-white/10 hover:bg-white/30 rounded-xl text-white backdrop-blur-md transition-all active:scale-95" title="Copy Prompt Text">
                                                <IconCopy class="w-4 h-4" />
                                            </button>
                                            <button @click.stop="reusePrompt(image)" class="p-2 bg-white/10 hover:bg-blue-500 rounded-xl text-white backdrop-blur-md transition-all active:scale-95" title="Reuse Settings in Studio">
                                                <IconRefresh class="w-4 h-4" />
                                            </button>
                                            <button @click.stop="openInpaintingEditor(image)" class="p-2 bg-white/10 hover:bg-purple-500 rounded-xl text-white backdrop-blur-md transition-all active:scale-95" title="Open Layer Canvas Studio">
                                                <IconPencil class="w-4 h-4" />
                                            </button>
                                        </div>

                                        <div class="flex items-center gap-1">
                                            <button @click.stop="downloadSingle(image)" class="p-2 bg-white/10 hover:bg-emerald-500 rounded-xl text-white backdrop-blur-md transition-all active:scale-95" title="Download Image File">
                                                <IconArrowDownTray class="w-4 h-4" />
                                            </button>
                                            <button @click.stop="openImageViewer(image, index)" class="p-2 bg-white/10 hover:bg-white/30 rounded-xl text-white backdrop-blur-md transition-all active:scale-95" title="Fullscreen Lightbox (Navigable)">
                                                <IconMaximize class="w-4 h-4" />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- ── PAGINATION CONTROLS ── -->
                    <div v-if="totalPages > 1" class="pt-6 pb-12 border-t dark:border-gray-800 flex flex-col sm:flex-row items-center justify-between gap-4">
                        <span class="text-xs font-mono text-gray-500 dark:text-gray-400">
                            Showing {{ (currentPage - 1) * pageSize + 1 }}–{{ Math.min(currentPage * pageSize, totalImages) }} of {{ totalImages }} creations
                        </span>

                        <div class="flex items-center gap-1.5">
                            <button 
                                @click="goToPage(currentPage - 1)" 
                                :disabled="currentPage <= 1"
                                class="px-3 py-1.5 rounded-xl border dark:border-gray-700 text-xs font-bold disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                            >
                                Previous
                            </button>

                            <div class="flex items-center gap-1">
                                <button 
                                    v-for="p in visiblePageNumbers" 
                                    :key="p"
                                    @click="goToPage(p)"
                                    class="w-8 h-8 rounded-xl text-xs font-mono font-bold flex items-center justify-center transition-all"
                                    :class="currentPage === p ? 'bg-blue-600 text-white shadow-md' : 'hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400'"
                                >
                                    {{ p }}
                                </button>
                            </div>

                            <button 
                                @click="goToPage(currentPage + 1)" 
                                :disabled="currentPage >= totalPages"
                                class="px-3 py-1.5 rounded-xl border dark:border-gray-700 text-xs font-bold disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                            >
                                Next
                            </button>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useImageStore } from '../stores/images';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import { useDiscussionsStore } from '../stores/discussions';
import { useTasksStore } from '../stores/tasks';
import { storeToRefs } from 'pinia';
import AuthenticatedImage from '../components/ui/AuthenticatedImage.vue';
import apiClient from '../services/api';

// Icons
import IconPhoto from '../assets/icons/IconPhoto.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconArrowUpTray from '../assets/icons/IconArrowUpTray.vue';
import IconSend from '../assets/icons/IconSend.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconMaximize from '../assets/icons/IconMaximize.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue'; 
import IconChevronUp from '../assets/icons/IconChevronUp.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconCamera from '../assets/icons/IconCamera.vue';
import IconXMark from '../assets/icons/IconXMark.vue';
import IconAdjustmentsHorizontal from '../assets/icons/IconAdjustmentsHorizontal.vue';
import IconFolder from '../assets/icons/IconFolder.vue';
import IconCheckCircle from '../assets/icons/IconCheckCircle.vue';
import IconCopy from '../assets/icons/IconCopy.vue';
import IconMagnifyingGlass from '../assets/icons/IconMagnifyingGlass.vue';
import IconArrowsUpDown from '../assets/icons/IconArrowsUpDown.vue';

const imageStore = useImageStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const tasksStore = useTasksStore();
const router = useRouter();

const { 
    images, isLoading, isGenerating, 
    currentPage, pageSize, totalImages, totalPages,
    prompt, negativePrompt, imageSize, nImages, seed, generationParams, 
    selectedAlbumId, albums 
} = storeToRefs(imageStore);
const { user } = storeToRefs(authStore);
const { imageGenerationTasks, imageGenerationTasksCount } = storeToRefs(tasksStore);

// Studio Local State
const activeDockTab = ref('prompt'); // 'prompt' | 'parameters'
const selectedStyle = ref('None');
const showMobileSidebar = ref(false);
const sidebarWidth = ref(400); 
const isResizing = ref(false);
const searchQuery = ref('');
const filterOrientation = ref('all');
const useFullResThumbnails = ref(false);
const isDraggingOver = ref(false);
const isEnhancingPrompt = ref(false);
const isEnhancingNegative = ref(false);
const isAnyEnhancing = computed(() => isEnhancingPrompt.value || isEnhancingNegative.value);
let searchDebounceTimer = null;

const collapsedStyles = ref({ 
    'Art Style': false, 
    'Artist Signature': true, 
    'Enhancements & Lighting': false, 
    'Camera & Framing': true 
});

const sidebarStyle = computed(() => ({
    width: window.innerWidth >= 1024 ? `${sidebarWidth.value}px` : undefined,
    minWidth: window.innerWidth >= 1024 ? '340px' : undefined
}));

const currentAlbumName = computed(() => {
    if (selectedAlbumId.value) {
        const album = albums.value.find(a => a.id === selectedAlbumId.value);
        return album ? album.name : 'Unknown Album';
    }
    return 'All Creations';
});

// Selection & Batch Management
const selectedImages = ref([]);
const isSelectionMode = computed(() => selectedImages.value.length > 0);

// Preserves the exact user-defined stage sequence
const selectedImageObjects = computed(() => {
    const idMap = new Map(images.value.map(img => [img.id, img]));
    return selectedImages.value.map(id => idMap.get(id)).filter(Boolean);
});

const areAllSelected = computed({ 
    get: () => filteredImages.value.length > 0 && selectedImages.value.length === filteredImages.value.length, 
    set: (v) => { selectedImages.value = v ? filteredImages.value.map(i => i.id) : []; } 
});

// Drag and drop reordering state for staged images
const draggedStagedIndex = ref(null);
const dragOverStagedIndex = ref(null);

function onStagedDragStart(index, event) {
    draggedStagedIndex.value = index;
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', String(index));
}

function onStagedDragOver(index, event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    dragOverStagedIndex.value = index;
}

function onStagedDrop(targetIndex, event) {
    event.preventDefault();
    const sourceIndex = draggedStagedIndex.value;
    if (sourceIndex !== null && sourceIndex !== targetIndex) {
        const item = selectedImages.value.splice(sourceIndex, 1)[0];
        selectedImages.value.splice(targetIndex, 0, item);
    }
    draggedStagedIndex.value = null;
    dragOverStagedIndex.value = null;
}

function onStagedDragEnd() {
    draggedStagedIndex.value = null;
    dragOverStagedIndex.value = null;
}

function moveStagedItem(index, direction) {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= selectedImages.value.length) return;
    const item = selectedImages.value.splice(index, 1)[0];
    selectedImages.value.splice(targetIndex, 0, item);
}

function getSelectionIndex(imageId) {
    const idx = selectedImages.value.indexOf(imageId);
    return idx !== -1 ? idx + 1 : null;
}

// Filtering Pipeline
const filteredImages = computed(() => {
    let list = images.value || [];

    if (searchQuery.value.trim()) {
        const q = searchQuery.value.toLowerCase().trim();
        list = list.filter(img => (img.prompt || '').toLowerCase().includes(q) || (img.model || '').toLowerCase().includes(q));
    }

    if (filterOrientation.value !== 'all') {
        list = list.filter(img => {
            if (!img.width || !img.height) return true;
            if (filterOrientation.value === 'square') return img.width === img.height;
            if (filterOrientation.value === 'landscape') return img.width > img.height;
            if (filterOrientation.value === 'portrait') return img.height > img.width;
            return true;
        });
    }

    return list;
});

// Resizing Drawer Logic
function startResizing(event) {
    isResizing.value = true;
    const startX = event.clientX, startWidth = sidebarWidth.value;
    const handleMouseMove = (e) => { 
        if (!isResizing.value) return; 
        sidebarWidth.value = Math.max(340, Math.min(startWidth + (e.clientX - startX), 720)); 
    };
    const handleMouseUp = () => { 
        isResizing.value = false; 
        localStorage.setItem('lollms_image_studio_sidebar_width', sidebarWidth.value); 
        window.removeEventListener('mousemove', handleMouseMove); 
        window.removeEventListener('mouseup', handleMouseUp); 
    };
    window.addEventListener('mousemove', handleMouseMove); 
    window.addEventListener('mouseup', handleMouseUp);
}

// Preset Library
const styleLibrary = {
    'Art Style': [
        { name: 'Photo RAW', emoji: '📸', prompt: 'photorealistic, RAW photo, 8k uhd, dslr, high detailed, professional photography', negative: 'drawing, cartoon, 3d render, plastic' },
        { name: 'Cinematic', emoji: '🎬', prompt: 'cinematic lighting, 35mm film, dramatic atmosphere, color graded, epic composition', negative: 'amateur, grainy, low quality' },
        { name: 'Anime Pro', emoji: '🎌', prompt: 'high quality anime key visual, Makoto Shinkai style, vibrant colors, detailed line art', negative: 'photorealistic, 3d, western comic' },
        { name: 'Concept Art', emoji: '🎨', prompt: 'digital concept art, trending on ArtStation, dynamic lighting, octane render', negative: 'photo, realistic' },
        { name: 'Cyberpunk', emoji: '🌃', prompt: 'cyberpunk aesthetic, volumetric neon light, rain soaked streets, futuristic high tech', negative: 'vintage, medieval' },
        { name: 'Fantasy', emoji: '🧙‍♂️', prompt: 'high fantasy illustration, magical ethereal atmosphere, intricate ornate detailing', negative: 'modern, industrial' }
    ],
    'Artist Signature': [
        { name: 'Van Gogh', emoji: '🌻', prompt: 'post-impressionism, vibrant swirling brushstrokes in the style of Vincent van Gogh', negative: '' },
        { name: 'Studio Ghibli', emoji: '🌳', prompt: 'Studio Ghibli aesthetic, Hayao Miyazaki, lush hand-painted background, serene', negative: '' },
        { name: 'Greg Rutkowski', emoji: '⚔️', prompt: 'style of Greg Rutkowski, dramatic fantasy concept art, oil on canvas feel', negative: '' },
        { name: 'Moebius', emoji: '🏜️', prompt: 'Jean Giraud Moebius style, clean linework, flat pastel palette, sci-fi surrealism', negative: '' }
    ],
    'Enhancements & Lighting': [
        { name: 'Golden Hour', emoji: '🌅', prompt: 'warm sunset lighting, soft golden hour glow, lens flare', negative: 'harsh shadows, studio light' },
        { name: 'Studio Lights', emoji: '💡', prompt: 'three-point studio lighting, softbox, rim light, clean studio backdrop', negative: 'dark, noisy' },
        { name: 'Moody Dark', emoji: '🕯️', prompt: 'chiaroscuro, deep shadows, moody candlelight, atmospheric haze', negative: 'overexposed, washed out' },
        { name: 'Volumetric', emoji: '✨', prompt: 'volumetric god rays, atmospheric fog, ethereal backlighting', negative: 'flat lighting' }
    ],
    'Camera & Framing': [
        { name: 'Wide Angle', emoji: '🔭', prompt: 'wide angle lens, 24mm, expansive view, grand scale', negative: 'telephoto, cropped' },
        { name: 'Macro Close', emoji: '🔍', prompt: 'macro lens photography, extreme shallow depth of field, sharp focal subject', negative: 'wide shot' },
        { name: 'Isometric', emoji: '📐', prompt: 'isometric perspective, clean 3D diorama view, orthographic projection', negative: 'first person' }
    ]
};

const quickNegativePresets = [
    { label: 'Standard Clean', value: 'ugly, deformed, disfigured, low quality, blurry, watermark' },
    { label: 'Anatomy Fix', value: 'extra limbs, bad anatomy, missing fingers, extra fingers, mutated hands' },
    { label: 'Photo Reality', value: '3D render, cartoon, anime, illustration, plastic skin, airbrushed' }
];

const aspectRatios = [
    { name: '1:1 Square', value: '1024x1024', style: { width: '18px', height: '18px' } },
    { name: '16:9 Cinema', value: '1344x768', style: { width: '24px', height: '14px' } },
    { name: '9:16 Story', value: '768x1344', style: { width: '14px', height: '24px' } },
    { name: '4:3 Classic', value: '1152x896', style: { width: '20px', height: '15px' } },
    { name: '3:2 Photo', value: '1216x832', style: { width: '22px', height: '15px' } },
    { name: '21:9 Ultra', value: '1536x640', style: { width: '26px', height: '11px' } }
];

const selectedModel = computed(() => user.value?.tti_binding_model_name);

const modelConfigurableParameters = computed(() => {
    const details = dataStore.availableTtiModels.find(m => m.id === selectedModel.value);
    if (!details?.binding_params) return [];
    const params = isSelectionMode.value ? (details.binding_params.edit_parameters || []) : (details.binding_params.generation_parameters || []);
    return params.filter(p => !['prompt', 'negative_prompt', 'image', 'mask', 'width', 'height', 'n', 'seed', 'size'].includes(p.name));
});

function applyStyle(style) {
    if (selectedStyle.value === style.name) {
        selectedStyle.value = 'None';
    } else {
        selectedStyle.value = style.name;
        if (style.name !== 'None') {
            prompt.value = prompt.value.trim() ? `${prompt.value}, ${style.prompt}` : style.prompt;
            if (style.negative) {
                negativePrompt.value = negativePrompt.value.trim() ? `${negativePrompt.value}, ${style.negative}` : style.negative;
            }
        }
    }
}

function appendNegative(tagText) {
    if (!negativePrompt.value.trim()) {
        negativePrompt.value = tagText;
    } else if (!negativePrompt.value.includes(tagText)) {
        negativePrompt.value += `, ${tagText}`;
    }
}

function clearPrompt() {
    prompt.value = '';
    selectedStyle.value = 'None';
}

function copyPrompt(text) {
    if (!text) return;
    uiStore.copyToClipboard(text);
}

function downloadSingle(image) {
    const link = document.createElement('a');
    link.href = `/api/image-studio/${image.id}/file`;
    link.download = `${image.prompt ? image.prompt.slice(0, 30) : 'creation'}_${image.id}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    uiStore.addNotification('Image download started.', 'success', 2000);
}

function handleBatchZipDownload() {
    imageStore.downloadBatch(selectedImages.value);
}

function openCompareModal() {
    if (selectedImages.value.length !== 2) return;
    const [imgA, imgB] = selectedImageObjects.value;
    uiStore.openModal('interactiveOutput', {
        title: 'Side-by-Side Comparison',
        htmlContent: `
            <div style="display: flex; gap: 16px; justify-content: center; align-items: center; width: 100%; height: 100%; padding: 16px; box-sizing: border-box;">
                <div style="flex: 1; text-align: center;">
                    <img src="/api/image-studio/${imgA.id}/file" style="max-width: 100%; max-height: 75vh; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.3);" />
                    <p style="margin-top: 8px; font-size: 11px; opacity: 0.7;">${imgA.prompt || 'Variant A'}</p>
                </div>
                <div style="flex: 1; text-align: center;">
                    <img src="/api/image-studio/${imgB.id}/file" style="max-width: 100%; max-height: 75vh; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.3);" />
                    <p style="margin-top: 8px; font-size: 11px; opacity: 0.7;">${imgB.prompt || 'Variant B'}</p>
                </div>
            </div>
        `
    });
}

function toggleSelection(id) { 
    const i = selectedImages.value.indexOf(id); 
    if (i > -1) selectedImages.value.splice(i, 1); 
    else selectedImages.value.push(id); 
}

function isSelected(id) { 
    return selectedImages.value.includes(id); 
}

async function handleGenerateOrApply() {
    if (!prompt.value.trim() || !selectedModel.value) {
        uiStore.addNotification('Please provide a prompt and select an active TTI model.', 'warning');
        return;
    }
    showMobileSidebar.value = false;
    const payload = { 
        prompt: prompt.value, 
        negative_prompt: negativePrompt.value, 
        model: selectedModel.value, 
        seed: seed.value, 
        ...generationParams.value 
    };

    if (isSelectionMode.value) {
        const [w, h] = imageSize.value.split('x').map(Number);
        await imageStore.editImage({ ...payload, image_ids: selectedImages.value, width: w, height: h });
        selectedImages.value = [];
    } else {
        await imageStore.generateImage({ ...payload, size: imageSize.value, n: nImages.value });
    }
}

async function handleEnhance(type, options = {}) {
    if (type !== 'negative_prompt' && !prompt.value.trim()) return;
    if (type === 'prompt' || type === 'both') isEnhancingPrompt.value = true;
    if (type === 'negative_prompt' || type === 'both') isEnhancingNegative.value = true;

    const payload = { 
        prompt: prompt.value, 
        negative_prompt: negativePrompt.value, 
        target: type, 
        model: authStore.user?.lollms_model_name, 
        instructions: options.instructions || '', 
        mode: options.mode || 'description' 
    };

    try {
        const task = await imageStore.enhanceImagePrompt(payload);
        if (task?.id) monitorEnhancementTask(task.id, type);
        else resetEnhancingFlags(type);
    } catch (e) { 
        resetEnhancingFlags(type); 
    }
}

function monitorEnhancementTask(id, type) {
    const unwatch = watch(() => tasksStore.tasks.find(t => t.id === id), (t) => {
        if (!t) return;
        if (t.status === 'completed') {
            let res = typeof t.result === 'string' ? JSON.parse(t.result) : t.result;
            if (res) { 
                if (res.prompt) imageStore.prompt = res.prompt; 
                if (res.negative_prompt) imageStore.negativePrompt = res.negative_prompt; 
            }
            resetEnhancingFlags(type); 
            unwatch();
        } else if (['failed', 'cancelled'].includes(t.status)) { 
            resetEnhancingFlags(type); 
            unwatch(); 
        }
    }, { deep: true, immediate: true });
}

function resetEnhancingFlags(type) { 
    if (type === 'prompt' || type === 'both') isEnhancingPrompt.value = false; 
    if (type === 'negative_prompt' || type === 'both') isEnhancingNegative.value = false; 
}

function openEnhanceModal(target) { 
    uiStore.openModal('enhancePrompt', { onConfirm: (opts) => handleEnhance(target, opts) }); 
}

function handleNewBlankImage() { router.push('/image-studio/edit/new'); }

function reusePrompt(img) { 
    prompt.value = img.prompt || ''; 
    negativePrompt.value = img.negative_prompt || ''; 
    seed.value = img.seed ?? -1; 
    uiStore.addNotification('Parameters loaded into Studio.', 'info', 1500);
}

function openInpaintingEditor(img) { router.push(`/image-studio/edit/${img.id}`); }

function openImageViewer(img, idx) { 
    // Build full sequence for the lightbox viewer so user can navigate seamlessly across all images
    const sequence = filteredImages.value.map((i, ord) => ({
        id: i.id,
        src: `/api/image-studio/${i.id}/file`,
        thumbnail: `/api/image-studio/${i.id}/thumbnail?size=256`,
        prompt: i.prompt ? `#${(currentPage.value - 1) * pageSize.value + ord + 1}: ${i.prompt}` : `Image #${(currentPage.value - 1) * pageSize.value + ord + 1}`,
        model: i.model,
        width: i.width,
        height: i.height,
        seed: i.seed
    }));

    uiStore.openImageViewer({ 
        imageList: sequence, 
        startIndex: idx 
    }); 
}

const visiblePageNumbers = computed(() => {
    const total = totalPages.value;
    const current = currentPage.value;
    const pages = [];

    if (total <= 7) {
        for (let i = 1; i <= total; i++) pages.push(i);
    } else {
        pages.push(1);
        let start = Math.max(2, current - 1);
        let end = Math.min(total - 1, current + 1);

        for (let i = start; i <= end; i++) {
            if (!pages.includes(i)) pages.push(i);
        }
        if (!pages.includes(total)) pages.push(total);
    }
    return pages;
});

function goToPage(p) {
    if (p < 1 || p > totalPages.value || p === currentPage.value) return;
    imageStore.fetchImages(p);
}

function onSearchInput() {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        imageStore.searchQuery = searchQuery.value;
        imageStore.fetchImages(1);
    }, 400);
}

function clearSearch() {
    searchQuery.value = '';
    imageStore.searchQuery = '';
    imageStore.fetchImages(1);
}

async function handleUpload(e) { 
    if (e.target.files.length) await imageStore.uploadImages(Array.from(e.target.files)); 
}

async function handleDeleteSelected() { 
    const confirmed = await uiStore.showConfirmation({ 
        title: `Delete ${selectedImages.value.length} Image(s)?`,
        message: 'This will permanently remove these files from disk.',
        confirmText: 'Delete All',
        danger: true
    }); 
    if (confirmed) { 
        await Promise.all(selectedImages.value.map(id => imageStore.deleteImage(id))); 
        selectedImages.value = []; 
    } 
}

async function handleMoveToDiscussion() {
    const { confirmed, value: id } = await uiStore.showConfirmation({ 
        title: 'Send Images to Discussion Workspace', 
        message: `Label and attach ${selectedImages.value.length} image(s) (#1, #2...) into discussion context.`,
        inputType: 'select', 
        inputOptions: discussionsStore.sortedDiscussions.map(d => ({ text: d.title, value: d.id })) 
    }); 
    if (confirmed && id) { 
        await imageStore.moveImagesToDiscussionBatch(selectedImages.value, id);
        selectedImages.value = []; 
    }
}

async function handleMoveToAlbum() {
    const { confirmed, value: albumId } = await uiStore.showConfirmation({
        title: 'Organize into Album',
        inputType: 'select',
        inputOptions: [
            { text: 'Ungrouped (Default)', value: '' },
            ...albums.value.map(a => ({ text: a.name, value: a.id }))
        ]
    });

    if (confirmed) {
        const targetId = albumId === '' ? null : albumId;
        await Promise.all(selectedImages.value.map(imgId => imageStore.moveImageToAlbum(imgId, targetId)));
        selectedImages.value = [];
    }
}

function handleDragOver(e) { e.preventDefault(); isDraggingOver.value = true; }
function handleDragLeave(e) { if (!e.currentTarget.contains(e.relatedTarget)) isDraggingOver.value = false; }
async function handleDrop(e) { 
    e.preventDefault(); 
    isDraggingOver.value = false; 
    const f = Array.from(e.dataTransfer.files).filter(i => i.type.startsWith('image/')); 
    if (f.length) await imageStore.uploadImages(f); 
}

async function handlePaste(e) { 
    const items = (e.clipboardData || window.clipboardData).items; 
    const files = []; 
    for (const i of items) { 
        if (i.kind === 'file' && i.type.startsWith('image/')) { 
            const f = i.getAsFile(); 
            if (f) files.push(new File([f], `pasted_${Date.now()}.png`, { type: f.type })); 
        } 
    } 
    if (files.length) { 
        e.preventDefault(); 
        await imageStore.uploadImages(files); 
    } 
}

function openCameraModal() { uiStore.openModal('cameraCapture'); }
function handleRefresh() { imageStore.fetchImages(); }

onMounted(() => {
    const savedWidth = localStorage.getItem('lollms_image_studio_sidebar_width');
    if (savedWidth) sidebarWidth.value = parseInt(savedWidth, 10);
    imageStore.fetchImages();
    if (dataStore.availableTtiModels.length === 0) dataStore.fetchAvailableTtiModels();
    window.addEventListener('paste', handlePaste);
});

onUnmounted(() => { 
    window.removeEventListener('paste', handlePaste); 
});
</script>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>
