<!-- [UPDATE] frontend/webui/src/views/ImageStudioView.vue -->
<template>
    <!-- 1. Header Title Portal: Studio Status, Album & Selection Toggle -->
    <Teleport to="#global-header-title-target" v-if="hasHeaderTarget">
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
    <Teleport to="#global-header-actions-target" v-if="hasHeaderTarget">
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

                        <!-- Categorized Style Library with Quick Search -->
                        <div class="space-y-3 pt-2">
                            <div class="flex items-center justify-between">
                                <span class="text-[10px] font-black text-gray-400 uppercase tracking-widest block">Style Preset Library (50+)</span>
                                <span v-if="selectedStyle !== 'None'" class="text-[9px] font-bold text-blue-500 uppercase bg-blue-50 dark:bg-blue-900/30 px-2 py-0.5 rounded-full border border-blue-200 dark:border-blue-800">
                                    Active: {{ selectedStyle }}
                                </span>
                            </div>

                            <!-- Style Search Filter Input -->
                            <div class="relative">
                                <input 
                                    v-model="styleSearchTerm" 
                                    type="text" 
                                    placeholder="Search 50+ presets (e.g. Ghibli, 35mm, Neon, Cyberpunk)..." 
                                    class="input-field !py-1 !pl-7 !text-[10px] w-full"
                                />
                                <IconMagnifyingGlass class="w-3 h-3 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                                <button v-if="styleSearchTerm" @click="styleSearchTerm = ''" class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-red-500">
                                    <IconXMark class="w-3 h-3" />
                                </button>
                            </div>

                            <div v-for="(group, category) in filteredStyleLibrary" :key="category" class="rounded-xl border dark:border-gray-800 overflow-hidden bg-gray-50/50 dark:bg-gray-900/30">
                                <button 
                                    @click="toggleStyleCategory(category)" 
                                    class="w-full flex items-center justify-between p-2.5 hover:bg-gray-100/50 dark:hover:bg-gray-800/50 transition-colors select-none"
                                >
                                    <div class="flex items-center gap-2">
                                        <span class="text-[10px] font-black text-gray-700 dark:text-gray-200 uppercase tracking-widest">{{ category }}</span>
                                        <span class="text-[9px] font-mono font-bold text-gray-400 bg-gray-200 dark:bg-gray-800 px-1.5 py-0.2 rounded">{{ group.length }}</span>
                                    </div>
                                    <IconChevronUp class="w-3.5 h-3.5 text-gray-400 transition-transform" :class="{'rotate-180': isCategoryCollapsed(category)}" />
                                </button>

                                <div v-show="!isCategoryCollapsed(category)" class="p-2 grid grid-cols-2 sm:grid-cols-3 gap-1.5 border-t dark:border-gray-800 animate-in fade-in">
                                    <button 
                                        v-for="style in group" 
                                        :key="style.name" 
                                        @click="applyStyle(style)"
                                        class="flex flex-col items-center p-2 rounded-xl border transition-all hover:scale-102 text-center"
                                        :class="selectedStyle === style.name ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 ring-1 ring-blue-500 shadow-sm' : 'border-gray-200 dark:border-gray-700/50 bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600 shadow-xs'"
                                        :title="style.prompt"
                                    >
                                        <span class="text-xl mb-1 select-none">{{ style.emoji }}</span>
                                        <span class="text-[9px] font-black truncate w-full uppercase tracking-tight">{{ style.name }}</span>
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
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue';
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
const hasHeaderTarget = ref(false);
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
const styleSearchTerm = ref('');
const collapsedStyles = ref({
    '💎 Image Enhancement & Restoration': false,
    '🌈 Colorization & Color Grading': false,
    '📸 Photographic & Realism': false,
    '🎮 3D, CGI & Sci-Fi': true,
    '🎨 Traditional Mediums': true,
    '🎌 Anime, Manga & Comics': true,
    '🏛️ Art Movements & Masters': true,
    '✨ Lighting & Atmosphere': true,
    '🔭 Camera Angles & Lenses': true
});

function toggleStyleCategory(cat) {
    collapsedStyles.value[cat] = !collapsedStyles.value[cat];
}

function isCategoryCollapsed(cat) {
    if (styleSearchTerm.value.trim()) return false; // Auto-expand all when searching
    return !!collapsedStyles.value[cat];
}

// 140+ Curated State-of-the-Art Style Presets for Diffusion Models (16 per category)
const styleLibrary = {
    '💎 Image Enhancement & Restoration': [
        { name: '4K Remaster', emoji: '💎', prompt: 'masterpiece, 8k uhd, pristine sharp focus, ultra-detailed micro texture, noise reduction, crystal clear details, natural pore structure, ProRes cinematic remaster', negative: 'blurry, noise, artifacts, low resolution, pixelated, jpeg compression, bad anatomy, over-smoothed' },
        { name: 'HDR Clarity', emoji: '🌟', prompt: 'high dynamic range, crystal clear clarity, hyper-fine details, de-noised, sharp edges, clean lighting, balanced exposure, immaculate textures', negative: 'grainy, noisy, dark artifacts, washed out, blurry' },
        { name: 'Portrait Refine', emoji: '👤', prompt: 'subsurface scattering, realistic natural skin texture, visible fine pores, catchlights in eyes, individually defined hair strands, studio quality headshot, photorealistic', negative: 'plastic skin, airbrushed, cartoon, doll-like, waxy face, smooth blur' },
        { name: 'Damage Repair', emoji: '🩹', prompt: 'restored photograph, seamless scratch repair, crease removal, stain heal, sharp details recovered, crisp edges, damage-free vintage photo restoration', negative: 'scratches, cracks, stains, torn, fold lines, dust spots, blur, noise' },
        { name: 'Tack Sharp Edge', emoji: '🔍', prompt: 'tack sharp contrast, crisp high-definition line recovery, well-resolved edges, geometric clarity, clean micro-details, ultra-focused', negative: 'blurry edges, halo artifacts, chromatic aberration, fuzzy' },
        { name: 'De-Blur & Focus', emoji: '🎯', prompt: 'de-blurred, sharp focal alignment, recovered subject contours, clean separation, pristine optical clarity', negative: 'motion blur, camera shake, out of focus, soft haze' },
        { name: 'Noise Cleanse', emoji: '🧼', prompt: 'ultra clean denoising, grain removal, pristine smooth gradients, artifact elimination, studio clean sensor fidelity', negative: 'film grain, digital noise, chromatic noise, compression artifacts, gritty' },
        { name: 'Face Symmetry', emoji: '🪞', prompt: 'balanced facial symmetry, natural anatomical perfection, realistic proportions, harmonious facial features, photorealistic headshot', negative: 'asymmetric eyes, crooked mouth, distorted nose, bad anatomy, deformed facial features' },
        { name: 'Micro Detail Texture', emoji: '🔬', prompt: 'hyper-detailed micro-surface textures, intricate fine details, sharp fabric weave, realistic pore fidelity, 8k resolution macro', negative: 'blurry, flat texture, low resolution, smooth plastic' },
        { name: 'White Balance Neutral', emoji: '⚖️', prompt: 'perfect neutral white balance, corrected color cast, true-to-life tones, natural daylight calibration, calibrated color profile', negative: 'yellow tint, blue cast, magenta tint, green color cast, washed out' },
        { name: 'Dynamic Range Recover', emoji: '⛅', prompt: 'recovered shadow detail, balanced dynamic range, pulled highlights, zero clipping, smooth tonal roll-off, raw development', negative: 'blown out highlights, crushed blacks, harsh contrast, clipped dynamic range' },
        { name: 'Hair & Fur Groom', emoji: '🦁', prompt: 'fine strand separation, individual hair rendering, realistic soft fur texture, detailed edge definition, natural volume', negative: 'clumpy hair, painted blob, blurry edges, low polygon' },
        { name: 'Vector Line Sharpener', emoji: '🖋️', prompt: 'clean vectorized ink lines, crisp edge detection, anti-aliased smooth contours, high-contrast black line recovery', negative: 'pixelated jagged lines, blurry ink, smudges, halo effect' },
        { name: 'Artifact Heal', emoji: '🧩', prompt: 'removed JPEG artifacts, band removal, pixelation fix, scanline cleanup, clean reconstructed raster', negative: 'banding, posterization, compression blocks, glitch, corrupted pixels' },
        { name: 'Studio Relighting', emoji: '💡', prompt: 'professional three-point studio relighting, soft fill light, sharp rim accent, balanced key light, dimensional sculpting', negative: 'harsh flash, flat lighting, muddy shadows, underexposed' },
        { name: 'Iris Catchlight', emoji: '👁️', prompt: 'deep intricate iris patterns, sharp corneal reflection, luminous crystalline catchlight, crystal clear gaze, high resolution macro eyes', negative: 'dull lifeless eyes, blurry pupil, bloodshot, deformed iris' }
    ],

    '🌈 Colorization & Color Grading': [
        { name: 'B&W to Color', emoji: '🎨', prompt: 'natural historical colorization, authentic human skin tones, realistic clothing pigments, vibrant balanced color depth, accurate environmental colors, colorized from black and white', negative: 'monochrome, black and white, grayscale, washed out color, sepia tint, oversaturated neon' },
        { name: '50s Technicolor', emoji: '📼', prompt: '1950s 3-strip Technicolor film aesthetic, lush saturated primary colors, warm golden skin tones, rich velvety reds and emerald greens, classic Hollywood palette', negative: 'modern desaturated, cold digital, monochrome' },
        { name: 'Vibrant Color Pop', emoji: '💥', prompt: 'vivid dynamic color palette, rich color depth, chromatic brilliance, high saturation balance, vibrant eye-catching hues, radiant colors', negative: 'dull, muted, faded, washed out, monochromatic, muddy' },
        { name: 'Pastel Dreams', emoji: '🌸', prompt: 'soft pastel color grading, gentle creamy tones, subtle lavender, peach and mint hues, airy diffused lighting, delicate romantic aesthetic', negative: 'harsh contrast, garish neon, dark muddy shadows' },
        { name: 'Teal & Orange', emoji: '🎬', prompt: 'cinematic teal and orange color harmony, cool moody shadow tones, warm golden subject accents, atmospheric Hollywood film grade', negative: 'green tint, muddy colors, flat monochrome' },
        { name: 'Warm Terracotta', emoji: '🍯', prompt: 'warm amber and terracotta color grade, rich honey undertones, golden sunlight hues, cozy inviting atmosphere, sun-kissed warmth', negative: 'cold blue, stark sterile, pale' },
        { name: 'Cyber Duotone', emoji: '🟣', prompt: 'striking dual-tone duotone, electric cyan and hot magenta contrast, high-impact graphic poster lighting, stylized chromatic split', negative: 'natural lighting, muted colors, muddy' },
        { name: 'Hand-Tinted Antique', emoji: '🖌️', prompt: 'hand-tinted vintage photograph, delicate watercolor washes over silver gelatin print, antique subtle tinting, historic nostalgic charm', negative: 'modern digital HDR, harsh neon saturation' },
        { name: 'Nordic Muted Cold', emoji: '❄️', prompt: 'scandinavian cinema grade, cold desaturated tones, icy blue undertones, minimalist Nordic mood, muted earthy accents', negative: 'oversaturated, warm yellow, tropical bright' },
        { name: 'Autumn Warmth', emoji: '🍂', prompt: 'rich autumn color grade, deep crimson reds, burnt orange, golden mustard tones, crisp cozy warmth', negative: 'neon colors, cold blue, vibrant green' },
        { name: 'Sepia Nostalgia', emoji: '📜', prompt: 'authentic antique sepia tone, rich warm monochrome brown palette, historical vintage photographic aesthetic', negative: 'vibrant modern colors, RGB, neon, cool cyan' },
        { name: 'Fuji Velvia Vivid', emoji: '🏔️', prompt: 'Fujifilm Velvia 50 film simulation, vivid emerald greens, deep saturated blues, punchy high-contrast color landscape', negative: 'flat, desaturated, digital video look' },
        { name: 'Kodachrome 64', emoji: '📻', prompt: 'classic 1970s Kodachrome 64 slide film, iconic documentary colors, rich saturated primary tones, timeless analog nostalgia', negative: 'cold modern digital, oversaturated HDR' },
        { name: 'Midnight Cyan', emoji: '🌙', prompt: 'deep midnight navy palette, bioluminescent cyan highlights, moody low-key cool tones, cinematic night atmosphere', negative: 'warm daylight, yellow sunlight' },
        { name: 'Sunset Coral & Lilac', emoji: '🪸', prompt: 'dreamy sunset gradient palette, soft coral pink and lavender purple skies, luminous twilight hues, romantic aesthetic', negative: 'harsh noon lighting, dull grey' },
        { name: 'High-Key Pure White', emoji: '⚪', prompt: 'high-key pure white minimalist palette, clean porcelain whites, delicate subtle silver tones, airy bright composition', negative: 'dark shadows, saturated colors, dirty textures' }
    ],

    '📸 Photographic & Realism': [
        { name: 'Photo RAW', emoji: '📸', prompt: 'photorealistic, RAW photo, 8k uhd, dslr, soft lighting, high detailed skin texture, sharp focus, professional award-winning photography', negative: 'drawing, cartoon, 3d render, plastic, airbrushed, oversaturated' },
        { name: 'Cinematic 35mm', emoji: '🎬', prompt: 'cinematic still, 35mm anamorphic lens, dramatic atmosphere, color graded, subtle lens flare, teal and orange film aesthetic, Panavision', negative: 'amateur, grainy, low quality, overexposed, flat lighting' },
        { name: 'Vintage Kodak', emoji: '🎞️', prompt: 'vintage 35mm photograph, Kodak Portra 400, authentic analog film grain, nostalgic warm hues, organic light leaks, 1990s aesthetic', negative: 'digital, pristine, 3d CGI, artificial, modern HDR' },
        { name: 'Polaroid Instant', emoji: '📷', prompt: 'authentic vintage Polaroid instant photo, flash photography, soft edges, square white border, slight vignette, authentic film artifacts', negative: 'sharp digital rendering, high definition 3d' },
        { name: 'Street Candid', emoji: '🚶', prompt: 'candid street photography, Leica M11, natural daylight, authentic human emotion, urban documentary composition, 35mm f/2', negative: 'posed, studio lighting, plastic, CGI' },
        { name: 'Macro Detail', emoji: '🔬', prompt: 'extreme macro photography, 100mm f/2.8 lens, hyper-detailed texture, shallow depth of field, natural soft bokeh, crisp focal point', negative: 'wide shot, blurry center, cartoon' },
        { name: 'National Geographic', emoji: '🌍', prompt: 'National Geographic award-winning wildlife and landscape photography, dramatic natural light, authentic documentary realism, telephoto lens', negative: 'staged, studio, amateur, low resolution, fake' },
        { name: 'Film Noir B&W', emoji: '🕵️', prompt: 'classic film noir black and white photography, high contrast chiaroscuro, dramatic Venetian blind shadows, atmospheric grain, 1940s moody', negative: 'color, flat lighting, daylight' },
        { name: 'Drone Aerial', emoji: '🛰️', prompt: 'breathtaking drone aerial landscape photography, top-down bird eye view, expansive golden hour light, high altitude perspective, 4k ultra-detailed', negative: 'ground level, close up, fisheye' },
        { name: 'Fashion Editorial', emoji: '👗', prompt: 'high-fashion editorial photography, Vogue magazine style, dramatic studio lighting, avant-garde styling, ultra sharp, clean solid backdrop', negative: 'amateur, passport photo, flat lighting' },
        { name: 'Lomography Toy Cam', emoji: '🎯', prompt: 'Lomography Diana camera aesthetic, heavy circular vignette, cross-processed saturated colors, soft focus optical distortion, playful analog', negative: 'clean digital, sharp clinical, 3d render' },
        { name: 'Wet Plate Tintype', emoji: '🏺', prompt: '19th-century tintype wet plate collodion photograph, silver emulsion streaks, antique chemical patina, dark moody historical portrait', negative: 'clean modern photo, digital color' },
        { name: 'Architectural Digest', emoji: '🏛️', prompt: 'Architectural Digest professional interior and exterior photography, tilt-shift straight vertical lines, pristine balanced natural light, ultra sharp', negative: 'crooked angles, wide distortion, messy lighting' },
        { name: 'Paparazzi Flash', emoji: '📸', prompt: 'direct camera flash aesthetic, high-contrast celebrity night snap, harsh dramatic drop shadow, 2000s paparazzi style', negative: 'soft studio light, diffused painting' },
        { name: 'Long Exposure Waves', emoji: '🌊', prompt: 'long exposure photography, silky smooth water flow, luminous light trails, ethereal motion blur, tack-sharp static elements', negative: 'choppy frozen water, daytime snapshot' },
        { name: 'Pinhole Camera', emoji: '🕳️', prompt: 'primitive pinhole camera exposure, infinite soft depth of field, dramatic edge vignetting, organic analog blur, dreamlike simplicity', negative: 'sharp modern lens, digital crispness' }
    ],

    '🎮 3D, CGI & Sci-Fi': [
        { name: 'Unreal Engine 5', emoji: '🎮', prompt: 'rendered in Unreal Engine 5, Octane Render, 8k, Ray Tracing, Lumen Global Illumination, volumetric fog, hyper-detailed textures, cinematic composition', negative: 'flat 2d, sketch, low poly, noisy' },
        { name: 'Pixar / Disney 3D', emoji: '🧸', prompt: '3D animated movie style, Pixar Disney aesthetic, cute expressive stylized character, soft subsurface scattering, vibrant warm lighting, 4k render', negative: 'gritty, photorealistic, creepy, flat 2d' },
        { name: 'Cyberpunk 2077', emoji: '🌃', prompt: 'cyberpunk aesthetic, high-tech low-life, neon volumetric light, rain-soaked reflective asphalt, holographic interfaces, futuristic megalopolis', negative: 'medieval, rustic, pastoral, daylight' },
        { name: 'Steampunk Industrial', emoji: '⚙️', prompt: 'intricate steampunk aesthetic, polished brass gears, copper pressure gauges, Victorian industrial craftsmanship, steam vapors, warm amber atmosphere', negative: 'cyberpunk, sleek modern plastic, neon' },
        { name: 'Synthwave 80s', emoji: '🌴', prompt: '1980s synthwave retrowave aesthetic, glowing neon grid horizon, magenta and cyan gradient sunset, chrome reflections, VHS glitch aesthetic', negative: 'monochrome, gritty photorealism' },
        { name: 'Solarpunk City', emoji: '🌿', prompt: 'solarpunk architecture, lush vertical gardens, gleaming eco-futuristic curved glass towers, clean renewable energy, golden morning sunlight, utopian', negative: 'dystopian, smog, grim cyberpunk grime' },
        { name: 'Low Poly 3D', emoji: '🔷', prompt: 'isometric low poly 3D render, minimalist geometric aesthetic, soft pastel studio lighting, clean blender modeling, charming diorama', negative: 'hyperrealistic, high detail noisy textures' },
        { name: 'Claymation Motion', emoji: '🗿', prompt: 'stop-motion claymation, sculpted plasticine clay textures, visible fingerprint details, Aardman style studio miniature lighting, charming handcrafted', negative: 'smooth digital 3d, glossy vector, CGI' },
        { name: 'Papercraft Cutout', emoji: '📜', prompt: 'layered papercraft cutout art, multi-depth shadow box, textured craft paper, delicate folded origami, soft warm ambient lighting', negative: 'metallic, glossy plastic, photographic' },
        { name: 'Voxel Diorama', emoji: '🧊', prompt: 'detailed 3D voxel art, isometric blocky miniature diorama, colorful pixel-cubes, MagicaVoxel aesthetic, soft ambient occlusion shadows', negative: 'smooth, organic realistic' },
        { name: 'Biomechanical Giger', emoji: '👽', prompt: 'H.R. Giger biomechanical aesthetic, intricate organic alien machinery, dark chrome bone structures, surreal industrial xenomorph horror', negative: 'bright cheerful, cartoon, simple geometric' },
        { name: 'Ray-Traced Crystal', emoji: '🔮', prompt: 'ultra-realistic 3D ray tracing, complex glass refraction, chromatic dispersion, caustic light patterns, pristine crystal material render', negative: 'opaque, flat 2d, matte plastic' },
        { name: 'Mecha Anime Robot', emoji: '🤖', prompt: 'detailed Japanese mecha concept art, intricate mechanical joints, armor plating, hydraulic pistons, Gundam Macross industrial design', negative: 'organic human, fantasy medieval' },
        { name: 'Holographic HUD', emoji: '🥽', prompt: 'futuristic translucent holographic interface, glowing wireframe geometry, glowing blue HUD telemetry, floating data particles', negative: 'solid opaque, vintage paper, rustic' },
        { name: 'Diorama Isometric', emoji: '🏰', prompt: 'miniature tilt-shift 3D diorama, intricate tiny world modeling, toy box aesthetic, soft ray-traced ambient occlusion', negative: 'full scale real world, flat 2d' },
        { name: 'Fractal 3D Dream', emoji: '🌀', prompt: 'Mandelbulb 3D fractal art, infinitely complex geometric recursion, kaleidoscopic iridescent surfaces, mathematical dimensional wonder', negative: 'simple low poly, mundane real world' }
    ],

    '🎨 Traditional Mediums': [
        { name: 'Watercolor Splash', emoji: '🎨', prompt: 'fluid watercolor painting, wet-on-wet technique, delicate translucent color bleeds, expressive paint splatters, cold press cotton paper texture', negative: 'digital vector, harsh lines, 3d render' },
        { name: 'Impasto Oil Painting', emoji: '🖼️', prompt: 'textured impasto oil painting, thick visible palette knife strokes, rich layered oil pigments, museum masterpiece, heavy canvas texture', negative: 'smooth digital airbrush, photo, 3d CGI' },
        { name: 'Sumi-e Ink Wash', emoji: '🖌️', prompt: 'traditional Japanese Sumi-e ink wash painting, minimalist black ink brush calligraphy strokes, atmospheric rice paper bleeding, zen aesthetic', negative: 'vibrant neon colors, digital 3d, photorealistic' },
        { name: 'Charcoal Sketch', emoji: '✏️', prompt: 'expressive charcoal and chalk pastel drawing on textured vintage paper, smudged shadows, dramatic tonal contrast, raw hand-drawn hatching', negative: 'clean vector, digital gradient, saturated color' },
        { name: 'Ukiyo-e Woodblock', emoji: '🌊', prompt: 'traditional Japanese Ukiyo-e woodblock print, Hokusai and Hiroshige style, bold outlines, flat decorative color blocks, aged washi paper texture', negative: 'photorealistic, modern 3d, smooth shading' },
        { name: 'Opaque Gouache', emoji: '🌄', prompt: 'matte opaque gouache painting, mid-century modern aesthetic, rich flat colors, stylized hand-painted textures, clean folk art aesthetic', negative: 'glossy, 3d CGI, photorealistic' },
        { name: 'Stained Glass', emoji: '🕯️', prompt: 'intricate stained glass window art, luminous colorful translucent glass panels, leaded black contours, radiant glowing backlighting, cathedral cathedral aesthetic', negative: 'opaque, paper sketch, photo' },
        { name: 'Pointillism Dots', emoji: '🟣', prompt: 'Georges Seurat pointillism masterpiece, composed entirely of tiny distinct color dots, optical color blending, classical post-impressionist', negative: 'smooth continuous strokes, digital vector' },
        { name: 'Fresco Mural', emoji: '🏛️', prompt: 'aged Renaissance fresco plaster mural, weathered texture, crackled lime plaster surface, historic pigment patina, timeless wall painting', negative: 'glossy oil, modern digital, clean photo' },
        { name: 'Linocut Block Print', emoji: '✂️', prompt: 'handcrafted linocut print, bold graphic black-and-white gouged textures, raw expressive relief carving, craft printmaking ink', negative: 'smooth airbrush, gradient shading, 3d' },
        { name: 'Pastel Chalk Soft', emoji: '🖍️', prompt: 'soft French pastel chalk on velvet paper, delicate feathery blending, luminous powdery pigment dust, dreamy impressionist texture', negative: 'hard digital lines, glossy vector' },
        { name: 'Encaustic Beeswax', emoji: '🕯️', prompt: 'molten beeswax encaustic painting, layered translucent wax depth, embedded textured pigments, luminous dimensional surface', negative: 'flat 2d print, digital vector' },
        { name: 'Colored Pencil Layer', emoji: '✏️', prompt: 'meticulous colored pencil drawing, fine cross-hatched layering, crisp waxy pigment sheen, heavy archival bristol paper texture', negative: 'watercolor bleed, digital airbrush, 3d CGI' },
        { name: 'Scratchboard Art', emoji: '🖤', prompt: 'scratchboard art, white lines meticulously scraped out of black India ink board, high-contrast precision engraving look', negative: 'soft color wash, blurry edges, watercolor' },
        { name: 'Roman Mosaic', emoji: '🏺', prompt: 'ancient Roman mosaic artwork, thousands of tiny hand-placed colorful stone tesserae tiles, weathered grout lines, classical antiquity', negative: 'smooth paint, vector, photograph' },
        { name: 'Copperplate Etching', emoji: '📜', prompt: 'fine copperplate intaglio etching, Albrecht Dürer master engraving style, ultra-fine parallel hatching, antique printmaker ink', negative: 'modern color, smooth airbrush, cartoon' }
    ],

    '🎌 Anime, Manga & Comics': [
        { name: 'Studio Ghibli', emoji: '🍃', prompt: 'Studio Ghibli animation still, Hayao Miyazaki aesthetic, lush hand-painted watercolor background, nostalgic heartwarming mood, whimsical hand-drawn', negative: '3d render, gritty dark, realistic photo' },
        { name: 'Shinkai Anime Visual', emoji: '🎌', prompt: 'high-production anime key visual, Makoto Shinkai style, crisp cel shading, dazzling celestial light particles, hyper-vibrant blue sky and clouds', negative: 'western comic, 3d CGI, photorealism' },
        { name: 'Retro 80s Cel Anime', emoji: '📺', prompt: 'retro 1980s cel anime screen grab, classic vintage aesthetic, hand-drawn animation grain, nostalgic warm palette, VHS tape scanlines', negative: 'modern digital gradient, 3d CGI' },
        { name: 'Western Action Comic', emoji: '💥', prompt: 'dynamic comic book illustration, bold ink lineart, halftone Ben-Day dots, vibrant dramatic action hero coloring, Marvel DC style', negative: 'photograph, soft watercolor, smooth 3d' },
        { name: 'Graphic Novel Noir', emoji: '🕶️', prompt: 'Sin City graphic novel style, high-contrast stark black and white ink, selective vibrant splash of red, gritty urban shadows, Frank Miller', negative: 'colorful, soft pastel, realistic photograph' },
        { name: 'Manga Screentone', emoji: '📖', prompt: 'authentic Japanese manga page, sharp black ink line art, professional screentone dot patterns, expressive cross-hatching, dramatic speedlines', negative: 'color, watercolor, photorealistic, 3d' },
        { name: 'Chibi Kawaii', emoji: '🐱', prompt: 'super deformed chibi character art, oversized expressive head, kawaii aesthetic, cute bright pastels, charming sticker look, clean vector outlines', negative: 'realistic proportions, dark scary' },
        { name: 'Pop Art Silkscreen', emoji: '🥫', prompt: 'Andy Warhol and Roy Lichtenstein pop art, bold primary silkscreen colors, commercial graphic advertising aesthetic, high contrast print', negative: 'subtle, dark, realistic photograph' },
        { name: '90s Battle Shonen', emoji: '⚡', prompt: 'classic 1990s battle shonen manga style, explosive dynamic action lines, intense muscular anatomy, screaming power aura, hand-inked', negative: 'soft pastel, cute chibi, western cartoon' },
        { name: 'Shojo Romance', emoji: '💖', prompt: 'delicate Japanese shojo manga illustration, sparkling ethereal flower backgrounds, expressive emotional eyes, flowing ribbon hair', negative: 'gritty dark, violent, heavy mechanical' },
        { name: 'Dark Fantasy Berserk', emoji: '🗡️', prompt: 'Berserk Kentaro Miura aesthetic, ultra-dense cross-hatching, grim dark fantasy ink, terrifying demon monstrosities, majestic medieval horror', negative: 'bright cheerful, modern flat cartoon, clean 3d' },
        { name: 'Akira Neo-Tokyo', emoji: '🏍️', prompt: 'Katsuhiro Otomo Akira aesthetic, detailed industrial destruction, hand-painted cel animation background, cinematic neo-Tokyo', negative: 'cute simple, 3d CGI render' },
        { name: 'Manhwa Webtoon', emoji: '📱', prompt: 'modern Korean webtoon manhwa style, polished digital painting, glowing magical particle effects, dynamic panel lighting', negative: 'monochrome black and white, old cel animation' },
        { name: 'Ligne Claire Comic', emoji: '🏰', prompt: 'Ligne Claire Franco-Belgian comic style, Hergé Tintin and Moebius aesthetic, clear uniform line weights, flat elegant colors', negative: 'heavy shadows, cross-hatching, 3d' },
        { name: 'Rubberhose 1930s', emoji: '🎺', prompt: '1930s rubberhose animation, Fleischer Cuphead style, black and white pie-eyes, bouncy rounded anatomy, vintage film grain and scratches', negative: 'modern anime, realistic proportions, 3d CGI' },
        { name: 'Gothic Lolita Anime', emoji: '🖤', prompt: 'Gothic Lolita anime illustration, intricate lace and frills, porcelain doll aesthetics, dark romantic roses and corsets, moody elegance', negative: 'bright casual sportswear, simple vector' }
    ],

    '🏛️ Art Movements & Masters': [
        { name: 'Art Nouveau (Mucha)', emoji: '🌸', prompt: 'Alphonse Mucha Art Nouveau masterpiece, elegant organic flowing curves, intricate floral motifs, gold leaf foil embellishments, stained glass palette', negative: 'modern geometry, sharp industrial, photorealism' },
        { name: 'Art Deco Luxury', emoji: '🏛️', prompt: '1920s Art Deco grandeur, Great Gatsby geometric elegance, gleaming gold and black lacquer, streamlined luxury, symmetrical ornate architectural lines', negative: 'rustic, organic messy, watercolor' },
        { name: 'Surrealism (Dalí)', emoji: '⏳', prompt: 'dreamlike surrealist painting in the style of Salvador Dalí and René Magritte, impossible juxtaposed architecture, melting forms, enigmatic desert landscape', negative: 'ordinary, mundane realistic photo' },
        { name: 'Post-Impressionism', emoji: '🌻', prompt: 'post-impressionism in the style of Vincent van Gogh, thick expressive swirling brushstrokes, intense vivid color emotion, starry night aesthetic', negative: 'smooth photo, flat vector' },
        { name: 'Baroque Chiaroscuro', emoji: '👑', prompt: 'Baroque oil masterpiece, Rembrandt and Caravaggio lighting, deep mysterious darks, dramatic illuminated golden highlights, emotional intensity', negative: 'flat high-key, modern bright neon' },
        { name: 'Bauhaus Minimalist', emoji: '🟥', prompt: 'Bauhaus modernism design, clean geometric forms, primary colors red blue yellow, asymmetric balance, functional graphic poster style', negative: 'ornate decorative clutter, realistic photo' },
        { name: 'Gothic Dark Fantasy', emoji: '🏰', prompt: 'dark gothic fantasy illustration, Soulsborne aesthetic, crumbling cathedral ruins, grim atmospheric mist, Eldritch horror, oil on canvas feel', negative: 'cheerful, bright pastel, modern' },
        { name: 'Cubism Picasso', emoji: '🔲', prompt: 'analytical cubism in the style of Pablo Picasso and Georges Braque, deconstructed geometric viewpoints, fragmented overlapping facets', negative: 'photorealistic, single perspective, smooth 3d' },
        { name: 'Monet Impressionism', emoji: '🪷', prompt: 'Claude Monet impressionist masterpiece, dappled outdoor natural sunlight, visible soft loose brush strokes, radiant fleeting light on water', negative: 'sharp hard lines, dark gloomy, photographic' },
        { name: 'Da Vinci Renaissance', emoji: '🎨', prompt: 'Italian High Renaissance oil painting in the style of Leonardo da Vinci, sfumato soft smoky blending, classical anatomical grace, golden varnish', negative: 'modern digital, harsh neon, cartoon' },
        { name: 'Turner Romanticism', emoji: '⛵', prompt: 'Romanticism oil painting in the style of J.M.W. Turner and Caspar David Friedrich, immense turbulent skies, sublime awe-inspiring nature', negative: 'tame indoor studio, clean geometric' },
        { name: 'Matisse Fauvism', emoji: '🐯', prompt: 'wild expressive Fauvism painting in the style of Henri Matisse, explosive non-naturalistic bold colors, passionate painterly freedom', negative: 'realistic subdued colors, monochrome' },
        { name: 'Constructivism', emoji: '📐', prompt: 'Russian Constructivism propaganda poster, dynamic diagonal typography, stark red black white palette, revolutionary industrial photomontage', negative: 'soft pastel flowers, decorative rococo' },
        { name: 'Rococo Opulence', emoji: '🪞', prompt: '18th-century French Rococo painting in the style of Fragonard and Boucher, lavish pastel pinks and golds, ornate gilded luxury, playful romance', negative: 'dark brutalist, stark minimalist, modern' },
        { name: 'Klimt Gold Leaf', emoji: '👑', prompt: 'Gustav Klimt Golden Phase masterpiece, shimmering gold leaf mosaic patterns, intricate decorative Byzantine ornamentation, sensual symbolism', negative: 'plain background, flat monochrome, photographic' },
        { name: 'Pre-Raphaelite', emoji: '🌿', prompt: 'Pre-Raphaelite masterpiece in the style of John William Waterhouse, romantic medieval legends, intense luminous jewel tones, botanical fidelity', negative: 'modern cartoon, rough sketch, dark low resolution' }
    ],

    '✨ Lighting & Atmosphere': [
        { name: 'Golden Hour Sunset', emoji: '🌅', prompt: 'warm setting sun, long golden hour shadows, rich honey-amber atmospheric glow, gentle cinematic lens flare, natural warmth', negative: 'overcast, harsh blue midday flash' },
        { name: 'Blue Hour Twilight', emoji: '🌌', prompt: 'peaceful blue hour dusk, soft ambient evening glow, deep indigo skies, warm interior window accents, serene cinematic stillness', negative: 'harsh noon sun, high contrast shadows' },
        { name: 'Volumetric God Rays', emoji: '✨', prompt: 'spectacular volumetric god rays streaming through dust motes, dramatic cinematic crepuscular beams, atmospheric forest cathedral haze', negative: 'flat ambient light, overcast' },
        { name: 'Bioluminescence', emoji: '🪼', prompt: 'luminous bioluminescent neon glow, Avatar Pandora jungle aesthetic, glowing flora and fauna in deep mystical darkness, radiant cyan and violet', negative: 'harsh daylight, washed out' },
        { name: 'Cyber Neon Dual-Tone', emoji: '💡', prompt: 'vibrant dual-tone magenta and cyan neon backlight, sleek reflective edge lighting, dark atmospheric studio environment', negative: 'natural warm sunlight, flat' },
        { name: 'Ethereal Dreamlight', emoji: '🧚', prompt: 'soft diffused dreamlike glow, gentle bloom, sparkling ambient bokeh particles, fairy tale pastel illumination, soft focus highlights', negative: 'harsh dark shadows, gritty' },
        { name: 'Dramatic Silhouette', emoji: '👤', prompt: 'stark back-lit silhouette against an immense radiant sky, high contrast, dramatic minimalist composition, edge contour glow', negative: 'front lit, washed out details' },
        { name: 'Moody Fog & Mist', emoji: '🌫️', prompt: 'dense atmospheric rolling fog, soft diffused cinematic mist, mysterious depth fading into white haze, silent melancholic beauty', negative: 'harsh clear noon sun, high contrast' },
        { name: 'Strobe Flash Party', emoji: '⚡', prompt: 'vivid strobe light photography, high-energy party motion, dynamic colored gel lights, motion trails and sharp freeze-frame contrast', negative: 'peaceful quiet natural daylight' },
        { name: 'Candlelight Warmth', emoji: '🕯️', prompt: 'soft flickering candlelight illumination, deep rich warm amber glow, intimate dark room atmosphere, soft dancing shadows', negative: 'harsh fluorescent overhead light, daylight' },
        { name: 'Aurora Borealis', emoji: '🌠', prompt: 'shimmering green and purple Aurora Borealis Northern Lights dancing across a starry night sky, reflecting on icy water', negative: 'cloudy overcast, daytime sunlight' },
        { name: 'Noon Desert Sun', emoji: '☀️', prompt: 'harsh blazing midday desert sun, intense hard-edged shadows, blinding bright highlights, heat wave mirage shimmer, searing clarity', negative: 'soft diffused light, cool blue tones, night' },
        { name: 'Studio Rim Light', emoji: '💡', prompt: 'dramatic razor-sharp rim backlighting, luminous edge contour highlights tracing the subject silhouette in a pitch-black studio', negative: 'flat frontal flash, washed out background' },
        { name: 'Underwater Caustics', emoji: '🤿', prompt: 'submerged underwater perspective, undulating sunlight caustic patterns dancing across surfaces, deep turquoise gradient, floating bubbles', negative: 'dry land, harsh dry shadows' },
        { name: 'Lightning Storm', emoji: '🌩️', prompt: 'electric blue lightning flash splitting a stormy black sky, violent rain streaks, dramatic momentary illuminating flash', negative: 'sunny clear skies, peaceful calm' },
        { name: 'Cyberpunk Neon Rain', emoji: '🌧️', prompt: 'heavy atmospheric rain pouring through neon-illuminated city mist, glowing wet ground reflections, vaporous urban haze', negative: 'dry sunny daylight, rural countryside' }
    ],

    '🔭 Camera Angles & Lenses': [
        { name: 'Anamorphic 2.39:1', emoji: '🎥', prompt: 'anamorphic widescreen cinema lens, horizontal blue streak flare, 2.39:1 aspect ratio framing, shallow depth of field, oval bokeh highlights', negative: 'spherical lens, vertical video' },
        { name: 'Ultra-Wide 14mm', emoji: '🔭', prompt: 'ultra-wide angle 14mm lens perspective, expansive grand scale, dramatic foreground depth, towering architectural grandeur', negative: 'cropped close-up, telephoto compression' },
        { name: 'Tilt-Shift Miniature', emoji: '🏙️', prompt: 'tilt-shift miniature effect, selective narrow horizontal focus band, toy-like diorama scale perspective, vibrant saturation, high angle', negative: 'normal perspective, full focus plane' },
        { name: 'Fish-Eye Dynamic', emoji: '🌐', prompt: 'dramatic 180-degree fish-eye lens curvature, warped hemispherical perspective, dynamic extreme action framing, rounded edges', negative: 'flat rectilinear, telephoto' },
        { name: 'Isometric Cutaway', emoji: '📐', prompt: 'isometric 3D cutaway diorama, orthographic view, cross-section detail, clean miniature room modeling, architectural showcase', negative: 'perspective view, ground level camera' },
        { name: 'Low-Angle Hero Shot', emoji: '⚡', prompt: 'extreme low-angle hero perspective looking up, towering monumental stature, imposing powerful presence, epic sky background', negative: 'bird eye view, high angle looking down' },
        { name: 'First-Person POV', emoji: '👁️', prompt: 'first-person point of view (POV), hands visible interacting in the scene, immersive foreground perspective', negative: 'third person, portrait, wide exterior' },
        { name: 'Birds Eye Overhead', emoji: '🦅', prompt: 'steep high-angle perspective looking directly down from above, panoramic overview, expansive geometric ground patterns', negative: 'low angle looking up, eye level' },
        { name: 'Dutch Angle Tension', emoji: '📐', prompt: 'dramatic tilted Dutch angle framing, off-axis diagonal horizon, intense psychological tension, dynamic cinematography', negative: 'perfectly level horizon, flat static' },
        { name: 'Over-The-Shoulder', emoji: '👥', prompt: 'cinematic over-the-shoulder perspective, foreground shoulder out of focus, framed subject dialogue composition', negative: 'isolated portrait, aerial view' },
        { name: 'Extreme Close-Up', emoji: '🔬', prompt: 'extreme close-up macro framing, filling the frame with microscopic texture and focal intensity, razor-thin depth of field', negative: 'wide shot, distant full body' },
        { name: 'Telephoto 200mm', emoji: '🏔️', prompt: 'telephoto 200mm f/2.8 lens compression, flattened distance perspective, massive background scale towering behind subject, creamy bokeh', negative: 'wide angle distortion, fisheye' },
        { name: 'Dolly Zoom Vertigo', emoji: '🎬', prompt: 'vertigo effect dolly zoom perspective, warping background scale while foreground subject stays constant, psychological shock framing', negative: 'static standard photo' },
        { name: 'Worms Eye Ground', emoji: '🐛', prompt: 'extreme ground-level worm eye perspective looking up from the floor, towering monumental scale, dramatic floor textures', negative: 'eye level, bird eye view' },
        { name: 'Split Diopter Focus', emoji: '🔍', prompt: 'vintage cinema split-diopter shot, simultaneous tack-sharp focus on both extreme close-up foreground and distant background', negative: 'standard single focus plane, uniform blur' },
        { name: 'Rule of Thirds', emoji: '🎯', prompt: 'masterful rule-of-thirds composition, golden ratio framing, ample evocative negative space, balanced artistic storytelling', negative: 'centered passport mugshot, awkward crop' }
    ]
};

// Reactive filtered style library based on user search
const filteredStyleLibrary = computed(() => {
    if (!styleSearchTerm.value.trim()) return styleLibrary;
    const term = styleSearchTerm.value.toLowerCase().trim();
    const result = {};

    for (const [category, styles] of Object.entries(styleLibrary)) {
        const matching = styles.filter(s => 
            s.name.toLowerCase().includes(term) || 
            s.prompt.toLowerCase().includes(term) ||
            category.toLowerCase().includes(term)
        );
        if (matching.length > 0) {
            result[category] = matching;
        }
    }
    return result;
});

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
    nextTick(() => {
        hasHeaderTarget.value = !!document.getElementById('global-header-title-target') && !!document.getElementById('global-header-actions-target');
    });
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
