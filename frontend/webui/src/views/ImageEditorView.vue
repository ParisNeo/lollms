<template>
    <!-- TELEPORT EDITOR TOOLBAR TO GLOBAL HEADER -->
    <Teleport to="#global-header-title-target" v-if="isComponentMounted && hasHeaderTarget">
        <div class="flex items-center bg-gray-100/90 dark:bg-gray-800/90 rounded-2xl p-1 gap-1 pointer-events-auto shadow-inner border border-gray-200 dark:border-gray-700/70 backdrop-blur-md relative z-[100] max-w-full overflow-x-auto no-scrollbar">
            <template v-for="(group, gi) in toolGroups" :key="group.id">
                <div class="flex items-center gap-0.5 shrink-0">
                    <button 
                        v-for="t in toolsByGroup(group.id)" 
                        :key="t.id" 
                        @click.stop="setTool(t.id)" 
                        type="button"
                        class="p-2 rounded-xl transition-all transform active:scale-95 cursor-pointer flex items-center justify-center shrink-0"
                        :class="tool === t.id ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-md ring-1 ring-black/5' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'"
                        :title="`${t.name} (${t.shortcut})`"
                    >
                        <component :is="t.icon" class="w-4 h-4 pointer-events-none" />
                    </button>
                </div>
                <div v-if="gi < toolGroups.length - 1" class="h-5 w-px bg-gray-300 dark:bg-gray-600 shrink-0"></div>
            </template>
            <div class="h-5 w-px bg-gray-300 dark:bg-gray-600 shrink-0"></div>
            <button 
                @click.stop="showShortcutsHelp = !showShortcutsHelp"
                type="button"
                class="p-2 rounded-xl text-gray-500 hover:text-gray-800 dark:hover:text-gray-200 transition-all cursor-pointer shrink-0 font-black text-sm w-8 h-8 flex items-center justify-center"
                title="Keyboard Shortcuts (?)"
            >?</button>
        </div>
    </Teleport>

    <Teleport to="#global-header-actions-target" v-if="isComponentMounted && hasHeaderTarget">
        <div class="flex items-center gap-1.5 pointer-events-auto relative z-[100]">
            <!-- Undo / Redo Controls -->
            <button @click="undo" :disabled="historyIndex <= 0" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl disabled:opacity-30 transition-all text-gray-600 dark:text-gray-300" title="Undo (Ctrl+Z)"><IconUndo class="w-4 h-4" /></button>
            <button @click="redo" :disabled="historyIndex >= history.length - 1" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl disabled:opacity-30 transition-all text-gray-600 dark:text-gray-300" title="Redo (Ctrl+Y)"><IconRedo class="w-4 h-4" /></button>
            
            <div class="h-5 w-px bg-gray-200 dark:bg-gray-700 mx-1"></div>

            <button @click="saveProject" class="btn btn-secondary btn-sm h-8 px-3 rounded-xl flex items-center gap-1.5" title="Save Multi-Layer Project File (.json)">
                <IconFolder class="w-3.5 h-3.5 text-amber-500"/> <span class="hidden sm:inline text-xs font-bold">Project</span>
            </button>
            <button @click="openSaveModal" class="btn btn-primary btn-sm h-8 px-3 rounded-xl flex items-center gap-1.5 shadow-lg shadow-blue-500/20" title="Export / Save in chosen format">
                <IconSave class="w-3.5 h-3.5" /> <span class="hidden sm:inline text-xs font-bold">Save / Export</span>
            </button>
            
            <button @click="showMobileSidebar = !showMobileSidebar" class="lg:hidden btn btn-secondary p-1.5 ml-1 h-8 w-8 flex items-center justify-center rounded-xl"><IconAdjustmentsHorizontal class="w-4 h-4" /></button>
        </div>
    </Teleport>

    <div class="h-full flex flex-col bg-gray-100 dark:bg-gray-950 overflow-hidden relative select-none font-sans">
        
        <!-- Top Tool Options HUD (Floating Pill) -->
        <div class="absolute top-3 left-1/2 -translate-x-1/2 z-30 flex items-center gap-3 bg-white/95 dark:bg-gray-900/95 backdrop-blur-xl px-4 py-2 rounded-2xl shadow-2xl border border-gray-200/80 dark:border-gray-800 animate-in fade-in slide-in-from-top-3 max-w-[95vw] overflow-x-auto no-scrollbar">
            <div class="flex items-center gap-1.5 pr-2 border-r dark:border-gray-800 shrink-0">
                <span class="text-[9px] font-black uppercase tracking-widest text-primary">{{ currentToolName }}</span>
            </div>

            <!-- Dynamic Color Palette & Swatches Studio -->
            <div class="flex items-center gap-1.5 shrink-0 relative" v-if="['brush', 'line', 'rect', 'circle', 'text', 'gradient'].includes(tool)">
                <!-- Current Active Color Box with Quick Picker -->
                <div 
                    @click="isPaletteStudioOpen = !isPaletteStudioOpen" 
                    class="relative w-7 h-7 rounded-xl overflow-hidden border-2 border-black/20 dark:border-white/20 shadow-md cursor-pointer hover:scale-105 transition-transform flex items-center justify-center"
                    :style="{ backgroundColor: color }"
                    :title="`Current Color: ${color} (Click to open Color Studio)`"
                >
                    <span class="text-[8px] font-black mix-blend-difference text-white">🎨</span>
                </div>

                <!-- Live Swatch Strip (Active Palette) -->
                <div class="hidden md:flex items-center gap-1 max-w-[200px] overflow-x-auto no-scrollbar py-0.5">
                    <button 
                        v-for="swatch in activePaletteColors" 
                        :key="swatch" 
                        @click="selectColor(swatch)" 
                        class="w-4.5 h-4.5 rounded-lg border border-black/10 dark:border-white/10 hover:scale-115 transition-all shrink-0 shadow-xs" 
                        :class="color.toLowerCase() === swatch.toLowerCase() ? 'ring-2 ring-blue-500 scale-110 z-10' : ''"
                        :style="{ backgroundColor: swatch }"
                        :title="swatch"
                    ></button>
                </div>

                <!-- Palette Studio Popover Button -->
                <button 
                    @click="isPaletteStudioOpen = !isPaletteStudioOpen" 
                    class="px-2 py-1 text-[9px] font-black uppercase tracking-wider rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors flex items-center gap-1"
                >
                    <span>{{ selectedPaletteName }}</span>
                    <IconChevronDown class="w-3 h-3 transition-transform" :class="{'rotate-180': isPaletteStudioOpen}" />
                </button>

                <!-- Floating Color & Palette Studio Popover -->
                <div 
                    v-if="isPaletteStudioOpen" 
                    v-on-click-outside="() => isPaletteStudioOpen = false"
                    class="absolute top-full left-0 mt-3 w-80 bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-800 p-4 space-y-4 z-50 animate-in fade-in slide-in-from-top-2"
                >
                    <!-- Header -->
                    <div class="flex items-center justify-between border-b dark:border-gray-800 pb-2.5">
                        <div class="flex items-center gap-2">
                            <span class="text-[10px] font-black uppercase tracking-widest text-primary">Color Studio</span>
                            <span class="text-[9px] font-mono font-bold text-gray-400 bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">{{ activePaletteColors.length }} Swatches</span>
                        </div>
                        <button @click="isPaletteStudioOpen = false" class="p-1 text-gray-400 hover:text-red-500">
                            <IconXMark class="w-4 h-4" />
                        </button>
                    </div>

                    <!-- Category Selector -->
                    <div class="space-y-1">
                        <label class="text-[9px] font-black uppercase text-gray-400 tracking-wider block">Palette Theme</label>
                        <select v-model="selectedPaletteName" class="input-field !text-xs !py-1.5 w-full bg-gray-50 dark:bg-gray-800">
                            <option value="Essentials">🌟 Essentials Palette</option>
                            <option value="Custom">⭐ My Custom Palette (Saved)</option>
                            <option value="Extracted" v-if="extractedPalette.length > 0">📸 Extracted from Canvas</option>
                            <option value="Skin & Portrait">👤 Skin & Portrait Tones</option>
                            <option value="Cyberpunk Neon">🌃 Cyberpunk Neon</option>
                            <option value="Earth & Nature">🌿 Earth & Forest</option>
                            <option value="Pastel Dreams">🌸 Pastel Dreams</option>
                            <option value="Vintage Retro">🎞️ 70s Vintage Retro</option>
                            <option value="Manga & Comic">💥 Manga & Comic Inks</option>
                            <option value="Monochrome Shading">⚫ Monochrome Shading</option>
                        </select>
                    </div>

                    <!-- Swatches Grid -->
                    <div class="space-y-1.5">
                        <div class="grid grid-cols-6 gap-2 p-2 bg-gray-50 dark:bg-gray-950/60 rounded-xl border dark:border-gray-800 max-h-40 overflow-y-auto custom-scrollbar">
                            <div 
                                v-for="(swatch, idx) in activePaletteColors" 
                                :key="swatch + idx"
                                class="group/swatch relative aspect-square rounded-lg border border-black/15 dark:border-white/15 cursor-pointer hover:scale-110 transition-transform shadow-xs flex items-center justify-center"
                                :class="color.toLowerCase() === swatch.toLowerCase() ? 'ring-2 ring-blue-500 ring-offset-2 dark:ring-offset-gray-900' : ''"
                                :style="{ backgroundColor: swatch }"
                                @click="selectColor(swatch)"
                                :title="swatch"
                            >
                                <button 
                                    v-if="selectedPaletteName === 'Custom'" 
                                    @click.stop="removeColorFromCustomPalette(idx)" 
                                    class="absolute -top-1 -right-1 bg-red-600 text-white rounded-full w-3.5 h-3.5 flex items-center justify-center text-[8px] opacity-0 group-hover/swatch:opacity-100 transition-opacity shadow"
                                    title="Delete Swatch"
                                >
                                    ✕
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Interactive Inputs & Tools -->
                    <div class="space-y-2.5 pt-1 border-t dark:border-gray-800">
                        <div class="flex items-center gap-2">
                            <!-- Native Color Picker Trigger -->
                            <div class="relative w-9 h-9 rounded-xl overflow-hidden border dark:border-gray-700 shrink-0 shadow-sm" :style="{ backgroundColor: color }">
                                <input type="color" v-model="color" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full">
                            </div>
                            
                            <!-- Manual Hex Text Input -->
                            <div class="relative grow">
                                <input 
                                    v-model="color" 
                                    type="text" 
                                    class="input-field !text-xs !py-2 font-mono uppercase font-bold w-full pl-6"
                                    placeholder="#RRGGBB"
                                />
                                <span class="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 font-mono text-xs">#</span>
                            </div>

                            <!-- Add to Custom Palette Button -->
                            <button 
                                @click="addColorToCustomPalette(color)"
                                class="btn btn-secondary btn-sm h-9 px-3 text-xs flex items-center gap-1 font-bold shrink-0"
                                title="Save current color to My Custom Palette"
                            >
                                <IconPlus class="w-3.5 h-3.5 text-blue-500" />
                                <span>Save</span>
                            </button>
                        </div>

                        <!-- One-Click Palette Extractor from Image -->
                        <button 
                            @click="extractPaletteFromCanvas" 
                            class="btn btn-secondary btn-xs w-full py-2 flex items-center justify-center gap-1.5 font-bold uppercase text-[9px] tracking-wider"
                        >
                            <span>📸</span> Extract Dominant Palette from Image
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- Secondary Color picker (for Gradients) -->
            <div class="flex items-center gap-1.5 shrink-0" v-if="tool === 'gradient'">
                <span class="text-[9px] font-bold text-gray-400 uppercase">To</span>
                <div class="relative w-6 h-6 rounded-lg overflow-hidden border dark:border-gray-700 shadow-sm cursor-pointer" :style="{ backgroundColor: secondaryColor }">
                    <input type="color" v-model="secondaryColor" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full">
                </div>
            </div>

            <!-- Size, Thickness & Tolerance Slider Controls -->
            <div class="flex items-center gap-2 shrink-0" v-if="['brush', 'eraser', 'line', 'rect', 'circle', 'text', 'clone', 'wand', 'colorkey', 'fill', 'heal', 'dodge', 'burn', 'smudge'].includes(tool)">
                <span class="text-[9px] font-black text-gray-400 uppercase tracking-widest">
                    {{ (tool === 'wand' || tool === 'colorkey' || tool === 'fill') ? 'Tolerance' : 'Size' }}
                </span>
                <input 
                    type="range" 
                    v-model.number="brushSize" 
                    :min="1" 
                    :max="(tool === 'wand' || tool === 'colorkey' || tool === 'fill') ? 100 : 300" 
                    class="w-20 sm:w-28 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                >
                <span class="text-[9px] font-mono font-bold w-7 text-center bg-gray-100 dark:bg-gray-800 py-0.5 rounded">{{ brushSize }}</span>
            </div>

            <!-- Phase 2 — Selection ops -->
            <div v-if="['marquee', 'ellipse-select', 'lasso'].includes(tool)" class="flex items-center gap-1 shrink-0 border-l dark:border-gray-800 pl-2">
                <button @click="selectAll" class="btn btn-xs btn-secondary h-7 text-[10px]" title="Select All (Ctrl+A)">All</button>
                <button @click="deselectAll" class="btn btn-xs btn-secondary h-7 text-[10px]" title="Deselect (Esc)">None</button>
                <button v-if="selection.active" @click="invertSelection" class="btn btn-xs btn-secondary h-7 text-[10px]" :class="{'!bg-blue-100 dark:!bg-blue-900/40 !text-blue-600': selection.inverted}" title="Invert selection">Invert</button>
                <button v-if="selection.active" @click="deleteSelectionContent" class="btn btn-xs btn-secondary h-7 text-[10px] !text-red-500" title="Delete selection contents">Delete</button>
                <button v-if="selection.active" @click="selectionToMask" class="btn btn-xs btn-secondary h-7 text-[10px] !text-purple-500" title="Convert selection → inpaint mask">→Mask</button>
            </div>

            <!-- Phase 2 — Crop controls -->
            <div v-if="tool === 'crop'" class="flex items-center gap-1.5 shrink-0 border-l dark:border-gray-800 pl-2">
                <select v-model="cropAspect" class="input-field !text-[10px] !py-1 !px-1.5" title="Crop aspect ratio">
                    <option :value="null">Free</option>
                    <option :value="1">1:1</option>
                    <option :value="16/9">16:9</option>
                    <option :value="9/16">9:16</option>
                    <option :value="4/3">4:3</option>
                    <option :value="3/2">3:2</option>
                    <option :value="1536/1088">A4 Portrait</option>
                    <option :value="1088/1536">A4 Landscape</option>
                    <option :value="1408/1088">Letter</option>
                </select>
                <button v-if="cropRect" @click="applyCrop" class="btn btn-xs btn-primary h-7 text-[10px]">Apply Crop</button>
                <button v-if="cropRect" @click="cancelCrop" class="btn btn-xs btn-secondary h-7 text-[10px]">Cancel</button>
            </div>

            <!-- Brush Hardness Settings -->
            <div class="flex items-center gap-2 shrink-0" v-if="['brush', 'eraser'].includes(tool)">
                <span class="text-[9px] font-black text-gray-400 uppercase tracking-widest">Hardness</span>
                <input 
                    type="range" 
                    v-model.number="brushHardness" 
                    min="0" 
                    max="1" 
                    step="0.05" 
                    class="w-16 sm:w-20 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                >
            </div>

            <!-- Clone Stamp Anchor Configuration -->
            <div v-if="tool === 'clone'" class="flex items-center gap-2 border-l dark:border-gray-800 pl-3 shrink-0">
                <button @click="settingCloneAnchor = true" class="btn btn-xs h-6 px-2 text-[10px]" :class="settingCloneAnchor ? 'btn-primary' : 'btn-secondary'">
                    {{ settingCloneAnchor ? 'Click to Set Source...' : 'Set Anchor' }}
                </button>
            </div>

            <!-- Inpaint Mask Actions -->
            <div v-if="activeLayerId === 'mask'" class="flex items-center gap-2 border-l dark:border-gray-800 pl-3 shrink-0">
                <button @click="clearMask" class="btn btn-xs btn-secondary h-6 text-[10px] text-red-500">
                    Clear Mask
                </button>
                <button @click="invertMask" class="btn btn-xs btn-secondary h-6 text-[10px]">
                    Invert
                </button>
            </div>
        </div>

        <div class="grow flex min-h-0 relative overflow-hidden">
            <!-- Central Viewport & Canvas Composition Stack -->
            <main 
                ref="containerRef" 
                class="grow bg-gray-200 dark:bg-black relative overflow-hidden flex items-center justify-center cursor-crosshair pattern-grid" 
                @wheel.prevent="handleWheel" 
                @mousedown="startAction" 
                @mousemove="handleMove" 
                @mouseup="endAction" 
                @mouseleave="endAction"
            >
                <!-- ── SELECTION ACTIVE BADGE ── -->
                <div v-if="selection.active && !textEditor.visible" class="absolute top-[4.4rem] left-1/2 -translate-x-1/2 z-[25] bg-blue-600 text-white text-[9px] font-black uppercase tracking-widest px-3 py-1 rounded-full shadow-lg flex items-center gap-2 pointer-events-none">
                    <span>{{ selection.inverted ? 'Inverted' : 'Selection' }}</span>
                    <span class="opacity-60">·</span>
                    <span class="font-mono">{{ Math.round(selection.bounds?.w || 0) }}×{{ Math.round(selection.bounds?.h || 0) }}</span>
                </div>

                <!-- ── DOCUMENT TABS ── -->
                <div class="absolute top-3 left-3 z-20 flex items-center gap-1 bg-white/90 dark:bg-gray-900/90 backdrop-blur-xl rounded-xl shadow-lg border border-gray-200 dark:border-gray-800 p-1 max-w-[55vw] overflow-x-auto no-scrollbar">
                    <button 
                        v-for="(doc, idx) in docs" 
                        :key="doc.id"
                        @click="switchToDoc(idx)"
                        @dblclick.prevent="renameActiveDoc()"
                        class="px-2.5 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1 whitespace-nowrap transition-colors"
                        :class="activeDocIndex === idx ? 'bg-blue-600 text-white shadow-sm' : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'"
                        :title="doc.name + (doc.dirty ? ' • unsaved' : '')"
                    >
                        <span v-if="doc.dirty" class="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0"></span>
                        <span>{{ doc.name }}</span>
                        <span 
                            v-if="docs.length > 1" 
                            @click.stop="closeDocTab(idx)" 
                            class="ml-1 opacity-60 hover:opacity-100 font-black"
                            title="Close tab"
                        >×</span>
                    </button>
                    <button @click="openNewDocTab" class="p-1 rounded-lg text-gray-400 hover:text-blue-500 transition-colors shrink-0" title="New Tab">
                        <IconPlus class="w-3.5 h-3.5" />
                    </button>
                </div>

                <!-- ── PHOTOSHOP-STYLE VERTICAL TOOL PALETTE (LEFT) ── -->
                <div
                    @mousedown.stop
                    class="hidden lg:flex flex-col absolute left-3 top-20 z-20 bg-white/95 dark:bg-gray-900/95 backdrop-blur-xl rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-800 p-1.5 gap-1.5 max-h-[calc(100vh-14rem)] overflow-y-auto custom-scrollbar"
                >
                    <div class="grid grid-cols-2 gap-1">
                        <template v-for="(t, idx) in tools" :key="'toolpalette-'+t.id">
                            <!-- Group divider: spans a full grid row when the tool group changes -->
                            <div
                                v-if="idx > 0 && tools[idx - 1].group !== t.group"
                                class="col-span-2 h-px bg-gray-200 dark:bg-gray-700/70 my-0.5"
                            ></div>
                            <button
                                @click.stop="setTool(t.id)"
                                type="button"
                                class="group/tool relative w-9 h-9 rounded-lg flex items-center justify-center transition-all active:scale-95"
                                :class="tool === t.id ? 'bg-blue-600 text-white shadow-md ring-1 ring-black/5 scale-105' : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-800 dark:hover:text-gray-200'"
                                :title="`${t.name} (${t.shortcut})`"
                            >
                                <component :is="t.icon" class="w-[18px] h-[18px] pointer-events-none" />
                                <span
                                    class="absolute -bottom-0.5 -right-0.5 min-w-[12px] px-1 py-[1px] rounded-md text-[8px] font-black leading-none pointer-events-none transition-opacity duration-150"
                                    :class="tool === t.id ? 'bg-white/25 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-500 opacity-0 group-hover/tool:opacity-100'"
                                >{{ t.shortcut }}</span>
                            </button>
                        </template>
                    </div>

                    <!-- Foreground / Background Color Swatches (X swap · D reset) -->
                    <div class="pt-2 mt-0.5 border-t dark:border-gray-700 flex flex-col items-center gap-1">
                        <div class="relative w-11 h-10">
                            <!-- Background color (bottom-right) -->
                            <div class="absolute bottom-0 right-0 w-7 h-7 rounded-md border-2 border-white dark:border-gray-800 shadow-md overflow-hidden cursor-pointer z-0" :style="{ backgroundColor: secondaryColor }" title="Background Color — click to pick">
                                <input type="color" v-model="secondaryColor" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full">
                            </div>
                            <!-- Foreground color (top-left) -->
                            <div class="absolute top-0 left-0 w-7 h-7 rounded-md border-2 border-white dark:border-gray-800 shadow-md overflow-hidden cursor-pointer z-10" :style="{ backgroundColor: color }" title="Foreground Color — click to pick">
                                <input type="color" v-model="color" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full">
                            </div>
                            <!-- Swap arrow -->
                            <button @click.stop="swapColors" class="absolute -top-0.5 right-0 text-[10px] leading-none text-gray-400 hover:text-blue-500 font-bold" title="Swap Colors (X)">⇄</button>
                        </div>
                        <div class="flex items-center gap-1">
                            <button @click.stop="swapColors" class="text-[8px] px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-blue-100 dark:hover:bg-blue-900/30 hover:text-blue-600 font-bold" title="Swap Foreground / Background (X)">X</button>
                            <button @click.stop="resetColors" class="text-[8px] px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-blue-100 dark:hover:bg-blue-900/30 hover:text-blue-600 font-bold" title="Reset to Black / White (D)">D</button>
                        </div>
                    </div>
                </div>

                <!-- Task Progress Overlay -->
                <transition name="fade">
                    <div v-if="isProcessingTask" class="absolute inset-0 z-[100] flex flex-col items-center justify-center bg-gray-900/60 backdrop-blur-md">
                        <div class="w-72 bg-white dark:bg-gray-800 p-5 rounded-3xl border border-gray-200 dark:border-gray-700 shadow-2xl space-y-3">
                             <div class="flex justify-between items-center">
                                 <span class="text-[9px] font-black text-blue-500 uppercase tracking-[0.2em] animate-pulse">AI Synthesis</span>
                                 <span class="text-xs font-mono font-bold">{{ activeTask?.progress || 0 }}%</span>
                             </div>
                             <div class="h-2 w-full bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                                 <div class="h-full bg-gradient-to-r from-blue-500 to-indigo-600 transition-all duration-500" :style="{ width: `${activeTask?.progress || 0}%` }"></div>
                             </div>
                             <p class="text-[10px] text-gray-500 dark:text-gray-400 italic text-center truncate">{{ activeTask?.description || 'Processing...' }}</p>
                        </div>
                    </div>
                </transition>

                <!-- Canvas Wrapper Stack -->
                <!-- Layer Composition Container -->
                <div :style="combinedCanvasStyle" class="relative shadow-2xl origin-center canvas-stack">
                    <!-- Base Sizing Anchor Canvas -->
                    <canvas 
                        ref="imageCanvasRef" 
                        :width="canvasWidth" 
                        :height="canvasHeight" 
                        class="block bg-transparent layer-canvas"
                    ></canvas>

                    <!-- Render All Stacked Layers with Individual Reactivity -->
                    <template v-for="layer in layers" :key="layer.id">
                        <canvas 
                            :ref="el => setLayerCanvasRef(layer, el)" 
                            v-show="layer.visible"
                            :width="canvasWidth" 
                            :height="canvasHeight"
                            class="absolute inset-0 layer-canvas" 
                            :style="{ 
                                zIndex: layer.order, 
                                opacity: layer.opacity,
                                mixBlendMode: layer.blendMode || 'normal',
                                filter: getLayerFilterCss(layer)
                            }"
                        ></canvas>
                    </template>

                    <!-- Inpainting Mask Canvas Layer -->
                    <canvas 
                        ref="maskCanvasRef" 
                        v-show="activeLayerId === 'mask' || useInpaintMask"
                        :width="canvasWidth" 
                        :height="canvasHeight"
                        class="absolute inset-0 opacity-50 layer-canvas pointer-events-none" 
                        style="z-index: 998"
                    ></canvas>

                    <!-- Shape & Interactive Drawing Preview Layer -->
                    <canvas 
                        ref="previewCanvasRef" 
                        :width="canvasWidth" 
                        :height="canvasHeight"
                        class="absolute inset-0 pointer-events-none layer-canvas" 
                        style="z-index: 1000"
                    ></canvas>
                    
                    <!-- Interactive Cursor Reticle -->
                    <div 
                        v-show="showCursor" 
                        class="absolute pointer-events-none rounded-full border border-black/60 bg-white/20 z-[1100] transform -translate-x-1/2 -translate-y-1/2 transition-none" 
                        :style="{ width: `${brushSize}px`, height: `${brushSize}px`, left: `${cursorX}px`, top: `${cursorY}px` }"
                    ></div>

                    <!-- Clone Anchor Marker -->
                    <div v-if="cloneAnchor" class="absolute pointer-events-none z-[1100] flex items-center justify-center transform -translate-x-1/2 -translate-y-1/2" :style="{ left: `${cloneAnchor.x}px`, top: `${cloneAnchor.y}px` }">
                        <div class="w-5 h-5 border-2 border-emerald-500 rounded-full animate-ping"></div>
                        <div class="absolute w-px h-8 bg-emerald-500"></div>
                        <div class="absolute h-px w-8 bg-emerald-500"></div>
                    </div>
                </div>

                <!-- ── HISTORY TIMELINE ── -->
                <div 
                    v-if="isHistoryStripVisible && history.length > 0"
                    class="absolute bottom-16 left-1/2 -translate-x-1/2 z-20 bg-white/95 dark:bg-gray-900/95 backdrop-blur-xl rounded-xl shadow-2xl border border-gray-200 dark:border-gray-800 p-2 max-w-[85vw] overflow-x-auto no-scrollbar flex items-center gap-1.5"
                >
                    <div class="flex flex-col items-start shrink-0 pr-2 border-r dark:border-gray-800">
                        <span class="text-[9px] font-black uppercase tracking-widest text-gray-400">History</span>
                        <button @click="nameCurrentSnapshot" class="text-[8px] font-bold text-blue-600 hover:underline uppercase">Name</button>
                    </div>
                    <button
                        v-for="(snap, idx) in history"
                        :key="idx"
                        @click="jumpToHistory(idx)"
                        class="shrink-0 w-14 h-14 rounded-lg overflow-hidden border-2 transition-all relative"
                        :class="idx === historyIndex ? 'border-blue-500 ring-2 ring-blue-500/20' : 'border-transparent hover:border-gray-300 dark:hover:border-gray-600'"
                        :title="snap.name || `Step ${idx + 1}`"
                    >
                        <img v-if="snap.thumb" :src="snap.thumb" class="w-full h-full object-cover" />
                        <span v-else class="text-[9px] font-mono text-gray-400 w-full h-full flex items-center justify-center bg-gray-50 dark:bg-gray-800">{{ idx + 1 }}</span>
                        <span v-if="snap.pinned" class="absolute top-0.5 right-0.5 bg-amber-500 text-white text-[7px] font-black px-1 rounded">📌</span>
                    </button>
                </div>

                <!-- Viewport Navigation HUD (Bottom Left) -->
                <div class="absolute bottom-4 left-4 bg-white/90 dark:bg-gray-900/90 backdrop-blur-md rounded-2xl shadow-xl p-1.5 flex items-center gap-1.5 z-10 border dark:border-gray-800">
                    <button @click="zoomOut" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg" title="Zoom Out (Ctrl/Alt + Wheel)"><IconMinus class="w-4 h-4" /></button>
                    <span @click="resetZoom" class="text-[10px] font-black font-mono w-12 text-center select-none cursor-pointer hover:text-blue-500" title="Click to reset to 100%">{{ Math.round(zoom * 100) }}%</span>
                    <button @click="zoomIn" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg" title="Zoom In (Ctrl/Alt + Wheel)"><IconPlus class="w-4 h-4" /></button>
                    <input type="range" min="0.1" max="8" step="0.05" v-model.number="zoom" class="w-16 h-1 accent-blue-500 cursor-pointer hidden sm:block" title="Navigator Zoom" />
                    <button @click="fitToScreen" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg text-blue-500 font-bold text-xs" title="Fit Canvas to View">Fit</button>
                    <button @click="resetZoom" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg text-gray-500 font-bold text-xs" title="100% 1:1">1:1</button>
                    <button @click="isHistoryStripVisible = !isHistoryStripVisible" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors" :class="isHistoryStripVisible ? 'text-blue-500 bg-blue-50 dark:bg-blue-900/30' : 'text-gray-500'" title="Toggle History Timeline"><IconClock class="w-4 h-4" /></button>
                </div>
            </main>

            <!-- Right Inspector Sidebar (Layers, Transform & AI Controls) -->
            <aside 
                class="absolute inset-y-0 right-0 z-30 w-80 bg-white dark:bg-gray-900 border-l dark:border-gray-800 transform transition-transform lg:relative lg:translate-x-0 flex flex-col shadow-2xl"
                :class="showMobileSidebar ? 'translate-x-0' : 'translate-x-full'"
            >
                <!-- Inspector Tabs -->
                <div class="p-3 border-b dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50 flex items-center justify-between">
                    <div class="flex items-center gap-1 bg-gray-200/60 dark:bg-gray-800 p-1 rounded-xl w-full">
                        <button 
                            @click="activeInspectorTab = 'layers'" 
                            class="flex-1 py-1 text-[10px] font-black uppercase tracking-wider rounded-lg transition-all"
                            :class="activeInspectorTab === 'layers' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                        >
                            Layers
                        </button>
                        <button 
                            @click="activeInspectorTab = 'transform'" 
                            class="flex-1 py-1 text-[10px] font-black uppercase tracking-wider rounded-lg transition-all"
                            :class="activeInspectorTab === 'transform' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                        >
                            Transform
                        </button>
                        <button 
                            @click="activeInspectorTab = 'adjust'" 
                            class="flex-1 py-1 text-[10px] font-black uppercase tracking-wider rounded-lg transition-all"
                            :class="activeInspectorTab === 'adjust' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                        >
                            Adjust
                        </button>
                        <button 
                            @click="activeInspectorTab = 'ai'" 
                            class="flex-1 py-1 text-[10px] font-black uppercase tracking-wider rounded-lg transition-all"
                            :class="activeInspectorTab === 'ai' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                        >
                            AI Studio
                        </button>
                    </div>
                </div>
                
                <!-- Inspector Body -->
                <div class="grow overflow-y-auto custom-scrollbar p-4 space-y-5">
                    
                    <!-- ── TAB 1: LAYER STACK MANAGER ── -->
                    <div v-show="activeInspectorTab === 'layers'" class="space-y-4">
                        <div class="flex items-center justify-between">
                            <span class="text-[9px] font-black text-gray-400 uppercase tracking-widest">Stack Layers ({{ layers.length }})</span>
                            <div class="flex items-center gap-1">
                                <button @click="addNewLayer()" class="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 text-blue-500 rounded-lg" title="Add Layer"><IconPlus class="w-4 h-4"/></button>
                                <button @click="duplicateActiveLayer" class="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 rounded-lg" title="Duplicate Layer"><IconCopy class="w-4 h-4"/></button>
                                <button @click="mergeLayerDown" :disabled="layers.length <= 1 || activeLayerId === 'base'" class="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 disabled:opacity-30 rounded-lg" title="Merge Down"><IconArrowDownTray class="w-4 h-4"/></button>
                            </div>
                        </div>
                        
                        <!-- Layer List -->
                        <div class="space-y-1.5">
                            <!-- AI Inpainting Mask Virtual Layer -->
                            <div 
                                @click="activeLayerId = 'mask'" 
                                class="layer-item group" 
                                :class="{'active !border-purple-500 !bg-purple-50 dark:!bg-purple-950/30': activeLayerId === 'mask'}"
                            >
                                <div class="w-6 h-6 rounded-lg bg-purple-100 dark:bg-purple-900/40 text-purple-600 flex items-center justify-center shrink-0">
                                    <IconPencil class="w-3.5 h-3.5"/>
                                </div>
                                <span class="text-xs font-black truncate grow text-purple-700 dark:text-purple-300">Inpaint Selection Mask</span>
                            </div>

                            <!-- User Graphic Layers (draggable, thumbnails, lock, inline rename) -->
                            <div 
                                v-for="layer in sortedLayers" 
                                :key="layer.id" 
                                draggable="true"
                                @dragstart="onLayerDragStart(layer, $event)"
                                @dragover="onLayerDragOver($event)"
                                @drop="onLayerDrop(layer, $event)"
                                @dragend="onLayerDragEnd"
                                @click="activeLayerId = layer.id" 
                                class="layer-item group" 
                                :class="{
                                    'active': activeLayerId === layer.id,
                                    'opacity-40': draggingLayerId === layer.id,
                                    'ring-2 ring-amber-400': dragOverLayerId === layer.id && draggingLayerId !== layer.id
                                }"
                            >
                                <!-- Drag handle -->
                                <div v-if="layer.id !== 'base'" class="text-gray-400 cursor-grab active:cursor-grabbing shrink-0">
                                    <svg class="w-3 h-3" viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.5"/><circle cx="15" cy="6" r="1.5"/><circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/><circle cx="9" cy="18" r="1.5"/><circle cx="15" cy="18" r="1.5"/></svg>
                                </div>

                                <!-- Thumbnail -->
                                <div class="w-8 h-8 rounded-md bg-gray-100 dark:bg-gray-800 border dark:border-gray-700 overflow-hidden shrink-0 flex items-center justify-center">
                                    <img v-if="layer.thumbnail" :src="layer.thumbnail" class="w-full h-full object-cover" />
                                    <span v-else class="text-[8px] font-mono text-gray-400">L{{ layer.order }}</span>
                                </div>

                                <!-- Visibility + Lock -->
                                <div class="flex items-center gap-0.5 shrink-0">
                                    <button @click.stop="toggleLayerVisibility(layer)" class="p-1 text-gray-400 hover:text-blue-500" :title="layer.visible ? 'Hide' : 'Show'">
                                        <IconEye v-if="layer.visible" class="w-3.5 h-3.5 text-blue-500"/>
                                        <IconEyeOff v-else class="w-3.5 h-3.5 text-gray-400"/>
                                    </button>
                                    <button 
                                        v-if="layer.id !== 'base'" 
                                        @click.stop="toggleLayerLock(layer)" 
                                        class="p-1 transition-colors" 
                                        :class="layer.locked ? 'text-amber-500' : 'text-gray-400 hover:text-amber-500'"
                                        :title="layer.locked ? 'Unlock layer' : 'Lock layer'"
                                    >
                                        <IconLock v-if="layer.locked" class="w-3 h-3"/>
                                        <IconLockOpen v-else class="w-3 h-3"/>
                                    </button>
                                </div>

                                <!-- Name / rename -->
                                <div class="grow min-w-0">
                                    <input 
                                        v-if="editingLayerId === layer.id" 
                                        v-model="editingLayerName" 
                                        type="text" 
                                        class="input-field !text-xs !py-0.5 w-full" 
                                        @blur="commitLayerRename(layer)" 
                                        @keydown.enter="commitLayerRename(layer)"
                                        @click.stop
                                        autofocus
                                    />
                                    <span 
                                        v-else 
                                        class="text-xs font-bold truncate block" 
                                        :class="layer.id === 'base' ? 'font-black' : ''"
                                        @dblclick.stop="startLayerRename(layer)"
                                        :title="layer.id === 'base' ? layer.name : 'Double-click to rename'"
                                    >{{ layer.name }}</span>
                                </div>

                                <button v-if="layer.id !== 'base'" @click.stop="deleteLayer(layer.id)" class="opacity-0 group-hover:opacity-100 p-1 text-red-400 hover:text-red-500 transition-opacity" title="Delete layer"><IconTrash class="w-3.5 h-3.5"/></button>
                            </div>
                        </div>

                        <!-- Active Layer Properties -->
                        <div v-if="activeLayerId !== 'mask'" class="p-3 bg-gray-50 dark:bg-gray-800/60 rounded-2xl border dark:border-gray-700/60 space-y-3">
                            <span class="text-[9px] font-black uppercase text-gray-400 tracking-widest block">Layer Properties ({{ activeLayer.name }})</span>
                            
                            <!-- Opacity Slider -->
                            <div class="space-y-1">
                                <div class="flex justify-between text-xs">
                                    <span class="text-[10px] font-bold text-gray-500">Opacity</span>
                                    <span class="font-mono text-[10px] font-bold">{{ Math.round(activeLayer.opacity * 100) }}%</span>
                                </div>
                                <input type="range" v-model.number="activeLayer.opacity" min="0" max="1" step="0.01" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                            </div>

                            <!-- Blend Mode -->
                            <div class="space-y-1">
                                <span class="text-[10px] font-bold text-gray-500 block">Blend Mode</span>
                                <select v-model="activeLayer.blendMode" class="input-field !text-xs !py-1 w-full bg-white dark:bg-gray-900">
                                    <option v-for="mode in blendModes" :key="mode.value" :value="mode.value">{{ mode.label }}</option>
                                </select>
                                <!-- Quick blend presets -->
                                <div class="flex items-center gap-1 flex-wrap pt-1">
                                    <button 
                                        v-for="b in blendQuickRow" 
                                        :key="b.value" 
                                        @click="activeLayer.blendMode = b.value; saveState();" 
                                        class="px-1.5 py-0.5 rounded text-[9px] font-bold border transition-colors"
                                        :class="activeLayer.blendMode === b.value ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600' : 'border-gray-200 dark:border-gray-700 text-gray-500 hover:border-gray-300'"
                                        :title="b.label"
                                    >{{ b.short }}</button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- ── TAB 2: GEOMETRY & TRANSFORMS ── -->
                    <div v-show="activeInspectorTab === 'transform'" class="space-y-4">
                        <span class="text-[9px] font-black text-gray-400 uppercase tracking-widest block">Canvas & Layer Transform</span>

                        <div class="grid grid-cols-2 gap-2">
                            <button @click="flipActiveLayerHorizontal" class="btn btn-secondary btn-sm text-xs flex items-center justify-center gap-1.5">
                                ↔ Flip Horiz
                            </button>
                            <button @click="flipActiveLayerVertical" class="btn btn-secondary btn-sm text-xs flex items-center justify-center gap-1.5">
                                ↕ Flip Vert
                            </button>
                            <button @click="rotateActiveLayer(90)" class="btn btn-secondary btn-sm text-xs flex items-center justify-center gap-1.5">
                                ↻ Rotate 90°
                            </button>
                            <button @click="rotateActiveLayer(-90)" class="btn btn-secondary btn-sm text-xs flex items-center justify-center gap-1.5">
                                ↺ Rotate -90°
                            </button>
                        </div>

                        <!-- Canvas Size Expansion (Outpaint prep) -->
                        <div class="p-3 bg-gray-50 dark:bg-gray-800/60 rounded-2xl border dark:border-gray-700/60 space-y-3">
                            <span class="text-[9px] font-black uppercase text-gray-400 tracking-widest block">Expand Canvas (Outpainting)</span>
                            <div class="grid grid-cols-2 gap-2">
                                <button @click="expandCanvas('horizontal', 256)" class="btn btn-secondary btn-xs py-2 font-bold">
                                    +256px Width
                                </button>
                                <button @click="expandCanvas('vertical', 256)" class="btn btn-secondary btn-xs py-2 font-bold">
                                    +256px Height
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- ── TAB 3: NON-DESTRUCTIVE ADJUSTMENTS ── -->
                    <div v-show="activeInspectorTab === 'adjust'" class="space-y-4">
                        <div class="flex justify-between items-center">
                            <span class="text-[9px] font-black text-gray-400 uppercase tracking-widest">Adjustments ({{ activeLayer.name }})</span>
                            <button @click="resetAdjustments" class="text-[9px] font-bold text-blue-500 uppercase hover:underline">Reset</button>
                        </div>

                        <div v-if="activeLayer && activeLayer.adjustments" class="space-y-3 p-3 bg-gray-50 dark:bg-gray-800/60 rounded-2xl border dark:border-gray-700/60">
                            <!-- Brightness -->
                            <div class="space-y-1">
                                <div class="flex justify-between text-xs">
                                    <span class="text-[10px] font-bold text-gray-500">Brightness</span>
                                    <span class="font-mono text-[10px]">{{ Math.round(activeLayer.adjustments.brightness * 100) }}%</span>
                                </div>
                                <input type="range" v-model.number="activeLayer.adjustments.brightness" @change="saveState" min="0" max="2" step="0.05" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                            </div>

                            <!-- Contrast -->
                            <div class="space-y-1">
                                <div class="flex justify-between text-xs">
                                    <span class="text-[10px] font-bold text-gray-500">Contrast</span>
                                    <span class="font-mono text-[10px]">{{ Math.round(activeLayer.adjustments.contrast * 100) }}%</span>
                                </div>
                                <input type="range" v-model.number="activeLayer.adjustments.contrast" @change="saveState" min="0" max="2" step="0.05" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                            </div>

                            <!-- Saturation -->
                            <div class="space-y-1">
                                <div class="flex justify-between text-xs">
                                    <span class="text-[10px] font-bold text-gray-500">Saturation</span>
                                    <span class="font-mono text-[10px]">{{ Math.round(activeLayer.adjustments.saturate * 100) }}%</span>
                                </div>
                                <input type="range" v-model.number="activeLayer.adjustments.saturate" @change="saveState" min="0" max="2" step="0.05" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                            </div>

                            <!-- Hue Rotation -->
                            <div class="space-y-1">
                                <div class="flex justify-between text-xs">
                                    <span class="text-[10px] font-bold text-gray-500">Hue Shift</span>
                                    <span class="font-mono text-[10px]">{{ activeLayer.adjustments.hueRotate }}°</span>
                                </div>
                                <input type="range" v-model.number="activeLayer.adjustments.hueRotate" @change="saveState" min="0" max="360" step="5" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                            </div>

                            <!-- Blur -->
                            <div class="space-y-1">
                                <div class="flex justify-between text-xs">
                                    <span class="text-[10px] font-bold text-gray-500">Blur Filter</span>
                                    <span class="font-mono text-[10px]">{{ activeLayer.adjustments.blur }}px</span>
                                </div>
                                <input type="range" v-model.number="activeLayer.adjustments.blur" @change="saveState" min="0" max="20" step="1" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                            </div>

                            <button @click="bakeAdjustmentsToActiveLayer" class="btn btn-secondary btn-xs w-full py-1.5 font-bold uppercase tracking-wider text-[9px] mt-2">
                                Bake Filter into Active Layer
                            </button>
                        </div>

                        <!-- ── DEDICATED COLOR / CHROMA KEY SUITE ── -->
                        <div class="space-y-3 p-3 bg-purple-50/50 dark:bg-purple-950/20 rounded-2xl border border-purple-200/70 dark:border-purple-900/40">
                            <div class="flex items-center justify-between">
                                <span class="text-[9px] font-black uppercase text-purple-700 dark:text-purple-300 tracking-wider flex items-center gap-1.5">
                                    <span>🎨</span> Chroma / Color Key (Transparency)
                                </span>
                            </div>

                            <!-- Key Color Selection -->
                            <div class="space-y-1.5">
                                <span class="text-[10px] font-bold text-gray-600 dark:text-gray-400 block">Key Color to Remove</span>
                                <div class="flex items-center gap-2">
                                    <div class="relative w-8 h-8 rounded-lg overflow-hidden border dark:border-gray-700 shadow-sm shrink-0" :style="{ backgroundColor: keyColor }">
                                        <input type="color" v-model="keyColor" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full">
                                    </div>
                                    <div class="grid grid-cols-5 gap-1 grow">
                                        <button 
                                            v-for="pk in [
                                                { hex: '#00FF00', label: 'Green', bg: 'bg-[#00FF00]' },
                                                { hex: '#FF00FF', label: 'Magenta', bg: 'bg-[#FF00FF]' },
                                                { hex: '#FFFFFF', label: 'White', bg: 'bg-white' },
                                                { hex: '#000000', label: 'Black', bg: 'bg-black' },
                                                { hex: '#0000FF', label: 'Blue', bg: 'bg-[#0000FF]' }
                                            ]"
                                            :key="pk.hex"
                                            @click="keyColor = pk.hex"
                                            class="h-6 rounded-md border border-black/10 dark:border-white/10 hover:scale-105 transition-transform"
                                            :class="pk.bg"
                                            :title="pk.label"
                                        ></button>
                                    </div>
                                </div>
                            </div>

                            <!-- Tolerance Slider -->
                            <div class="space-y-1">
                                <div class="flex justify-between text-xs">
                                    <span class="text-[10px] font-bold text-gray-500">Color Tolerance</span>
                                    <span class="font-mono text-[10px] font-bold">{{ keyTolerance }}%</span>
                                </div>
                                <input type="range" v-model.number="keyTolerance" min="1" max="80" step="1" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-purple-500">
                            </div>

                            <!-- Edge Softness / Feathering Slider -->
                            <div class="space-y-1">
                                <div class="flex justify-between text-xs">
                                    <span class="text-[10px] font-bold text-gray-500">Edge Feathering</span>
                                    <span class="font-mono text-[10px] font-bold">{{ keySoftness }}%</span>
                                </div>
                                <input type="range" v-model.number="keySoftness" min="0" max="50" step="1" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-purple-500">
                            </div>

                            <!-- Spill Removal Toggle -->
                            <div class="flex items-center justify-between pt-1">
                                <span class="text-[10px] font-bold text-gray-600 dark:text-gray-300">Fringe Spill Suppression</span>
                                <button @click="keySpillSuppression = !keySpillSuppression" :class="keySpillSuppression ? 'bg-purple-600' : 'bg-gray-300 dark:bg-gray-600'" class="w-8 h-4 rounded-full relative transition-colors">
                                    <div class="absolute top-0.5 w-3 h-3 bg-white rounded-full transition-all" :style="{ left: keySpillSuppression ? '16px' : '2px' }"></div>
                                </button>
                            </div>

                            <!-- Apply Button -->
                            <button @click="executeChromaKeyOnActiveLayer" class="btn btn-primary btn-xs w-full py-2 font-bold uppercase tracking-wider text-[9px] mt-1 shadow-md !bg-purple-600 hover:!bg-purple-700">
                                Apply Chroma Key to Layer
                            </button>
                        </div>
                    </div>

                    <!-- ── TAB 4: TARGETED AI LAYER EDITING & INPAINTING ── -->
                    <div v-show="activeInspectorTab === 'ai'" class="space-y-4">
                        <div class="flex items-center justify-between">
                            <span class="text-[9px] font-black text-gray-400 uppercase tracking-widest">AI Layer Studio</span>
                            <button @click="enhancePrompt" class="text-blue-500 hover:scale-110 transition-transform text-xs flex items-center gap-1 font-bold">
                                <IconSparkles class="w-3.5 h-3.5"/> Enhance
                            </button>
                        </div>

                        <!-- 1. Layer Target Selector -->
                        <div class="space-y-1.5 p-3 bg-blue-50/50 dark:bg-blue-900/20 rounded-2xl border border-blue-100 dark:border-blue-800/40">
                            <label class="text-[10px] font-black uppercase text-blue-700 dark:text-blue-300 tracking-wider block">AI Target Layer</label>
                            <select v-model="aiEditTarget" class="input-field !text-xs !py-1.5 w-full bg-white dark:bg-gray-900">
                                <option value="active">Active Layer ({{ activeLayer.name }})</option>
                                <option value="flattened">All Visible Layers (Full Canvas Composite)</option>
                            </select>
                            <p class="text-[9px] text-gray-500 dark:text-gray-400">
                                {{ aiEditTarget === 'active' ? `AI will analyze and edit only "${activeLayer.name}".` : 'AI will flatten all visible layers into a unified image.' }}
                            </p>
                        </div>

                        <!-- 2. Quick Preset Modifier Chips & Prompts -->
                        <div class="space-y-2">
                            <div class="flex items-center justify-between">
                                <label class="text-[10px] font-bold text-gray-500">Edit / Inpaint Prompt</label>
                                <span class="text-[8px] font-black uppercase text-gray-400">Quick Modifiers</span>
                            </div>

                            <!-- Quick Preset Buttons -->
                            <div class="flex items-center gap-1 overflow-x-auto no-scrollbar py-1">
                                <button 
                                    v-for="mod in quickEditModifiers" 
                                    :key="mod.label"
                                    @click="applyQuickModifier(mod)"
                                    class="px-2 py-0.5 rounded-full text-[9px] font-bold bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-blue-100 dark:hover:bg-blue-900/40 hover:text-blue-600 whitespace-nowrap transition-colors border border-gray-200 dark:border-gray-700/50"
                                >
                                    {{ mod.emoji }} {{ mod.label }}
                                </button>
                            </div>

                            <textarea 
                                v-model="prompt" 
                                rows="3" 
                                class="input-field w-full text-xs resize-none leading-relaxed" 
                                placeholder="Describe changes, additions, texture replacement, or inpainting details..."
                            ></textarea>
                        </div>

                        <div class="space-y-1.5">
                            <label class="text-[10px] font-bold text-gray-500">Negative Prompt (Optional)</label>
                            <input 
                                v-model="negativePrompt" 
                                type="text"
                                class="input-field w-full text-xs" 
                                placeholder="ugly, blurry, deformed, low resolution..."
                            />
                        </div>

                        <!-- 3. Edit Strength Slider -->
                        <div class="space-y-1 p-2.5 bg-gray-50 dark:bg-gray-800/60 rounded-xl border dark:border-gray-700/60">
                            <div class="flex justify-between items-center text-xs">
                                <span class="text-[10px] font-bold text-gray-500">Edit Strength (Denoising)</span>
                                <span class="font-mono text-[10px] font-bold text-blue-600 dark:text-blue-400">{{ editStrength.toFixed(2) }}</span>
                            </div>
                            <input 
                                type="range" 
                                v-model.number="editStrength" 
                                min="0.1" 
                                max="1.0" 
                                step="0.05" 
                                class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                            >
                            <div class="flex justify-between text-[8px] font-mono text-gray-400">
                                <span>0.10 (Subtle Tweaks)</span>
                                <span>1.00 (Total Redraw)</span>
                            </div>
                        </div>

                        <!-- 4. Output Mode & Inpaint Options -->
                        <div class="space-y-2 pt-1">
                            <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-800 p-2.5 rounded-xl border dark:border-gray-700">
                                <span class="text-[10px] font-bold text-gray-600 dark:text-gray-300">Apply Mask (Inpainting)</span>
                                <button @click="useInpaintMask = !useInpaintMask" :class="useInpaintMask ? 'bg-purple-600' : 'bg-gray-300 dark:bg-gray-600'" class="w-8 h-4 rounded-full relative transition-colors">
                                    <div class="absolute top-0.5 w-3 h-3 bg-white rounded-full transition-all" :style="{ left: useInpaintMask ? '16px' : '2px' }"></div>
                                </button>
                            </div>

                            <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-800 p-2.5 rounded-xl border dark:border-gray-700">
                                <span class="text-[10px] font-bold text-gray-600 dark:text-gray-300">Output as New Layer</span>
                                <button @click="outputAsNewLayer = !outputAsNewLayer" :class="outputAsNewLayer ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'" class="w-8 h-4 rounded-full relative transition-colors">
                                    <div class="absolute top-0.5 w-3 h-3 bg-white rounded-full transition-all" :style="{ left: outputAsNewLayer ? '16px' : '2px' }"></div>
                                </button>
                            </div>
                        </div>

                        <!-- AI Layer Chroma Key Mode -->
                        <div class="space-y-2 p-3 bg-gray-50 dark:bg-gray-800/80 rounded-xl border dark:border-gray-700">
                            <div class="flex items-center justify-between">
                                <span class="text-[10px] font-black uppercase tracking-wider text-gray-700 dark:text-gray-300">Auto Chroma-Key Screen</span>
                                <span class="text-[9px] font-mono text-purple-500 font-bold">{{ aiKeyScreenMode.toUpperCase() }}</span>
                            </div>
                            
                            <div class="grid grid-cols-4 gap-1">
                                <button 
                                    v-for="mode in [
                                        { id: 'magenta', label: 'Magenta #FF00FF', bg: 'bg-[#FF00FF] text-white' },
                                        { id: 'green', label: 'Green #00FF00', bg: 'bg-[#00FF00] text-black' },
                                        { id: 'white', label: 'White #FFFFFF', bg: 'bg-white text-black' },
                                        { id: 'off', label: 'None (Opaque)', bg: 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300' }
                                    ]"
                                    :key="mode.id"
                                    @click="aiKeyScreenMode = mode.id"
                                    class="py-1 text-[9px] font-bold rounded-lg border transition-all text-center"
                                    :class="aiKeyScreenMode === mode.id ? 'border-purple-500 ring-2 ring-purple-500/30 font-black scale-105 ' + mode.bg : 'border-gray-200 dark:border-gray-700 opacity-60 hover:opacity-100'"
                                >
                                    {{ mode.id }}
                                </button>
                            </div>
                            <p class="text-[9px] text-gray-400 leading-tight">
                                Generates against a solid color studio backdrop and automatically cuts out transparency before adding to your layer stack.
                            </p>
                        </div>

                        <div class="space-y-1.5">
                            <label class="text-[10px] font-bold text-gray-500">Active Model</label>
                            <select v-model="selectedModel" class="input-field w-full text-xs">
                                <option v-for="m in compatibleModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- Footer Primary Action (Scoped strictly to AI Studio Tab) -->
                <div v-if="activeInspectorTab === 'ai'" class="p-4 border-t dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/80 animate-in fade-in">
                    <button 
                        @click="executeTargetedAiEdit" 
                        class="btn btn-primary w-full py-3 text-xs font-black uppercase tracking-widest shadow-xl shadow-blue-500/20 flex items-center justify-center gap-2" 
                        :disabled="isProcessingTask || !prompt.trim()"
                    >
                        <IconSparkles class="w-4 h-4" /> 
                        <span>{{ useInpaintMask ? 'Render Inpaint on Target' : 'Apply AI Edit to Target' }}</span>
                    </button>
                </div>
            </aside>
        </div>

        <!-- ── SAVE / EXPORT FORMAT MODAL ── -->
        <Teleport to="body">
            <Transition
                enter-active-class="transition-opacity duration-200"
                enter-from-class="opacity-0"
                enter-to-class="opacity-100"
                leave-active-class="transition-opacity duration-150"
                leave-from-class="opacity-100"
                leave-to-class="opacity-0"
            >
                <div
                    v-if="isSaveModalOpen"
                    class="fixed inset-0 z-[9999] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
                    @click.self="closeSaveModal"
                >
                    <div class="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl max-w-md w-full border border-gray-200 dark:border-gray-800 overflow-hidden flex flex-col max-h-[90vh]">
                        <!-- Header -->
                        <div class="px-5 py-4 border-b border-gray-200 dark:border-gray-800 flex items-start justify-between gap-3 shrink-0">
                            <div>
                                <h3 class="text-sm font-black uppercase tracking-widest text-gray-800 dark:text-gray-100">Save Image</h3>
                                <p class="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">Choose an output format for this export.</p>
                            </div>
                            <button @click="closeSaveModal" class="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors" title="Close">
                                <IconXMark class="w-4 h-4" />
                            </button>
                        </div>

                        <!-- Body -->
                        <div class="p-5 space-y-4 overflow-y-auto custom-scrollbar">
                            <!-- Format picker -->
                            <div>
                                <label class="text-[10px] font-black uppercase tracking-widest text-gray-400 dark:text-gray-500 block mb-2">Format</label>
                                <div class="grid grid-cols-4 gap-2">
                                    <button
                                        v-for="fmt in saveFormats"
                                        :key="fmt.id"
                                        @click="saveFormat = fmt.id"
                                        class="flex flex-col items-center p-2 rounded-xl border transition-all"
                                        :class="saveFormat === fmt.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 ring-1 ring-blue-500 shadow-sm' : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-400 hover:border-gray-300 dark:hover:border-gray-600'"
                                    >
                                        <span class="text-xl mb-1 leading-none">{{ fmt.emoji }}</span>
                                        <span class="text-[10px] font-black uppercase">{{ fmt.label }}</span>
                                        <span class="text-[8px] opacity-60 leading-tight text-center mt-0.5">{{ fmt.hint }}</span>
                                    </button>
                                </div>
                            </div>

                            <!-- Quality (lossy formats only) -->
                            <div v-if="['jpeg', 'webp', 'pdf'].includes(saveFormat)" class="space-y-1">
                                <div class="flex justify-between items-center">
                                    <label class="text-[10px] font-black uppercase tracking-widest text-gray-400 dark:text-gray-500">Quality</label>
                                    <span class="font-mono text-[10px] font-bold text-blue-600 dark:text-blue-400">{{ Math.round(saveQuality * 100) }}%</span>
                                </div>
                                <input type="range" min="0.4" max="1" step="0.01" v-model.number="saveQuality" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500" />
                            </div>

                            <!-- Filename -->
                            <div class="space-y-1">
                                <label class="text-[10px] font-black uppercase tracking-widest text-gray-400 dark:text-gray-500 block">File Name</label>
                                <div class="flex items-center gap-1">
                                    <input
                                        v-model="saveFilename"
                                        type="text"
                                        class="input-field w-full text-xs"
                                        placeholder="composition"
                                        @keydown.enter="confirmSave"
                                    />
                                    <span class="text-[10px] font-mono font-bold text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 px-2 py-1.5 rounded-lg shrink-0">.{{ saveExtension }}</span>
                                </div>
                            </div>

                            <!-- Also add to gallery -->
                            <div class="flex items-center justify-between gap-3 p-3 bg-gray-50 dark:bg-gray-800/60 rounded-xl border border-gray-200 dark:border-gray-700">
                                <div class="min-w-0">
                                    <p class="text-xs font-bold text-gray-700 dark:text-gray-200">Also add to gallery</p>
                                    <p class="text-[10px] text-gray-500 dark:text-gray-400">Saved as a PNG in Image Studio.</p>
                                </div>
                                <button @click="saveAlsoToGallery = !saveAlsoToGallery" :class="saveAlsoToGallery ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'" class="w-9 h-5 rounded-full relative transition-colors shrink-0">
                                    <div class="absolute top-0.5 w-4 h-4 bg-white rounded-full transition-all shadow" :style="{ left: saveAlsoToGallery ? '18px' : '2px' }"></div>
                                </button>
                            </div>
                        </div>

                        <!-- Footer -->
                        <div class="px-5 py-3 border-t border-gray-200 dark:border-gray-800 flex items-center justify-end gap-2 shrink-0">
                            <button @click="closeSaveModal" class="btn btn-secondary" :disabled="isSavingImage">Cancel</button>
                            <button @click="confirmSave" class="btn btn-primary flex items-center gap-2" :disabled="isSavingImage">
                                <IconAnimateSpin v-if="isSavingImage" class="w-4 h-4 animate-spin" />
                                <IconSave v-else class="w-4 h-4" />
                                <span>{{ isSavingImage ? 'Saving…' : 'Save' }}</span>
                            </button>
                        </div>
                    </div>
                </div>
            </Transition>
        </Teleport>

        <!-- ── TEXT TOOL EDITOR ── -->
        <Teleport to="body">
            <Transition
                enter-active-class="transition-opacity duration-150"
                enter-from-class="opacity-0"
                leave-active-class="transition-opacity duration-100"
                leave-to-class="opacity-0"
            >
                <div v-if="textEditor.visible" class="fixed inset-0 z-[9999] pointer-events-none">
                    <div class="absolute top-20 right-4 w-80 bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-800 overflow-hidden pointer-events-auto flex flex-col max-h-[80vh]">
                        <div class="px-4 py-2.5 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <IconType class="w-4 h-4 text-blue-500" />
                                <span class="text-xs font-black uppercase tracking-widest">Text Tool</span>
                            </div>
                            <button @click="cancelText" class="p-1 text-gray-400 hover:text-red-500"><IconXMark class="w-4 h-4" /></button>
                        </div>
                        <div class="p-4 space-y-3 overflow-y-auto custom-scrollbar">
                            <textarea v-model="textEditor.text" rows="3" class="input-field !text-sm w-full resize-none" placeholder="Type text..." autofocus></textarea>
                            <div class="grid grid-cols-2 gap-2">
                                <div class="space-y-1">
                                    <label class="text-[9px] font-black uppercase text-gray-400">Font</label>
                                    <select v-model="textEditor.fontFamily" class="input-field !text-[11px] !py-1">
                                        <option value="Inter, sans-serif">Inter (Sans)</option>
                                        <option value="Georgia, serif">Georgia (Serif)</option>
                                        <option value="'Courier New', monospace">Courier (Mono)</option>
                                        <option value="'Brush Script MT', cursive">Brush Script</option>
                                        <option value="'Times New Roman', serif">Times</option>
                                        <option value="Impact, sans-serif">Impact</option>
                                        <option value="Arial, sans-serif">Arial</option>
                                    </select>
                                </div>
                                <div class="space-y-1">
                                    <label class="text-[9px] font-black uppercase text-gray-400">Size (px)</label>
                                    <input v-model.number="textEditor.fontSize" type="number" min="8" max="400" class="input-field !text-[11px] !py-1 font-mono" />
                                </div>
                            </div>
                            <div class="flex items-center gap-1 flex-wrap">
                                <button @click="textEditor.fontWeight = textEditor.fontWeight === 'bold' ? 'normal' : 'bold'" class="px-2 py-1 text-[11px] font-black rounded border" :class="textEditor.fontWeight === 'bold' ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600' : 'border-gray-200 dark:border-gray-700 text-gray-500'">B</button>
                                <button @click="textEditor.italic = !textEditor.italic" class="px-2 py-1 text-[11px] italic rounded border" :class="textEditor.italic ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600' : 'border-gray-200 dark:border-gray-700 text-gray-500'">I</button>
                                <button @click="textEditor.underline = !textEditor.underline" class="px-2 py-1 text-[11px] underline rounded border" :class="textEditor.underline ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600' : 'border-gray-200 dark:border-gray-700 text-gray-500'">U</button>
                                <div class="w-px h-4 bg-gray-200 dark:bg-gray-700 mx-1"></div>
                                <button v-for="al in ['left','center','right']" :key="al" @click="textEditor.align = al" class="px-2 py-1 text-[10px] font-black rounded border uppercase" :class="textEditor.align === al ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600' : 'border-gray-200 dark:border-gray-700 text-gray-500'">{{ al[0] }}</button>
                            </div>
                            <div class="grid grid-cols-2 gap-2">
                                <div class="space-y-1">
                                    <label class="text-[9px] font-black uppercase text-gray-400">Color</label>
                                    <div class="flex items-center gap-1">
                                        <input type="color" v-model="textEditor.color" class="w-7 h-7 rounded border cursor-pointer" />
                                        <input v-model="textEditor.color" class="input-field !text-[10px] !py-1 font-mono uppercase" />
                                    </div>
                                </div>
                                <div class="space-y-1">
                                    <label class="text-[9px] font-black uppercase text-gray-400">Rotation°</label>
                                    <input v-model.number="textEditor.rotation" type="number" min="-180" max="180" class="input-field !text-[11px] !py-1 font-mono" />
                                </div>
                            </div>
                            <div class="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-800/60 rounded-lg border dark:border-gray-700">
                                <span class="text-[10px] font-bold text-gray-600 dark:text-gray-300">Drop Shadow</span>
                                <button @click="textEditor.shadow = !textEditor.shadow" :class="textEditor.shadow ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'" class="w-8 h-4 rounded-full relative transition-colors">
                                    <div class="absolute top-0.5 w-3 h-3 bg-white rounded-full transition-all" :style="{ left: textEditor.shadow ? '16px' : '2px' }"></div>
                                </button>
                            </div>
                        </div>
                        <div class="px-4 py-2.5 border-t border-gray-200 dark:border-gray-800 flex items-center justify-end gap-2">
                            <button @click="cancelText" class="btn btn-secondary btn-sm text-xs">Cancel</button>
                            <button @click="commitText" class="btn btn-primary btn-sm text-xs">Place Text</button>
                        </div>
                    </div>
                </div>
            </Transition>
        </Teleport>

        <!-- ── SHORTCUTS HELP OVERLAY (?) ── -->
        <Teleport to="body">
            <Transition
                enter-active-class="transition-opacity duration-150"
                enter-from-class="opacity-0"
                leave-active-class="transition-opacity duration-100"
                leave-to-class="opacity-0"
            >
                <div v-if="showShortcutsHelp" class="fixed inset-0 z-[9999] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" @click.self="showShortcutsHelp = false">
                    <div class="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl max-w-3xl w-full border border-gray-200 dark:border-gray-800 overflow-hidden">
                        <div class="px-5 py-3 border-b border-gray-200 dark:border-gray-800 flex justify-between items-center">
                            <h3 class="text-sm font-black uppercase tracking-widest text-gray-800 dark:text-gray-100">Keyboard Shortcuts</h3>
                            <button @click="showShortcutsHelp = false" class="p-1 text-gray-400 hover:text-red-500"><IconXMark class="w-4 h-4" /></button>
                        </div>
                        <div class="p-5 overflow-y-auto max-h-[70vh] custom-scrollbar grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                            <div v-for="group in toolGroups" :key="group.id" class="space-y-1">
                                <h4 class="text-[10px] font-black uppercase tracking-widest text-blue-600 mb-1.5">{{ group.label }}</h4>
                                <div v-for="t in toolsByGroup(group.id)" :key="t.id" class="flex justify-between items-center text-xs">
                                    <span class="text-gray-700 dark:text-gray-300">{{ t.name }}</span>
                                    <kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold border border-gray-200 dark:border-gray-700">{{ t.shortcut }}</kbd>
                                </div>
                            </div>
                            <div class="space-y-1 sm:col-span-2 md:col-span-3 pt-3 mt-3 border-t dark:border-gray-800">
                                <h4 class="text-[10px] font-black uppercase tracking-widest text-blue-600 mb-1.5">Editor Actions</h4>
                                <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-1">
                                    <div class="flex justify-between items-center text-xs"><span class="text-gray-700 dark:text-gray-300">Undo</span><kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold">Ctrl+Z</kbd></div>
                                    <div class="flex justify-between items-center text-xs"><span class="text-gray-700 dark:text-gray-300">Redo</span><kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold">Ctrl+Y</kbd></div>
                                    <div class="flex justify-between items-center text-xs"><span class="text-gray-700 dark:text-gray-300">Quick Save to Gallery</span><kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold">Ctrl+S</kbd></div>
                                    <div class="flex justify-between items-center text-xs"><span class="text-gray-700 dark:text-gray-300">Export / Save As…</span><kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold">Ctrl+Shift+S</kbd></div>
                                    <div class="flex justify-between items-center text-xs"><span class="text-gray-700 dark:text-gray-300">New Layer</span><kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold">Ctrl+Shift+N</kbd></div>
                                    <div class="flex justify-between items-center text-xs"><span class="text-gray-700 dark:text-gray-300">Duplicate Layer</span><kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold">Ctrl+J</kbd></div>
                                    <div class="flex justify-between items-center text-xs"><span class="text-gray-700 dark:text-gray-300">Swap FG / BG</span><kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold">X</kbd></div>
                                    <div class="flex justify-between items-center text-xs"><span class="text-gray-700 dark:text-gray-300">Reset to Black / White</span><kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold">D</kbd></div>
                                    <div class="flex justify-between items-center text-xs"><span class="text-gray-700 dark:text-gray-300">Momentary Pan</span><kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold">Space (hold)</kbd></div>
                                    <div class="flex justify-between items-center text-xs"><span class="text-gray-700 dark:text-gray-300">Brush Size ↓ / ↑</span><kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold">[ / ]</kbd></div>
                                    <div class="flex justify-between items-center text-xs"><span class="text-gray-700 dark:text-gray-300">Zoom In / Out</span><kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold">Wheel / Pinch</kbd></div>
                                    <div class="flex justify-between items-center text-xs"><span class="text-gray-700 dark:text-gray-300">Pan Horizontally</span><kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold">Shift + Wheel</kbd></div>
                                    <div class="flex justify-between items-center text-xs"><span class="text-gray-700 dark:text-gray-300">Pan Vertically</span><kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold">Alt + Wheel</kbd></div>
                                    <div class="flex justify-between items-center text-xs"><span class="text-gray-700 dark:text-gray-300">Toggle this Help</span><kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold">?</kbd></div>
                                    <div class="flex justify-between items-center text-xs"><span class="text-gray-700 dark:text-gray-300">Close Modal / Help</span><kbd class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-mono font-bold">Esc</kbd></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </Transition>
        </Teleport>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, h, watch, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { useImageStore } from '../stores/images';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import { useTasksStore } from '../stores/tasks';
import apiClient from '../services/api';

// Icons
import IconPencil from '../assets/icons/IconPencil.vue';
import IconEraser from '../assets/icons/IconEraser.vue';
import IconUndo from '../assets/icons/IconUndo.vue';
import IconRedo from '../assets/icons/IconRedo.vue';
import IconSave from '../assets/icons/IconSave.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconMinus from '../assets/icons/IconMinus.vue';
import IconMaximize from '../assets/icons/IconMaximize.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconType from '../assets/icons/IconType.vue';
import IconEye from '../assets/icons/IconEye.vue';
import IconEyeOff from '../assets/icons/IconEyeOff.vue';
import IconPhoto from '../assets/icons/IconPhoto.vue';
import IconXMark from '../assets/icons/IconXMark.vue';
import IconAdjustmentsHorizontal from '../assets/icons/IconAdjustmentsHorizontal.vue';
import IconArrowPath from '../assets/icons/IconArrowPath.vue';
import IconCircle from '../assets/icons/IconCircle.vue';
import IconFolder from '../assets/icons/IconFolder.vue';
import IconCopy from '../assets/icons/IconCopy.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconChevronDown from '../assets/icons/IconChevronDown.vue';
import IconLock from '../assets/icons/IconLock.vue';
import IconLockOpen from '../assets/icons/IconLockOpen.vue';
import IconClock from '../assets/icons/IconClock.vue';

// Dynamic Vector Icons — refined Heroicon-style paths (1.8 stroke, round caps)
const SVG_ATTRS = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true' };

// Move / Pan — raised hand (matches Photoshop's "grab" cursor intent for canvas pan)
const IconHand = { render: () => h('svg', SVG_ATTRS, [
    h('path', { d: 'M10.05 4.575a1.575 1.575 0 10-3.15 0v3m3.15-3v-1.5a1.575 1.575 0 013.15 0v1.5m-3.15 0l.075 5.925m3.075.75V4.575m-3.075 5.925L6.75 8.175A1.575 1.575 0 004.5 10.5l3.15 4.5m3.075-4.5l.075 5.925' })
]) };

// Line — diagonal segment with distinct endpoints
const IconLine = { render: () => h('svg', SVG_ATTRS, [
    h('path', { d: 'M4.5 19.5l15-15' }),
    h('circle', { cx: '4.5', cy: '19.5', r: '1.6', fill: 'currentColor', stroke: 'none' }),
    h('circle', { cx: '19.5', cy: '4.5', r: '1.6', fill: 'currentColor', stroke: 'none' })
]) };

// Rectangle — rounded portrait frame
const IconRect = { render: () => h('svg', SVG_ATTRS, [
    h('rect', { x: '3.75', y: '4.5', width: '16.5', height: '15', rx: '2' })
]) };

// Magic Wand — sparkles cluster (reads as "magic selection" at 18px)
const IconWand = { render: () => h('svg', SVG_ATTRS, [
    h('path', { d: 'M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z' }),
    h('path', { d: 'M18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z' })
]) };

// Eyedropper — angled picker with bulb and tip
const IconEyedropper = { render: () => h('svg', SVG_ATTRS, [
    h('path', { d: 'M17.25 3.75a3.182 3.182 0 014.5 4.5l-3 3-4.5-4.5 3-3z' }),
    h('path', { d: 'M15 6l3 3' }),
    h('path', { d: 'M12.75 8.25L4.5 16.5V19.5h3l8.25-8.25' })
]) };

// Gradient — frame with progressive horizontal band opacity (fade-to-transparent hint)
const IconGradient = { render: () => h('svg', SVG_ATTRS, [
    h('rect', { x: '3.75', y: '4.5', width: '16.5', height: '15', rx: '2' }),
    h('path', { d: 'M3.75 9h16.5', opacity: '0.6', 'stroke-width': '1' }),
    h('path', { d: 'M3.75 13h16.5', opacity: '0.38', 'stroke-width': '1' }),
    h('path', { d: 'M3.75 17h16.5', opacity: '0.2', 'stroke-width': '1' })
]) };

// ── Phase 2 icons ──
const IconMarquee = { render: () => h('svg', SVG_ATTRS, [
    h('rect', { x: '4', y: '4', width: '16', height: '16', rx: '1.5', 'stroke-dasharray': '3 2' })
]) };
const IconLasso = { render: () => h('svg', SVG_ATTRS, [
    h('path', { d: 'M8 18c-2-1-4-3-4-6a8 8 0 0116 0c0 3-2 5-4 6', 'stroke-dasharray': '3 2' }),
    h('circle', { cx: '8', cy: '18', r: '1.5', fill: 'currentColor', stroke: 'none' })
]) };
const IconCrop = { render: () => h('svg', SVG_ATTRS, [
    h('path', { d: 'M6 2v14a2 2 0 002 2h14' }),
    h('path', { d: 'M2 6h14a2 2 0 012 2v14' })
]) };
const IconMove = { render: () => h('svg', SVG_ATTRS, [
    h('path', { d: 'M12 2v20 M2 12h20' }),
    h('path', { d: 'M9 5l3-3 3 3 M9 19l3 3 3-3 M5 9l-3 3 3 3 M19 9l3 3-3 3' })
]) };
const IconFill = { render: () => h('svg', SVG_ATTRS, [
    h('path', { d: 'M4 12l7-7 7 7-7 7z' }),
    h('path', { d: 'M18 15c1.5 0 3 1 3 3a3 3 0 11-6 0c0-2 1.5-3 3-3z', fill: 'currentColor', opacity: '0.35', stroke: 'none' })
]) };
const IconHeal = { render: () => h('svg', SVG_ATTRS, [
    h('circle', { cx: '9', cy: '9', r: '5' }),
    h('path', { d: 'M17 14l1 2 2 1-2 1-1 2-1-2-2-1 2-1z', fill: 'currentColor', stroke: 'none' })
]) };
const IconDodge = { render: () => h('svg', SVG_ATTRS, [
    h('circle', { cx: '12', cy: '12', r: '3.5' }),
    h('path', { d: 'M12 2v3 M12 19v3 M2 12h3 M19 12h3 M4.9 4.9l2.1 2.1 M17 17l2.1 2.1 M4.9 19.1l2.1-2.1 M17 7l2.1-2.1' })
]) };
const IconBurn = { render: () => h('svg', SVG_ATTRS, [
    h('path', { d: 'M20 13.5A7.5 7.5 0 0110.5 4a7.5 7.5 0 1011.996 9.5' })
]) };
const IconSmudge = { render: () => h('svg', SVG_ATTRS, [
    h('path', { d: 'M5 17c3-1 5-3 7-6s4-5 7-5' }),
    h('path', { d: 'M15 4l4 2 M8 12l-1 4 4-1' })
]) };

const props = defineProps({ id: { type: String, default: null } });
const router = useRouter();
const imageStore = useImageStore();

// Click Outside Directive
const vOnClickOutside = {
  mounted: (el, binding) => {
    el.clickOutsideEvent = event => {
      if (!(el === event.target || el.contains(event.target))) {
        binding.value(event);
      }
    };
    document.addEventListener('mousedown', el.clickOutsideEvent);
  },
  unmounted: el => {
    document.removeEventListener('mousedown', el.clickOutsideEvent);
  },
};
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const tasksStore = useTasksStore();

const isComponentMounted = ref(false);
const hasHeaderTarget = ref(false);
const showMobileSidebar = ref(false);
const activeInspectorTab = ref('layers'); // 'layers' | 'transform' | 'adjust' | 'ai'

// ── Phase 2 state: selection / crop / retouch / text ──
const selection = ref({ active: false, type: null, points: [], bounds: null, inverted: false });
const isDrawingSelection = ref(false);
const cropRect = ref(null);
const isDrawingCrop = ref(false);
const cropAspect = ref(null);
const moveSnapshot = ref(null);
const moveStartPx = ref(null);
const retouchSample = ref(null);
const preStrokeSnapshot = ref(null);
const textEditor = ref({
    visible: false, x: 0, y: 0, text: '',
    fontFamily: 'Inter, sans-serif', fontSize: 48, fontWeight: 'bold',
    italic: false, underline: false, align: 'left',
    color: '#000000', shadow: true, rotation: 0
});

// ── Phase-1 additions ──
// Shortcuts help overlay (opened with `?`)
const showShortcutsHelp = ref(false);
// Visual history strip toggle
const isHistoryStripVisible = ref(false);
// Layer drag-reorder state
const draggingLayerId = ref(null);
const dragOverLayerId = ref(null);
// Layer inline rename state
const editingLayerId = ref(null);
const editingLayerName = ref('');
// Multi-document tabs — each tab holds a fully-serialized doc state (layers
// image data, history, prompts). Only the ACTIVE tab's live refs are real;
// switching tabs serializes the current tab and restores the target.
const docs = ref([]);
const activeDocIndex = ref(0);
const containerRef = ref(null);
const imageCanvasRef = ref(null);
const maskCanvasRef = ref(null);
const previewCanvasRef = ref(null);
const ctxMask = ref(null);
const ctxPreview = ref(null);

const canvasWidth = ref(1024);
const canvasHeight = ref(1024);

const activeLayerId = ref('base');
const tool = ref('brush');
const color = ref('#3B82F6');
const secondaryColor = ref('#EC4899');
const brushSize = ref(35);
const brushHardness = ref(0.85);
const zoom = ref(1);
const panX = ref(0);
const panY = ref(0);

// AI Studio Specific State
const prompt = ref('');
const negativePrompt = ref('');
const editStrength = ref(0.70);
const aiEditTarget = ref('active'); // 'active' | 'flattened'
const useInpaintMask = ref(false);
const outputAsNewLayer = ref(true);
const selectedModel = ref('');
const isProcessingTask = ref(false);
const activeTaskId = ref(null);

// ── Save / Export Modal State ──
// The toolbar "Save" action now opens a format picker instead of blindly
// flattening to PNG. `saveCanvas()` (below) is retained as the gallery-save
// pipeline and is reused by `confirmSave()` when "also add to gallery" is on.
const isSaveModalOpen = ref(false);
const saveFormat = ref('png'); // 'png' | 'jpeg' | 'webp' | 'pdf'
const saveQuality = ref(0.92);
const saveAlsoToGallery = ref(true);
const saveFilename = ref('composition');
const isSavingImage = ref(false);

const saveFormats = [
    { id: 'png',  label: 'PNG',  hint: 'Lossless · alpha',   emoji: '🖼️' },
    { id: 'jpeg', label: 'JPG',  hint: 'Smaller · no alpha', emoji: '📷' },
    { id: 'webp', label: 'WEBP', hint: 'Compact · modern',   emoji: '🌐' },
    { id: 'pdf',  label: 'PDF',  hint: 'Document export',    emoji: '📄' }
];

const saveExtension = computed(() => (
    { png: 'png', jpeg: 'jpg', webp: 'webp', pdf: 'pdf' }[saveFormat.value] || 'png'
));

function buildCompositeCanvas() {
    const comp = document.createElement('canvas');
    comp.width = imageCanvasRef.value.width;
    comp.height = imageCanvasRef.value.height;
    const cc = comp.getContext('2d');
    layers.value.filter(l => l.visible).forEach(l => {
        if (l.ctx) {
            cc.globalAlpha = l.opacity;
            cc.globalCompositeOperation = l.blendMode || 'source-over';
            cc.drawImage(l.ctx.canvas, 0, 0);
        }
    });
    return comp;
}

// JPEG/PDF have no alpha channel — composite onto solid white first so the
// transparent areas of the layered canvas don't turn black after encoding.
function flattenWithWhiteBackground(comp) {
    const bg = document.createElement('canvas');
    bg.width = comp.width;
    bg.height = comp.height;
    const c = bg.getContext('2d');
    c.fillStyle = '#FFFFFF';
    c.fillRect(0, 0, bg.width, bg.height);
    c.drawImage(comp, 0, 0);
    return bg;
}

function triggerDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1500);
}

/**
 * Builds a minimal, spec-compliant single-page PDF wrapping a JPEG-compressed
 * copy of the canvas (DCTDecode filter). No external library needed — we
 * assemble the object table, xref and trailer with correct byte offsets.
 */
function canvasToPdfBlob(canvas, quality = 0.92) {
    return new Promise((resolve, reject) => {
        const w = canvas.width;
        const h = canvas.height;
        canvas.toBlob(async (jpegBlob) => {
            if (!jpegBlob) {
                reject(new Error('Failed to encode JPEG for PDF.'));
                return;
            }
            try {
                const jpegBuf = new Uint8Array(await jpegBlob.arrayBuffer());
                const enc = new TextEncoder();

                const parts = [];
                let byteLen = 0;
                const pushBytes = (u8) => { parts.push(u8); byteLen += u8.length; };
                const pushStr = (s) => pushBytes(enc.encode(s));

                const objOffsets = {};

                // Header + binary marker (percent + 4 bytes >= 128)
                pushStr('%PDF-1.4\n');
                pushBytes(new Uint8Array([0x25, 0xE2, 0xE3, 0xCF, 0xD3, 0x0A]));

                objOffsets[1] = byteLen;
                pushStr('1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n');

                objOffsets[2] = byteLen;
                pushStr('2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n');

                objOffsets[3] = byteLen;
                pushStr(`3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${w} ${h}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>\nendobj\n`);

                objOffsets[4] = byteLen;
                pushStr(`4 0 obj\n<< /Type /XObject /Subtype /Image /Width ${w} /Height ${h} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpegBuf.length} >>\nstream\n`);
                pushBytes(jpegBuf);
                pushStr('\nendstream\nendobj\n');

                const contentBytes = enc.encode(`q\n${w} 0 0 ${h} 0 0 cm\n/Im0 Do\nQ\n`);
                objOffsets[5] = byteLen;
                pushStr(`5 0 obj\n<< /Length ${contentBytes.length} >>\nstream\n`);
                pushBytes(contentBytes);
                pushStr('\nendstream\nendobj\n');

                // xref table (20-byte entries) + trailer
                const xrefStart = byteLen;
                let xref = 'xref\n0 6\n0000000000 65535 f \n';
                for (let i = 1; i <= 5; i++) {
                    xref += String(objOffsets[i]).padStart(10, '0') + ' 00000 n \n';
                }
                pushStr(xref);
                pushStr(`trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF\n`);

                resolve(new Blob(parts, { type: 'application/pdf' }));
            } catch (err) {
                reject(err);
            }
        }, 'image/jpeg', quality);
    });
}

function openSaveModal() {
    const base = (prompt.value || 'composition')
        .trim()
        .slice(0, 40)
        .replace(/[^\w\s-]/g, '')
        .replace(/\s+/g, '_') || 'composition';
    saveFilename.value = base;
    saveFormat.value = 'png';
    saveQuality.value = 0.92;
    saveAlsoToGallery.value = true;
    isSaveModalOpen.value = true;
}

function closeSaveModal() {
    if (isSavingImage.value) return;
    isSaveModalOpen.value = false;
}

async function confirmSave() {
    if (!imageCanvasRef.value || isSavingImage.value) return;
    isSavingImage.value = true;
    try {
        const comp = buildCompositeCanvas();
        const cleanName = (saveFilename.value || 'composition')
            .trim()
            .replace(/\.[^.]+$/, '') || 'composition';
        const finalName = `${cleanName}.${saveExtension.value}`;

        // 1. Download in the chosen format
        if (saveFormat.value === 'pdf') {
            const blob = await canvasToPdfBlob(flattenWithWhiteBackground(comp), saveQuality.value);
            triggerDownload(blob, finalName);
        } else {
            const mime = saveFormat.value === 'jpeg'
                ? 'image/jpeg'
                : saveFormat.value === 'webp'
                    ? 'image/webp'
                    : 'image/png';
            const target = saveFormat.value === 'jpeg' ? flattenWithWhiteBackground(comp) : comp;
            const blob = await new Promise((res) => target.toBlob(res, mime, saveQuality.value));
            if (blob) triggerDownload(blob, finalName);
        }

        // 2. Optionally persist a PNG copy into the gallery (reuses the
        //    existing saveCanvas pipeline, including its own notification).
        if (saveAlsoToGallery.value) {
            saveCanvas();
        }

        uiStore.addNotification(`Exported ${finalName}`, 'success', 2000);
        isSaveModalOpen.value = false;
    } catch (e) {
        console.error('Export failed:', e);
        uiStore.addNotification('Failed to export image.', 'error');
    } finally {
        isSavingImage.value = false;
    }
}

const recentColors = ref(['#000000', '#FFFFFF', '#EF4444', '#10B981', '#3B82F6', '#F59E0B', '#8B5CF6']);

// Non-destructive Color Adjustments
const adjustments = ref({
    brightness: 1.0,
    contrast: 1.0,
    saturate: 1.0,
    hueRotate: 0,
    blur: 0
});

const blendModes = [
    { label: 'Normal', value: 'normal' },
    { label: 'Multiply', value: 'multiply' },
    { label: 'Screen', value: 'screen' },
    { label: 'Overlay', value: 'overlay' },
    { label: 'Darken', value: 'darken' },
    { label: 'Lighten', value: 'lighten' },
    { label: 'Color Dodge', value: 'color-dodge' },
    { label: 'Color Burn', value: 'color-burn' },
    { label: 'Hard Light', value: 'hard-light' },
    { label: 'Soft Light', value: 'soft-light' },
    { label: 'Difference', value: 'difference' },
    { label: 'Exclusion', value: 'exclusion' }
];

const defaultAdjustments = () => ({
    brightness: 1.0,
    contrast: 1.0,
    saturate: 1.0,
    hueRotate: 0,
    blur: 0
});

const layers = ref([
    { 
        id: 'base', 
        name: 'Base Image Plate', 
        visible: true, 
        order: 0, 
        el: null, 
        ctx: null, 
        opacity: 1.0, 
        blendMode: 'normal',
        locked: false,
        thumbnail: null,
        adjustments: defaultAdjustments() 
    }
]);

const sortedLayers = computed(() => [...layers.value].sort((a, b) => b.order - a.order));
const activeLayer = computed(() => layers.value.find(l => l.id === activeLayerId.value) || layers.value[0]);

const cloneAnchor = ref(null);
const settingCloneAnchor = ref(false);
let isDragging = false, lastX = 0, lastY = 0, startX = 0, startY = 0;
let toolBeforeSpace = null; // remembers the previous tool while Space-held temporary pan is active
const cursorX = ref(0), cursorY = ref(0);
const history = ref([]);
const historyIndex = ref(-1);

// Grouped tool registry — the toolbar renders one pill per group with a
// vertical separator between them. Group order matters (matches visual flow:
// view → color → selection → drawing → shapes → type).
const tools = [ 
    { id: 'pan', name: 'Pan View', icon: IconHand, shortcut: 'V', group: 'view' }, 
    { id: 'move', name: 'Move Layer Content', icon: IconMove, shortcut: '⇧V', group: 'view' },
    { id: 'eyedropper', name: 'Eyedropper', icon: IconEyedropper, shortcut: 'I', group: 'color' },
    { id: 'colorkey', name: 'Chroma Key Click', icon: IconEyedropper, shortcut: 'K', group: 'color' },
    { id: 'marquee', name: 'Rectangular Marquee', icon: IconMarquee, shortcut: 'M', group: 'select' },
    { id: 'ellipse-select', name: 'Elliptical Marquee', icon: IconRect, shortcut: 'M', group: 'select' },
    { id: 'lasso', name: 'Freehand Lasso', icon: IconLasso, shortcut: 'L', group: 'select' },
    { id: 'wand', name: 'Magic Wand Transparency', icon: IconWand, shortcut: 'W', group: 'select' },
    { id: 'crop', name: 'Crop Canvas', icon: IconCrop, shortcut: '⇧C', group: 'select' },
    { id: 'brush', name: 'Brush', icon: IconPencil, shortcut: 'B', group: 'draw' }, 
    { id: 'eraser', name: 'Eraser', icon: IconEraser, shortcut: 'E', group: 'draw' }, 
    { id: 'clone', name: 'Clone Stamp', icon: IconArrowPath, shortcut: 'C', group: 'draw' },
    { id: 'gradient', name: 'Gradient', icon: IconGradient, shortcut: 'G', group: 'draw' },
    { id: 'fill', name: 'Paint Bucket', icon: IconFill, shortcut: '⇧G', group: 'draw' },
    { id: 'line', name: 'Line', icon: IconLine, shortcut: 'U', group: 'shape' }, 
    { id: 'rect', name: 'Rectangle', icon: IconRect, shortcut: 'R', group: 'shape' }, 
    { id: 'circle', name: 'Ellipse', icon: IconCircle, shortcut: 'O', group: 'shape' },
    { id: 'heal', name: 'Spot Heal', icon: IconHeal, shortcut: 'J', group: 'retouch' },
    { id: 'dodge', name: 'Dodge (Lighten)', icon: IconDodge, shortcut: '⇧D', group: 'retouch' },
    { id: 'burn', name: 'Burn (Darken)', icon: IconBurn, shortcut: '⇧B', group: 'retouch' },
    { id: 'smudge', name: 'Smudge', icon: IconSmudge, shortcut: 'S', group: 'retouch' },
    { id: 'text', name: 'Text', icon: IconType, shortcut: 'T', group: 'text' }
];

const toolGroups = [
    { id: 'view', label: 'View' },
    { id: 'color', label: 'Color' },
    { id: 'select', label: 'Selection' },
    { id: 'draw', label: 'Draw' },
    { id: 'shape', label: 'Shapes' },
    { id: 'retouch', label: 'Retouch' },
    { id: 'text', label: 'Type' }
];

function toolsByGroup(groupId) {
    return tools.filter(t => t.group === groupId);
}

const currentToolName = computed(() => tools.find(t => t.id === tool.value)?.name || 'Studio Tool');
const compatibleModels = computed(() => dataStore.availableTtiModels);
const showCursor = computed(() => ['brush', 'eraser', 'circle', 'text', 'clone', 'wand', 'eyedropper', 'heal', 'dodge', 'burn', 'smudge'].includes(tool.value));
const combinedCanvasStyle = computed(() => ({ transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})` }));
const activeTask = computed(() => tasksStore.tasks.find(t => t.id === activeTaskId.value));

const aiKeyScreenMode = ref('magenta'); // 'magenta' | 'green' | 'white' | 'off'

// Chroma Key Suite State
const keyColor = ref('#00FF00');
const keyTolerance = ref(28);
const keySoftness = ref(12);
const keySpillSuppression = ref(true);

const isPaletteStudioOpen = ref(false);
const selectedPaletteName = ref('Essentials');
const customPalette = ref(JSON.parse(localStorage.getItem('lollms_custom_palette') || '["#3B82F6", "#EC4899", "#10B981", "#F59E0B", "#8B5CF6", "#EF4444", "#06B6D4", "#F97316"]'));
const extractedPalette = ref([]);

// Curated Professional Palette Collections
const presetPalettes = {
    'Essentials': ['#000000', '#FFFFFF', '#374151', '#9CA3AF', '#EF4444', '#F97316', '#F59E0B', '#10B981', '#06B6D4', '#3B82F6', '#6366F1', '#EC4899'],
    'Skin & Portrait': ['#FCE5D8', '#F5D0B9', '#E8B99A', '#D09B79', '#B57C58', '#8D5638', '#5E341E', '#3D1E0E', '#F8B4B4', '#E06D53', '#8C2E2E', '#3A1414'],
    'Cyberpunk Neon': ['#00F0FF', '#FF0055', '#FFE600', '#7000FF', '#00FF66', '#FF00AA', '#120024', '#002B49', '#1A0033', '#FF5500', '#00E5FF', '#FFFF00'],
    'Earth & Nature': ['#1E3A1E', '#2D5A27', '#4E8752', '#86B049', '#D0E17C', '#F4E8C1', '#C89D7C', '#8C6239', '#5C3818', '#38220F', '#4A6B82', '#7DA0B5'],
    'Pastel Dreams': ['#FDE2E4', '#FFCAD4', '#B5E2FA', '#C5DEDD', '#DFE7FD', '#E2ECE9', '#F0E6EF', '#FFF1E6', '#FCD2D1', '#D6E2E9', '#BCD4E6', '#99C1DE'],
    'Vintage Retro': ['#DDA77A', '#C85A32', '#A33327', '#4E2B1F', '#7E8D52', '#3D5A45', '#1B3B36', '#E2D1A8', '#E68A00', '#B83B1D', '#5C4033', '#1A1110'],
    'Manga & Comic': ['#000000', '#333333', '#666666', '#999999', '#CCCCCC', '#FFFFFF', '#E50914', '#0070F3', '#FFD700', '#FF4500', '#22C55E', '#A855F7'],
    'Monochrome Shading': ['#000000', '#18181B', '#27272A', '#3F3F46', '#52525B', '#71717A', '#A1A1AA', '#D4D4D8', '#E4E4E7', '#F4F4F5', '#FAFAFA', '#FFFFFF']
};

const activePaletteColors = computed(() => {
    if (selectedPaletteName.value === 'Custom') return customPalette.value;
    if (selectedPaletteName.value === 'Extracted') return extractedPalette.value;
    return presetPalettes[selectedPaletteName.value] || presetPalettes['Essentials'];
});

function selectColor(hex) {
    color.value = hex;
    if (!recentColors.value.includes(hex)) {
        recentColors.value.unshift(hex);
        if (recentColors.value.length > 7) recentColors.value.pop();
    }
}

// Photoshop-style swatch helpers:
//   X → swap foreground / background colors
//   D → reset to black foreground / white background
function swapColors() {
    const tmp = color.value;
    color.value = secondaryColor.value;
    secondaryColor.value = tmp;
}

function resetColors() {
    color.value = '#000000';
    secondaryColor.value = '#FFFFFF';
}

function addColorToCustomPalette(hex) {
    const formatted = hex.toUpperCase();
    if (!customPalette.value.includes(formatted)) {
        customPalette.value.push(formatted);
        localStorage.setItem('lollms_custom_palette', JSON.stringify(customPalette.value));
        selectedPaletteName.value = 'Custom';
        uiStore.addNotification(`Saved ${formatted} to My Custom Palette!`, 'success', 1500);
    }
}

function removeColorFromCustomPalette(idx) {
    customPalette.value.splice(idx, 1);
    localStorage.setItem('lollms_custom_palette', JSON.stringify(customPalette.value));
}

// ── COLOR QUANTIZATION: AUTOMATIC PALETTE EXTRACTION FROM CANVAS ──
function extractPaletteFromCanvas() {
    if (!imageCanvasRef.value) return;
    const comp = document.createElement('canvas');
    comp.width = 120;
    comp.height = 120;
    const cc = comp.getContext('2d');
    
    layers.value.filter(l => l.visible).forEach(l => {
        if (l.ctx) {
            cc.globalAlpha = l.opacity;
            cc.globalCompositeOperation = l.blendMode || 'source-over';
            cc.drawImage(l.ctx.canvas, 0, 0, 120, 120);
        }
    });

    const imgData = cc.getImageData(0, 0, 120, 120).data;
    const colorCounts = new Map();

    for (let i = 0; i < imgData.length; i += 16) {
        const a = imgData[i + 3];
        if (a < 100) continue; // Skip transparent
        
        // Quantize colors (group neighboring shades into clusters)
        const r = Math.round(imgData[i] / 32) * 32;
        const g = Math.round(imgData[i + 1] / 32) * 32;
        const b = Math.round(imgData[i + 2] / 32) * 32;
        
        const hex = `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1).toUpperCase()}`;
        colorCounts.set(hex, (colorCounts.get(hex) || 0) + 1);
    }

    const sorted = Array.from(colorCounts.entries())
        .sort((a, b) => b[1] - a[1])
        .map(entry => entry[0])
        .slice(0, 18);

    if (sorted.length > 0) {
        extractedPalette.value = sorted;
        selectedPaletteName.value = 'Extracted';
        uiStore.addNotification(`Extracted ${sorted.length} dominant colors from artwork!`, 'success', 2000);
    } else {
        uiStore.addNotification('Could not extract colors (canvas is transparent/empty).', 'warning');
    }
}



// Quick Modifiers for Image Editor
const quickEditModifiers = [
    { label: '4K Enhance', emoji: '💎', prompt: 'masterpiece, 8k uhd, pristine sharp focus, ultra-detailed micro texture, noise reduction, crystal clear details', negative: 'blurry, noise, artifacts, low resolution' },
    { label: 'Colorize B&W', emoji: '🎨', prompt: 'natural historical colorization, authentic human skin tones, realistic clothing pigments, vibrant balanced color depth', negative: 'monochrome, black and white, grayscale, washed out' },
    { label: 'Face Refine', emoji: '👤', prompt: 'realistic natural skin texture, visible fine pores, catchlights in eyes, individually defined hair strands, photorealistic', negative: 'plastic skin, airbrushed, cartoon, waxy face' },
    { label: 'Heal Scratches', emoji: '🩹', prompt: 'seamless scratch repair, crease removal, stain heal, sharp details recovered, damage-free restoration', negative: 'scratches, cracks, stains, torn, dust spots' },
    { label: 'Color Pop', emoji: '💥', prompt: 'vivid dynamic color palette, rich color depth, chromatic brilliance, high saturation balance', negative: 'dull, muted, faded, washed out' },
    { label: 'Teal & Orange', emoji: '🎬', prompt: 'cinematic teal and orange color harmony, cool moody shadow tones, warm golden subject accents', negative: 'muddy colors, green tint' },
    { label: 'Despeckle Scan', emoji: '🧽', prompt: 'professionally despeckled scanned document, removed dust spots, print noise, and minute debris, ultra clean uniform page background, 600 DPI sharpness', negative: 'speckles, dust, dots, print noise, dirty scan' },
    { label: 'Deskew Doc', emoji: '📐', prompt: 'perfectly deskewed leveled scan, straight horizontal baselines, square-cropped edges, geometric document alignment', negative: 'tilted, crooked, wavy baseline, skewed scan' },
    { label: 'Recover Faded Ink', emoji: '🖋️', prompt: 'restored faded and degraded ink density, recovered washed-out print contrast, deepened low-opacity lettering, carbon copy recovery', negative: 'washed out, faded, illegible, low contrast, invisible faint text' },
    { label: 'Align Perspective', emoji: '📏', prompt: 'absolutely aligned perspective, corrected skewed document orientation, straightened baselines, uniform rectangular page geometry, four-corner pinning, snapped to vertical truth', negative: 'tilted, skewed, off-axis, rotated, canted, drifting baselines' },
    { label: 'Auto-Crop Borders', emoji: '✂️', prompt: 'auto-detected page borders, precise edge cropping, tight content-aware crop, removed outer blank margins, sharp rectangular document boundary', negative: 'misaligned crop, missing borders, cut-off content, uneven margin, black edge band' },
    { label: 'Pin Corners', emoji: '📌', prompt: 'four document corners detected and pinned, perspective pinpoints locked to rectangular page, corner extraction registration, restored straight border rectangle, unified page frame', negative: 'crooked corners, missed corner, floating edges, unbalanced page' },
    { label: 'Dewarp Page', emoji: '📖', prompt: 'page curvature dewarped, flattened curved book page, straightened distorted text lines, cylindrical perspective correction, dewarped flat print surface', negative: 'wavy text, curled page, barrel distortion, curved lines, bowl warp' }
];

onMounted(async () => {
    isComponentMounted.value = true;
    uiStore.setPageTitle({ title: '', icon: null });
    nextTick(() => hasHeaderTarget.value = !!document.getElementById('global-header-title-target'));

    if (dataStore.availableTtiModels.length === 0) {
        await dataStore.fetchAvailableTtiModels();
    }

    if (maskCanvasRef.value) ctxMask.value = maskCanvasRef.value.getContext('2d');
    if (previewCanvasRef.value) ctxPreview.value = previewCanvasRef.value.getContext('2d');

    // Initialize the multi-document tab registry BEFORE loading so the first
    // tab captures the entire resulting state.
    docs.value = [{
        id: `doc_${Date.now()}`,
        name: props.id && props.id !== 'new' ? 'Loaded Image' : 'Untitled',
        docId: props.id,
        state: null,
        dirty: false
    }];
    activeDocIndex.value = 0;

    if (props.id && props.id !== 'new') {
        await loadImage(props.id);
    } else {
        await initNewBlankCanvas();
    }

    await nextTick();
    docs.value[0].state = await serializeDoc();

    if (authStore.user) {
        selectedModel.value = authStore.user.iti_binding_model_name || authStore.user.tti_binding_model_name || '';
    }

    window.addEventListener('keydown', handleKeydown);
    window.addEventListener('keyup', handleKeyup);
});

// Watch for route ID changes when switching between images in sidebar.
// Route transitions reset the tab stack to a single tab for the new image.
watch(() => props.id, async (newId, oldId) => {
    if (newId !== oldId && isComponentMounted.value) {
        docs.value = [{
            id: `doc_${Date.now()}`,
            name: newId && newId !== 'new' ? 'Loaded Image' : 'Untitled',
            docId: newId,
            state: null,
            dirty: false
        }];
        activeDocIndex.value = 0;
        if (newId && newId !== 'new') {
            await loadImage(newId);
        } else {
            await initNewBlankCanvas();
        }
        await nextTick();
        docs.value[0].state = await serializeDoc();
    }
});

onUnmounted(() => { 
    isComponentMounted.value = false; 
    window.removeEventListener('keydown', handleKeydown); 
    window.removeEventListener('keyup', handleKeyup);
});

// Phase 2: live text preview + selection overlay repaint
watch(textEditor, () => {
    if (textEditor.value.visible) renderTextPreview();
}, { deep: true });
watch([() => tool.value, () => selection.value.active, () => selection.value.inverted], () => {
    if (!textEditor.value.visible && !isDrawingSelection.value && !isDrawingCrop.value) {
        drawSelectionOverlay();
    }
});

watch(() => activeTask.value?.status, async (newStatus) => {
    if (newStatus === 'completed' && activeTask.value?.result) {
        isProcessingTask.value = false;
        const res = Array.isArray(activeTask.value.result) ? activeTask.value.result[0] : activeTask.value.result;
        if (res?.id) {
            await loadAiResultOntoCanvas(res.id);
        }
        activeTaskId.value = null;
    } else if (newStatus === 'failed' || newStatus === 'cancelled') {
        isProcessingTask.value = false;
        activeTaskId.value = null;
        uiStore.addNotification('AI task did not complete.', 'error');
    }
});

async function initNewBlankCanvas() {
    const defaultW = 1024, defaultH = 1024;
    canvasWidth.value = defaultW;
    canvasHeight.value = defaultH;
    await nextTick();
    const base = layers.value.find(l => l.id === 'base') || layers.value[0];
    if (base?.el) {
        base.ctx = base.el.getContext('2d');
        base.ctx.fillStyle = '#FFFFFF';
        base.ctx.fillRect(0, 0, defaultW, defaultH);
    }
    flushSaveState();
    fitToScreen();
}

async function loadImage(id) {
    if (!id || id === 'new') {
        initNewBlankCanvas();
        return;
    }
    try {
        const res = await apiClient.get(`/api/image-studio/${id}/file`, { responseType: 'blob' });
        const img = new Image();
        await new Promise((resolve, reject) => { 
            img.onload = resolve; 
            img.onerror = reject; 
            img.src = URL.createObjectURL(res.data); 
        });

        const w = img.naturalWidth;
        const h = img.naturalHeight;

        canvasWidth.value = w; 
        canvasHeight.value = h;

        // Reset layer stack to single base plate for the newly loaded image
        layers.value = [
            { 
                id: 'base', 
                name: 'Base Image Plate', 
                visible: true, 
                order: 0, 
                el: null, 
                ctx: null, 
                opacity: 1.0, 
                blendMode: 'normal',
                locked: false,
                thumbnail: null,
                adjustments: defaultAdjustments() 
            }
        ];
        activeLayerId.value = 'base';
        history.value = [];
        historyIndex.value = -1;

        await nextTick();
        const base = layers.value.find(l => l.id === 'base') || layers.value[0];
        if (base?.el) {
            base.ctx = base.el.getContext('2d');
            base.ctx.clearRect(0, 0, w, h);
            base.ctx.drawImage(img, 0, 0);
        }

        if (maskCanvasRef.value && ctxMask.value) {
            ctxMask.value.clearRect(0, 0, w, h);
        }

        flushSaveState(); 
        refreshAllLayerThumbnails();
        fitToScreen();
    } catch (e) { 
        console.error("Failed to load image:", e);
        router.push('/image-studio'); 
    }
}

function setTool(t) { tool.value = t; }

function setLayerCanvasRef(layer, el) {
    if (el) {
        layer.el = el;
        layer.ctx = el.getContext('2d');
    }
}

function toggleLayerVisibility(layer) {
    layer.visible = !layer.visible;
    saveState();
}

function addNewLayer(name = null) {
    const id = `layer_${Date.now()}`;
    layers.value.push({ 
        id, 
        name: name || `Layer ${layers.value.length}`, 
        visible: true, 
        order: layers.value.length, 
        el: null, 
        ctx: null, 
        opacity: 1.0,
        blendMode: 'normal',
        locked: false,
        thumbnail: null,
        adjustments: defaultAdjustments()
    });
    activeLayerId.value = id;
    nextTick(() => {
        const l = layers.value.find(x => x.id === id);
        if (l?.el) {
            l.ctx = l.el.getContext('2d');
        }
        saveState();
    });
}

function duplicateActiveLayer() {
    if (activeLayerId.value === 'mask') return;
    const srcLayer = activeLayer.value;
    const newId = `layer_${Date.now()}`;
    const newLayer = {
        id: newId,
        name: `${srcLayer.name} Copy`,
        visible: true,
        order: layers.value.length,
        el: null,
        ctx: null,
        opacity: srcLayer.opacity,
        blendMode: srcLayer.blendMode,
        locked: false,
        thumbnail: null,
        adjustments: srcLayer.adjustments ? { ...srcLayer.adjustments } : defaultAdjustments()
    };
    layers.value.push(newLayer);
    activeLayerId.value = newId;
    nextTick(() => {
        const l = layers.value.find(x => x.id === newId);
        if (l && l.el) {
            l.el.width = imageCanvasRef.value.width;
            l.el.height = imageCanvasRef.value.height;
            l.ctx = l.el.getContext('2d');
            if (srcLayer.ctx) {
                l.ctx.drawImage(srcLayer.ctx.canvas, 0, 0);
            }
            saveState();
        }
    });
}

function mergeLayerDown() {
    if (layers.value.length <= 1 || activeLayerId.value === 'base' || activeLayerId.value === 'mask') return;
    const activeIdx = layers.value.findIndex(l => l.id === activeLayerId.value);
    if (activeIdx <= 0) return;
    
    const targetLayer = layers.value[activeIdx - 1];
    const currentLayer = layers.value[activeIdx];
    
    if (targetLayer.ctx && currentLayer.ctx) {
        targetLayer.ctx.save();
        targetLayer.ctx.globalAlpha = currentLayer.opacity;
        targetLayer.ctx.globalCompositeOperation = currentLayer.blendMode || 'source-over';
        targetLayer.ctx.drawImage(currentLayer.ctx.canvas, 0, 0);
        targetLayer.ctx.restore();
    }
    
    layers.value.splice(activeIdx, 1);
    activeLayerId.value = targetLayer.id;
    saveState();
    uiStore.addNotification('Layers merged down.', 'info', 1500);
}

function deleteLayer(id) { 
    if (id === 'base') return; 
    layers.value = layers.value.filter(l => l.id !== id); 
    if (activeLayerId.value === id) activeLayerId.value = 'base'; 
    saveState();
}

function flipActiveLayerHorizontal() {
    const l = activeLayer.value;
    if (!l?.ctx) return;
    const temp = document.createElement('canvas');
    temp.width = l.ctx.canvas.width;
    temp.height = l.ctx.canvas.height;
    const tc = temp.getContext('2d');
    tc.translate(temp.width, 0);
    tc.scale(-1, 1);
    tc.drawImage(l.ctx.canvas, 0, 0);
    l.ctx.clearRect(0, 0, temp.width, temp.height);
    l.ctx.drawImage(temp, 0, 0);
    saveState();
    uiStore.addNotification('Layer flipped horizontally.', 'info', 1000);
}

function flipActiveLayerVertical() {
    const l = activeLayer.value;
    if (!l?.ctx) return;
    const temp = document.createElement('canvas');
    temp.width = l.ctx.canvas.width;
    temp.height = l.ctx.canvas.height;
    const tc = temp.getContext('2d');
    tc.translate(0, temp.height);
    tc.scale(1, -1);
    tc.drawImage(l.ctx.canvas, 0, 0);
    l.ctx.clearRect(0, 0, temp.width, temp.height);
    l.ctx.drawImage(temp, 0, 0);
    saveState();
    uiStore.addNotification('Layer flipped vertically.', 'info', 1000);
}

function rotateActiveLayer(deg) {
    const l = activeLayer.value;
    if (!l?.ctx) return;
    const temp = document.createElement('canvas');
    temp.width = l.ctx.canvas.width;
    temp.height = l.ctx.canvas.height;
    const tc = temp.getContext('2d');
    tc.translate(temp.width / 2, temp.height / 2);
    tc.rotate((deg * Math.PI) / 180);
    tc.drawImage(l.ctx.canvas, -temp.width / 2, -temp.height / 2);
    l.ctx.clearRect(0, 0, temp.width, temp.height);
    l.ctx.drawImage(temp, 0, 0);
    saveState();
}

async function expandCanvas(direction, amount = 256) {
    const oldW = canvasWidth.value;
    const oldH = canvasHeight.value;
    const newW = direction === 'horizontal' ? oldW + amount : oldW;
    const newH = direction === 'vertical' ? oldH + amount : oldH;

    const offsetX = direction === 'horizontal' ? amount / 2 : 0;
    const offsetY = direction === 'vertical' ? amount / 2 : 0;

    // 1. Snapshot all layer contents offscreen before dimensions change
    const layerSnapshots = layers.value.map(l => {
        if (!l.el) return null;
        const temp = document.createElement('canvas');
        temp.width = oldW;
        temp.height = oldH;
        temp.getContext('2d').drawImage(l.el, 0, 0);
        return { layerId: l.id, canvas: temp };
    }).filter(Boolean);

    // Snapshot mask if it exists
    let maskSnapshot = null;
    if (maskCanvasRef.value && ctxMask.value) {
        const tempMask = document.createElement('canvas');
        tempMask.width = oldW;
        tempMask.height = oldH;
        tempMask.getContext('2d').drawImage(maskCanvasRef.value, 0, 0);
        maskSnapshot = tempMask;
    }

    // 2. Reactively update canvas dimensions across all template bound elements
    canvasWidth.value = newW;
    canvasHeight.value = newH;

    // 3. Await Vue DOM template update
    await nextTick();

    // 4. Redraw layers centered at the new offset
    layerSnapshots.forEach(snap => {
        const l = layers.value.find(x => x.id === snap.layerId);
        if (l?.ctx) {
            l.ctx.clearRect(0, 0, newW, newH);
            l.ctx.drawImage(snap.canvas, offsetX, offsetY);
        }
    });

    // Redraw mask centered
    if (maskSnapshot && ctxMask.value) {
        ctxMask.value.clearRect(0, 0, newW, newH);
        ctxMask.value.drawImage(maskSnapshot, offsetX, offsetY);
    }

    saveState();
    fitToScreen();
    uiStore.addNotification(`Canvas expanded to ${newW}×${newH}px.`, 'success');
}

function clearMask() {
    if (ctxMask.value && maskCanvasRef.value) {
        ctxMask.value.clearRect(0, 0, maskCanvasRef.value.width, maskCanvasRef.value.height);
        saveState();
    }
}

function invertMask() {
    if (!ctxMask.value || !maskCanvasRef.value) return;
    const w = maskCanvasRef.value.width, h = maskCanvasRef.value.height;
    const imgData = ctxMask.value.getImageData(0, 0, w, h);
    const d = imgData.data;
    for (let i = 0; i < d.length; i += 4) {
        d[i+3] = 255 - d[i+3];
        d[i] = 255; d[i+1] = 255; d[i+2] = 255;
    }
    ctxMask.value.putImageData(imgData, 0, 0);
    saveState();
}

function getPointerPos(e) {
    const r = imageCanvasRef.value.getBoundingClientRect();
    const sX = imageCanvasRef.value.width / r.width, sY = imageCanvasRef.value.height / r.height;
    return { x: (e.clientX - r.left) * sX, y: (e.clientY - r.top) * sY };
}

function sampleColorAtPoint(x, y) {
    const comp = document.createElement('canvas');
    comp.width = imageCanvasRef.value.width;
    comp.height = imageCanvasRef.value.height;
    const cc = comp.getContext('2d');
    
    layers.value.filter(l => l.visible).forEach(l => {
        if (l.ctx) {
            cc.globalAlpha = l.opacity; 
            cc.globalCompositeOperation = l.blendMode || 'source-over';
            cc.drawImage(l.ctx.canvas, 0, 0);
        }
    });
    
    const p = cc.getImageData(Math.floor(x), Math.floor(y), 1, 1).data;
    const hex = `#${((1 << 24) + (p[0] << 16) + (p[1] << 8) + p[2]).toString(16).slice(1)}`;
    color.value = hex;
    keyColor.value = hex;
    if (!recentColors.value.includes(hex)) {
        recentColors.value.unshift(hex);
        if (recentColors.value.length > 7) recentColors.value.pop();
    }
    uiStore.addNotification(`Sampled Color: ${hex}`, 'info', 1000);
}

function executeChromaKey({ targetCtx, hexColor, tolerance = 28, softness = 12, spillSuppression = true }) {
    if (!targetCtx) return;
    const w = targetCtx.canvas.width;
    const h = targetCtx.canvas.height;
    const imgData = targetCtx.getImageData(0, 0, w, h);
    const d = imgData.data;

    const kr = parseInt(hexColor.slice(1, 3), 16);
    const kg = parseInt(hexColor.slice(3, 5), 16);
    const kb = parseInt(hexColor.slice(5, 7), 16);

    const maxDist = 441.67;
    const tolThreshold = (tolerance / 100) * maxDist;
    const softThreshold = (softness / 100) * 120;

    for (let i = 0; i < d.length; i += 4) {
        const r = d[i];
        const g = d[i+1];
        const b = d[i+2];
        const a = d[i+3];

        if (a === 0) continue;

        const dr = r - kr;
        const dg = g - kg;
        const db = b - kb;
        const dist = Math.sqrt(dr*dr + dg*dg + db*db);

        if (dist <= tolThreshold) {
            d[i+3] = 0;
        } else if (dist < tolThreshold + softThreshold && softThreshold > 0) {
            const factor = (dist - tolThreshold) / softThreshold;
            d[i+3] = Math.round(a * factor);

            if (spillSuppression) {
                if (kg > kr && kg > kb) {
                    d[i+1] = Math.min(g, Math.round((r + b) / 2));
                } else if (kr > kg && kb > kg) {
                    d[i] = Math.min(r, Math.round(g * 1.1));
                    d[i+2] = Math.min(b, Math.round(g * 1.1));
                }
            }
        }
    }

    targetCtx.putImageData(imgData, 0, 0);
}

function executeChromaKeyOnActiveLayer() {
    const l = activeLayer.value;
    if (!l?.ctx) return;
    executeChromaKey({
        targetCtx: l.ctx,
        hexColor: keyColor.value,
        tolerance: keyTolerance.value,
        softness: keySoftness.value,
        spillSuppression: keySpillSuppression.value
    });
    saveState();
    uiStore.addNotification(`Color ${keyColor.value} keyed out of layer.`, 'success');
}

function keyOutColorAtPoint(x, y) {
    const l = activeLayer.value;
    if (!l?.ctx) return;
    const p = l.ctx.getImageData(Math.floor(x), Math.floor(y), 1, 1).data;
    const hex = `#${((1 << 24) + (p[0] << 16) + (p[1] << 8) + p[2]).toString(16).slice(1)}`;
    keyColor.value = hex;
    executeChromaKey({
        targetCtx: l.ctx,
        hexColor: hex,
        tolerance: brushSize.value ? Math.min(brushSize.value, 60) : keyTolerance.value,
        softness: keySoftness.value,
        spillSuppression: keySpillSuppression.value
    });
    saveState();
    uiStore.addNotification(`Keyed out ${hex} from layer.`, 'info', 1500);
}

function startAction(e) {
    if (e.button !== 0) return;
    const { x, y } = getPointerPos(e);

    // Phase 2: capture pre-stroke state when a selection is active so painted
    // pixels outside the mask can be reverted after the stroke commits.
    if (selection.value.active && activeLayerId.value !== 'mask'
        && ['brush','eraser','clone','line','rect','circle','gradient','fill','heal','dodge','burn','smudge','text'].includes(tool.value)) {
        const ac = getActiveContext();
        if (ac) {
            const s = document.createElement('canvas');
            s.width = ac.canvas.width; s.height = ac.canvas.height;
            s.getContext('2d').drawImage(ac.canvas, 0, 0);
            preStrokeSnapshot.value = s;
        }
    }

    if (tool.value === 'eyedropper') {
        sampleColorAtPoint(x, y);
        return;
    }

    if (tool.value === 'colorkey') {
        keyOutColorAtPoint(x, y);
        return;
    }
    
    if (tool.value === 'clone' && settingCloneAnchor.value) { 
        cloneAnchor.value = { x, y }; 
        settingCloneAnchor.value = false; 
        uiStore.addNotification('Clone anchor set.', 'success', 1000);
        return; 
    }
    
    if (tool.value === 'wand') { 
        magicWandTransparency(x, y); 
        return; 
    }
    
    isDragging = true; 
    lastX = e.clientX; 
    lastY = e.clientY; 
    startX = x; 
    startY = y;
    
    // ── Phase 2 tool branches ──
    if (['marquee', 'ellipse-select', 'lasso'].includes(tool.value)) {
        isDrawingSelection.value = true;
        selection.value = {
            active: false,
            type: tool.value === 'ellipse-select' ? 'ellipse' : (tool.value === 'lasso' ? 'lasso' : 'rect'),
            points: tool.value === 'lasso' ? [{ x, y }] : [],
            bounds: { x: startX, y: startY, w: 0, h: 0 },
            inverted: false
        };
        drawSelectionOverlay();
        return;
    }
    if (tool.value === 'crop') {
        isDrawingCrop.value = true;
        cropRect.value = { x: startX, y: startY, w: 0, h: 0 };
        drawSelectionOverlay();
        return;
    }
    if (tool.value === 'move') {
        const c = getActiveContext();
        if (c) {
            const snap = document.createElement('canvas');
            snap.width = c.canvas.width;
            snap.height = c.canvas.height;
            snap.getContext('2d').drawImage(c.canvas, 0, 0);
            moveSnapshot.value = snap;
            moveStartPx.value = { x, y };
        }
        return;
    }
    if (tool.value === 'fill') {
        floodFillAt(x, y);
        if (preStrokeSnapshot.value) { commitSelectionMask(preStrokeSnapshot.value); preStrokeSnapshot.value = null; }
        isDragging = false;
        return;
    }
    if (tool.value === 'heal') {
        spotHealAt(x, y);
        if (preStrokeSnapshot.value) { commitSelectionMask(preStrokeSnapshot.value); preStrokeSnapshot.value = null; }
        isDragging = false;
        return;
    }
    if (['dodge', 'burn', 'smudge'].includes(tool.value)) {
        retouchSample.value = { x, y };
        applyRetouchBrush(x, y);
        return;
    }
    if (tool.value === 'text') {
        textEditor.value = {
            visible: true,
            x, y,
            text: '',
            fontFamily: 'Inter, sans-serif',
            fontSize: 48,
            fontWeight: 'bold',
            italic: false,
            underline: false,
            align: 'left',
            color: color.value,
            shadow: true,
            rotation: 0
        };
        isDragging = false;
        return;
    }
    if (['brush', 'eraser', 'clone'].includes(tool.value)) {
        const c = getActiveContext(); 
        c.beginPath(); 
        c.moveTo(x, y);
    }
}

function handleMove(e) {
    const { x, y } = getPointerPos(e); 
    cursorX.value = x; 
    cursorY.value = y;
    if (!isDragging) return;

    // ── Phase 2: selection / crop / move / retouch branches ──
    if (isDrawingSelection.value) {
        const sel = selection.value;
        if (sel.type === 'lasso') {
            sel.points.push({ x, y });
        } else {
            sel.bounds = { x: startX, y: startY, w: x - startX, h: y - startY };
        }
        drawSelectionOverlay();
        return;
    }
    if (isDrawingCrop.value && cropRect.value) {
        let cw = x - startX;
        let ch = y - startY;
        if (cropAspect.value) {
            const signH = Math.sign(ch) || 1;
            ch = signH * Math.abs(cw) / cropAspect.value;
        }
        cropRect.value = { x: startX, y: startY, w: cw, h: ch };
        drawSelectionOverlay();
        return;
    }
    if (tool.value === 'move' && moveSnapshot.value && moveStartPx.value) {
        const c = getActiveContext();
        if (c) {
            const dx = x - moveStartPx.value.x;
            const dy = y - moveStartPx.value.y;
            c.clearRect(0, 0, c.canvas.width, c.canvas.height);
            c.drawImage(moveSnapshot.value, dx, dy);
        }
        return;
    }
    if (['dodge', 'burn', 'smudge'].includes(tool.value)) {
        applyRetouchBrush(x, y);
        return;
    }
    
    if (tool.value === 'pan' && e.shiftKey) {
        const c = getActiveContext(); 
        const t = document.createElement('canvas');
        t.width = c.canvas.width; 
        t.height = c.canvas.height; 
        t.getContext('2d').drawImage(c.canvas, 0, 0);
        c.clearRect(0,0,t.width,t.height); 
        c.drawImage(t, (x - startX), (y - startY));
    } else if (tool.value === 'pan') { 
        panX.value += e.clientX - lastX; 
        panY.value += e.clientY - lastY; 
        lastX = e.clientX; 
        lastY = e.clientY; 
    }
    else if (['brush', 'eraser'].includes(tool.value)) draw(x, y);
    else if (tool.value === 'clone') drawClone(x, y);
    else if (['line', 'rect', 'circle', 'gradient'].includes(tool.value)) drawPreviewShape(x, y);
}

function endAction() { 
    if (!isDragging) return; 
    isDragging = false; 
    if (['line', 'rect', 'circle', 'gradient'].includes(tool.value)) {
        commitShape(getPointerPos({ clientX: lastX, clientY: lastY })); 
    }

    if (isDrawingSelection.value) {
        isDrawingSelection.value = false;
        finalizeSelection();
        drawSelectionOverlay();
    }
    if (isDrawingCrop.value) {
        isDrawingCrop.value = false;
        const r = cropRect.value;
        if (r) {
            if (r.w < 0) { r.x += r.w; r.w = -r.w; }
            if (r.h < 0) { r.y += r.h; r.h = -r.h; }
        }
        drawSelectionOverlay();
    }
    if (tool.value === 'move') {
        moveSnapshot.value = null;
        moveStartPx.value = null;
    }
    if (['dodge', 'burn', 'smudge'].includes(tool.value)) {
        retouchSample.value = null;
    }
    if (preStrokeSnapshot.value) {
        commitSelectionMask(preStrokeSnapshot.value);
        preStrokeSnapshot.value = null;
    }
    flushSaveState(); 
}

function getActiveContext() { 
    if (activeLayerId.value === 'mask') return ctxMask.value; 
    return activeLayer.value.ctx; 
}

function draw(x, y) {
    const c = getActiveContext(); 
    if (!c) return;
    c.lineCap = 'round'; 
    c.lineJoin = 'round'; 
    c.lineWidth = brushSize.value;
    c.globalCompositeOperation = tool.value === 'eraser' ? 'destination-out' : 'source-over';
    c.strokeStyle = activeLayerId.value === 'mask' ? '#FFFFFF' : color.value;
    c.lineTo(x, y); 
    c.stroke(); 
    c.beginPath(); 
    c.moveTo(x, y);
}

function drawClone(x, y) {
    if (!cloneAnchor.value) return;
    const c = getActiveContext(); 
    if (!c) return;
    c.save(); 
    c.beginPath(); 
    c.arc(x, y, brushSize.value/2, 0, Math.PI*2); 
    c.clip();
    c.drawImage(
        imageCanvasRef.value, 
        cloneAnchor.value.x + (x - startX) - brushSize.value/2, 
        cloneAnchor.value.y + (y - startY) - brushSize.value/2, 
        brushSize.value, brushSize.value, 
        x - brushSize.value/2, y - brushSize.value/2, 
        brushSize.value, brushSize.value
    );
    c.restore();
}

function drawPreviewShape(x, y) {
    const c = ctxPreview.value; 
    if (!c) return;
    c.clearRect(0,0,c.canvas.width,c.canvas.height);
    c.strokeStyle = color.value; 
    c.lineWidth = 2; 
    c.beginPath();
    
    if (tool.value === 'line') { 
        c.moveTo(startX, startY); 
        c.lineTo(x, y); 
    }
    else if (tool.value === 'rect') c.rect(startX, startY, x-startX, y-startY);
    else if (tool.value === 'circle') c.arc(startX, startY, Math.sqrt(Math.pow(x-startX,2)+Math.pow(y-startY,2)), 0, Math.PI*2);
    else if (tool.value === 'gradient') {
        const grad = c.createLinearGradient(startX, startY, x, y);
        grad.addColorStop(0, color.value);
        grad.addColorStop(1, secondaryColor.value);
        c.fillStyle = grad;
        c.fillRect(0, 0, c.canvas.width, c.canvas.height);
    }
    c.stroke();
}

function commitShape(pos) {
    if (ctxPreview.value) {
        ctxPreview.value.clearRect(0,0,previewCanvasRef.value.width,previewCanvasRef.value.height);
    }
    const c = getActiveContext(); 
    if (!c) return;
    c.strokeStyle = color.value; 
    c.fillStyle = color.value; 
    c.lineWidth = brushSize.value; 
    c.beginPath();
    
    if (tool.value === 'line') { 
        c.moveTo(startX, startY); 
        c.lineTo(pos.x, pos.y); 
        c.stroke(); 
    }
    else if (tool.value === 'rect') { 
        c.rect(startX, startY, pos.x-startX, pos.y-startY); 
        c.fill(); 
    }
    else if (tool.value === 'circle') { 
        c.arc(startX, startY, Math.sqrt(Math.pow(pos.x-startX,2)+Math.pow(pos.y-startY,2)), 0, Math.PI*2); 
        c.fill(); 
    }
    else if (tool.value === 'gradient') {
        const grad = c.createLinearGradient(startX, startY, pos.x, pos.y);
        grad.addColorStop(0, color.value);
        grad.addColorStop(1, secondaryColor.value);
        c.fillStyle = grad;
        c.fillRect(0, 0, c.canvas.width, c.canvas.height);
    }
}

function magicWandTransparency(startX, startY) {
    const c = getActiveContext(); 
    if(!c) return;
    const w = c.canvas.width, h = c.canvas.height;
    const imgData = c.getImageData(0,0,w,h); 
    const data = imgData.data;
    const pos = (Math.floor(startY) * w + Math.floor(startX)) * 4;
    const tr = data[pos], tg = data[pos+1], tb = data[pos+2], tol = brushSize.value * 2.55;
    
    for (let i = 0; i < data.length; i += 4) {
        if (Math.abs(data[i]-tr) < tol && Math.abs(data[i+1]-tg) < tol && Math.abs(data[i+2]-tb) < tol) {
            data[i+3] = 0;
        }
    }
    c.putImageData(imgData, 0, 0); 
    saveState();
}

// ───────────────────────────────────────────────────────────
// PHASE 2 — Selection / Crop / Retouch / Text
// ───────────────────────────────────────────────────────────

function applySelectionClip(ctx, forceInverted = null) {
    const sel = selection.value;
    if (!sel.active) return;
    const W = ctx.canvas.width;
    const H = ctx.canvas.height;
    const invert = forceInverted === null ? sel.inverted : forceInverted;
    ctx.beginPath();
    if (sel.type === 'rect') {
        const b = sel.bounds;
        if (invert) {
            ctx.rect(0, 0, W, H);
            ctx.rect(b.x, b.y, b.w, b.h);
            ctx.clip('evenodd');
        } else {
            ctx.rect(b.x, b.y, b.w, b.h);
            ctx.clip();
        }
    } else if (sel.type === 'ellipse') {
        const b = sel.bounds;
        const cx = b.x + b.w / 2, cy = b.y + b.h / 2;
        const rx = Math.abs(b.w / 2), ry = Math.abs(b.h / 2);
        if (invert) {
            ctx.rect(0, 0, W, H);
            ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
            ctx.clip('evenodd');
        } else {
            ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
            ctx.clip();
        }
    } else if (sel.type === 'lasso' && sel.points.length > 2) {
        const pts = sel.points;
        if (invert) {
            ctx.rect(0, 0, W, H);
            ctx.moveTo(pts[0].x, pts[0].y);
            for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
            ctx.closePath();
            ctx.clip('evenodd');
        } else {
            ctx.moveTo(pts[0].x, pts[0].y);
            for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
            ctx.closePath();
            ctx.clip();
        }
    }
}

function finalizeSelection() {
    const sel = selection.value;
    if (sel.type === 'lasso' && sel.points.length > 2) {
        const xs = sel.points.map(p => p.x), ys = sel.points.map(p => p.y);
        sel.bounds = {
            x: Math.min(...xs), y: Math.min(...ys),
            w: Math.max(...xs) - Math.min(...xs),
            h: Math.max(...ys) - Math.min(...ys)
        };
        sel.active = true;
    } else if (sel.bounds) {
        if (sel.bounds.w < 0) { sel.bounds.x += sel.bounds.w; sel.bounds.w = -sel.bounds.w; }
        if (sel.bounds.h < 0) { sel.bounds.y += sel.bounds.h; sel.bounds.h = -sel.bounds.h; }
        if (sel.bounds.w > 1 && sel.bounds.h > 1) sel.active = true;
        else sel.active = false;
    }
}

function drawSelectionOverlay() {
    const c = ctxPreview.value;
    if (!c) return;
    c.clearRect(0, 0, c.canvas.width, c.canvas.height);

    // Crop preview overlay (marching-box with rule-of-thirds)
    if (cropRect.value && (tool.value === 'crop' || isDrawingCrop.value)) {
        const r = cropRect.value;
        c.save();
        c.fillStyle = 'rgba(0,0,0,0.45)';
        c.fillRect(0, 0, c.canvas.width, c.canvas.height);
        c.clearRect(r.x, r.y, r.w, r.h);
        c.strokeStyle = 'rgba(255,255,255,0.55)';
        c.lineWidth = 1;
        for (let i = 1; i <= 2; i++) {
            c.beginPath();
            c.moveTo(r.x + r.w * i / 3, r.y);
            c.lineTo(r.x + r.w * i / 3, r.y + r.h);
            c.stroke();
            c.beginPath();
            c.moveTo(r.x, r.y + r.h * i / 3);
            c.lineTo(r.x + r.w, r.y + r.h * i / 3);
            c.stroke();
        }
        c.strokeStyle = '#10b981';
        c.lineWidth = 2;
        c.setLineDash([8, 6]);
        c.strokeRect(r.x + 1, r.y + 1, r.w - 2, r.h - 2);
        c.restore();
        return;
    }

    // Marching-ants selection outline
    if (selection.value.active) {
        const sel = selection.value;
        c.save();
        c.lineWidth = 1.5;
        c.strokeStyle = '#ffffff';
        c.setLineDash([6, 4]);
        c.beginPath();
        if (sel.type === 'rect') {
            c.rect(sel.bounds.x, sel.bounds.y, sel.bounds.w, sel.bounds.h);
            c.stroke();
        } else if (sel.type === 'ellipse') {
            const b = sel.bounds;
            c.ellipse(b.x + b.w / 2, b.y + b.h / 2, Math.abs(b.w / 2), Math.abs(b.h / 2), 0, 0, Math.PI * 2);
            c.stroke();
        } else if (sel.type === 'lasso' && sel.points.length > 2) {
            const pts = sel.points;
            c.moveTo(pts[0].x, pts[0].y);
            for (let i = 1; i < pts.length; i++) c.lineTo(pts[i].x, pts[i].y);
            c.closePath();
            c.stroke();
        }
        c.restore();
    }
}

function commitSelectionMask(snapshotCanvas) {
    if (!selection.value.active || !snapshotCanvas) return;
    const c = getActiveContext();
    if (!c) return;
    const w = c.canvas.width, h = c.canvas.height;
    const temp = document.createElement('canvas');
    temp.width = w; temp.height = h;
    const tc = temp.getContext('2d');
    // Start from the edited layer
    tc.drawImage(c.canvas, 0, 0);
    // Restore the pre-stroke snapshot ONLY outside the effective selection.
    // For a normal selection, "outside" = inverted; for an inverted selection,
    // "outside of the selection intent" is the drawn shape itself.
    tc.save();
    applySelectionClip(tc, !selection.value.inverted);
    tc.drawImage(snapshotCanvas, 0, 0);
    tc.restore();
    c.clearRect(0, 0, w, h);
    c.drawImage(temp, 0, 0);
}

function selectAll() {
    selection.value = {
        active: true, type: 'rect', points: [],
        bounds: { x: 0, y: 0, w: canvasWidth.value, h: canvasHeight.value },
        inverted: false
    };
    drawSelectionOverlay();
    uiStore.addNotification('Select all.', 'info', 900);
}

function deselectAll() {
    selection.value = { active: false, type: null, points: [], bounds: null, inverted: false };
    drawSelectionOverlay();
}

function invertSelection() {
    if (!selection.value.active) return;
    selection.value.inverted = !selection.value.inverted;
    drawSelectionOverlay();
}

function deleteSelectionContent() {
    if (!selection.value.active) return;
    const c = getActiveContext();
    if (!c) return;
    c.save();
    applySelectionClip(c);
    c.globalCompositeOperation = 'destination-out';
    c.fillStyle = '#000';
    c.fillRect(0, 0, c.canvas.width, c.canvas.height);
    c.restore();
    flushSaveState();
    uiStore.addNotification('Selection content deleted.', 'success', 1400);
}

function selectionToMask() {
    if (!selection.value.active || !ctxMask.value) return;
    if (selection.value.inverted) {
        uiStore.addNotification('Inverted selection cannot be converted to mask.', 'warning');
        return;
    }
    const c = ctxMask.value;
    c.save();
    c.clearRect(0, 0, c.canvas.width, c.canvas.height);
    c.fillStyle = '#FFFFFF';
    const sel = selection.value;
    c.beginPath();
    if (sel.type === 'rect') {
        c.rect(sel.bounds.x, sel.bounds.y, sel.bounds.w, sel.bounds.h);
    } else if (sel.type === 'ellipse') {
        const b = sel.bounds;
        c.ellipse(b.x + b.w / 2, b.y + b.h / 2, Math.abs(b.w / 2), Math.abs(b.h / 2), 0, 0, Math.PI * 2);
    } else if (sel.type === 'lasso' && sel.points.length > 2) {
        const pts = sel.points;
        c.moveTo(pts[0].x, pts[0].y);
        for (let i = 1; i < pts.length; i++) c.lineTo(pts[i].x, pts[i].y);
        c.closePath();
    }
    c.fill();
    c.restore();
    activeLayerId.value = 'mask';
    flushSaveState();
    uiStore.addNotification('Selection → inpaint mask.', 'success', 1500);
}

function applyCrop() {
    if (!cropRect.value) return;
    const r = cropRect.value;
    const nx = Math.round(Math.max(0, Math.min(r.x, canvasWidth.value - 2)));
    const ny = Math.round(Math.max(0, Math.min(r.y, canvasHeight.value - 2)));
    const nw = Math.round(Math.max(2, Math.min(r.w, canvasWidth.value - nx)));
    const nh = Math.round(Math.max(2, Math.min(r.h, canvasHeight.value - ny)));

    const layerSnaps = layers.value.map(l => {
        if (!l.ctx) return null;
        const t = document.createElement('canvas');
        t.width = nw; t.height = nh;
        t.getContext('2d').drawImage(l.ctx.canvas, nx, ny, nw, nh, 0, 0, nw, nh);
        return { id: l.id, canvas: t };
    }).filter(Boolean);

    let maskSnap = null;
    if (maskCanvasRef.value && ctxMask.value) {
        maskSnap = document.createElement('canvas');
        maskSnap.width = nw; maskSnap.height = nh;
        maskSnap.getContext('2d').drawImage(maskCanvasRef.value, nx, ny, nw, nh, 0, 0, nw, nh);
    }

    cropRect.value = null;
    canvasWidth.value = nw;
    canvasHeight.value = nh;

    nextTick(() => {
        layerSnaps.forEach(snap => {
            const l = layers.value.find(x => x.id === snap.id);
            if (l?.ctx) {
                l.ctx.clearRect(0, 0, nw, nh);
                l.ctx.drawImage(snap.canvas, 0, 0);
            }
        });
        if (maskSnap && ctxMask.value) {
            ctxMask.value.clearRect(0, 0, nw, nh);
            ctxMask.value.drawImage(maskSnap, 0, 0);
        }
        deselectAll();
        ctxPreview.value?.clearRect(0, 0, nw, nh);
        fitToScreen();
        refreshAllLayerThumbnails();
        flushSaveState();
        uiStore.addNotification(`Cropped to ${nw} × ${nh}px.`, 'success');
    });
}

function cancelCrop() {
    cropRect.value = null;
    drawSelectionOverlay();
}

function floodFillAt(x, y) {
    const c = getActiveContext();
    if (!c) return;
    const w = c.canvas.width, h = c.canvas.height;

    if (selection.value.active && activeLayerId.value !== 'mask') {
        c.save();
        applySelectionClip(c);
        c.fillStyle = color.value;
        c.fillRect(0, 0, w, h);
        c.restore();
        flushSaveState();
        uiStore.addNotification('Filled selection.', 'success', 1000);
        return;
    }

    const px = Math.floor(x), py = Math.floor(y);
    if (px < 0 || py < 0 || px >= w || py >= h) return;

    const imgData = c.getImageData(0, 0, w, h);
    const d = imgData.data;
    const startIdx = (py * w + px) * 4;
    const tr = d[startIdx], tg = d[startIdx + 1], tb = d[startIdx + 2], ta = d[startIdx + 3];

    const hex = color.value.replace('#', '');
    const fr = parseInt(hex.slice(0, 2), 16);
    const fg = parseInt(hex.slice(2, 4), 16);
    const fb = parseInt(hex.slice(4, 6), 16);

    const tol = Math.max(1, brushSize.value) * 2.55;
    const visited = new Uint8Array(w * h);
    const stack = [[px, py]];

    const matches = (idx) => {
        const p = idx * 4;
        const dr = d[p] - tr, dg = d[p + 1] - tg, db = d[p + 2] - tb, da = d[p + 3] - ta;
        return Math.sqrt(dr * dr + dg * dg + db * db + da * da) <= tol;
    };

    while (stack.length) {
        const [cx, cy] = stack.pop();
        if (cx < 0 || cx >= w || cy < 0 || cy >= h) continue;
        const pi = cy * w + cx;
        if (visited[pi] || !matches(pi)) continue;
        visited[pi] = 1;
        const p = pi * 4;
        d[p] = fr; d[p + 1] = fg; d[p + 2] = fb; d[p + 3] = 255;
        stack.push([cx + 1, cy], [cx - 1, cy], [cx, cy + 1], [cx, cy - 1]);
    }

    c.putImageData(imgData, 0, 0);
    flushSaveState();
    uiStore.addNotification('Region filled.', 'success', 1000);
}

function spotHealAt(x, y) {
    const c = getActiveContext();
    if (!c) return;
    const w = c.canvas.width, h = c.canvas.height;
    const radius = Math.max(4, brushSize.value / 2);
    const imgData = c.getImageData(0, 0, w, h);
    const d = imgData.data;

    let rSum = 0, gSum = 0, bSum = 0, aSum = 0, count = 0;
    const ringR = radius * 1.5;
    for (let a = 0; a < Math.PI * 2; a += Math.PI / 16) {
        const rx = Math.floor(x + Math.cos(a) * ringR);
        const ry = Math.floor(y + Math.sin(a) * ringR);
        if (rx < 0 || ry < 0 || rx >= w || ry >= h) continue;
        const p = (ry * w + rx) * 4;
        rSum += d[p]; gSum += d[p + 1]; bSum += d[p + 2]; aSum += d[p + 3];
        count++;
    }
    if (count === 0) return;
    const ar = rSum / count, ag = gSum / count, ab = bSum / count, aa = aSum / count;

    const cx = Math.floor(x), cy = Math.floor(y);
    const ir = Math.ceil(radius);
    for (let oy = -ir; oy <= ir; oy++) {
        for (let ox = -ir; ox <= ir; ox++) {
            const dist = Math.sqrt(ox * ox + oy * oy);
            if (dist > radius) continue;
            const pX = cx + ox, pY = cy + oy;
            if (pX < 0 || pY < 0 || pX >= w || pY >= h) continue;
            const p = (pY * w + pX) * 4;
            const t = 1 - dist / radius;
            d[p]     = d[p]     * (1 - t) + ar * t;
            d[p + 1] = d[p + 1] * (1 - t) + ag * t;
            d[p + 2] = d[p + 2] * (1 - t) + ab * t;
            d[p + 3] = d[p + 3] * (1 - t) + aa * t;
        }
    }

    c.putImageData(imgData, 0, 0);
    flushSaveState();
}

function applyRetouchBrush(x, y) {
    const c = getActiveContext();
    if (!c) return;
    const w = c.canvas.width, h = c.canvas.height;
    const radius = Math.max(3, brushSize.value / 2);
    const cx = Math.floor(x), cy = Math.floor(y);
    const ir = Math.ceil(radius);
    const x0 = Math.max(0, cx - ir), y0 = Math.max(0, cy - ir);
    const x1 = Math.min(w, cx + ir + 1), y1 = Math.min(h, cy + ir + 1);
    if (x1 <= x0 || y1 <= y0) return;
    const lw = x1 - x0, lh = y1 - y0;
    const imgData = c.getImageData(x0, y0, lw, lh);
    const d = imgData.data;

    const strength = 0.15;

    if (tool.value === 'dodge' || tool.value === 'burn') {
        const dir = tool.value === 'dodge' ? 1 : -1;
        for (let py = 0; py < lh; py++) {
            for (let px = 0; px < lw; px++) {
                const dx = (x0 + px) - cx, dy = (y0 + py) - cy;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist > radius) continue;
                const falloff = 1 - dist / radius;
                const delta = dir * 255 * strength * falloff;
                const idx = (py * lw + px) * 4;
                d[idx]     = Math.min(255, Math.max(0, d[idx]     + delta));
                d[idx + 1] = Math.min(255, Math.max(0, d[idx + 1] + delta));
                d[idx + 2] = Math.min(255, Math.max(0, d[idx + 2] + delta));
            }
        }
        c.putImageData(imgData, x0, y0);
    } else if (tool.value === 'smudge') {
        if (!retouchSample.value) { retouchSample.value = { x, y }; return; }
        const prev = retouchSample.value;
        const dx = x - prev.x;
        const dy = y - prev.y;
        if (dx === 0 && dy === 0) return;
        const srcData = c.getImageData(0, 0, w, h).data;
        for (let py = 0; py < lh; py++) {
            for (let px = 0; px < lw; px++) {
                const wxc = x0 + px, wyc = y0 + py;
                const dist = Math.sqrt((wxc - cx) ** 2 + (wyc - cy) ** 2);
                if (dist > radius) continue;
                const falloff = (1 - dist / radius) * 0.7;
                const sx = Math.round(wxc - dx);
                const sy = Math.round(wyc - dy);
                if (sx < 0 || sy < 0 || sx >= w || sy >= h) continue;
                const srcP = (sy * w + sx) * 4;
                const idx = (py * lw + px) * 4;
                d[idx]     = d[idx]     * (1 - falloff) + srcData[srcP]     * falloff;
                d[idx + 1] = d[idx + 1] * (1 - falloff) + srcData[srcP + 1] * falloff;
                d[idx + 2] = d[idx + 2] * (1 - falloff) + srcData[srcP + 2] * falloff;
                d[idx + 3] = d[idx + 3] * (1 - falloff) + srcData[srcP + 3] * falloff;
            }
        }
        c.putImageData(imgData, x0, y0);
        retouchSample.value = { x, y };
    }
}

function drawTextOnCtx(ctx, te, preview = false) {
    if (!te.text) return;
    ctx.save();
    ctx.translate(te.x, te.y);
    if (te.rotation) ctx.rotate(te.rotation * Math.PI / 180);
    const fontStyle = te.italic ? 'italic ' : '';
    ctx.font = `${fontStyle}${te.fontWeight} ${te.fontSize}px ${te.fontFamily}`;
    ctx.textAlign = te.align === 'center' ? 'center' : te.align === 'right' ? 'right' : 'left';
    ctx.textBaseline = 'top';
    if (te.shadow) {
        ctx.shadowColor = 'rgba(0,0,0,0.5)';
        ctx.shadowBlur = 8;
        ctx.shadowOffsetX = 2;
        ctx.shadowOffsetY = 2;
    }
    ctx.fillStyle = te.color;
    const lines = te.text.split('\n');
    let yy = 0;
    for (const line of lines) {
        ctx.fillText(line, 0, yy);
        if (te.underline) {
            const width = ctx.measureText(line).width;
            const xOff = te.align === 'center' ? -width / 2 : te.align === 'right' ? -width : 0;
            ctx.fillRect(xOff, yy + te.fontSize * 0.95, width, 2);
        }
        yy += te.fontSize * 1.25;
    }
    ctx.restore();
    if (preview) {
        ctx.save();
        ctx.strokeStyle = '#3B82F6';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(te.x, te.y, 4, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
    }
}

function renderTextPreview() {
    if (!textEditor.value.visible) return;
    const c = ctxPreview.value;
    if (!c) return;
    c.clearRect(0, 0, c.canvas.width, c.canvas.height);
    drawTextOnCtx(c, textEditor.value, true);
}

function commitText() {
    const te = textEditor.value;
    if (!te.text) {
        textEditor.value.visible = false;
        ctxPreview.value?.clearRect(0, 0, ctxPreview.value.canvas.width, ctxPreview.value.canvas.height);
        return;
    }
    const c = getActiveContext();
    if (c) drawTextOnCtx(c, te, false);
    if (preStrokeSnapshot.value) {
        commitSelectionMask(preStrokeSnapshot.value);
        preStrokeSnapshot.value = null;
    }
    textEditor.value.visible = false;
    ctxPreview.value?.clearRect(0, 0, ctxPreview.value.canvas.width, ctxPreview.value.canvas.height);
    flushSaveState();
    uiStore.addNotification('Text placed on active layer.', 'success', 1400);
}

function cancelText() {
    textEditor.value.visible = false;
    preStrokeSnapshot.value = null;
    ctxPreview.value?.clearRect(0, 0, ctxPreview.value.canvas.width, ctxPreview.value.canvas.height);
}

function getLayerFilterCss(layer) {
    if (!layer?.adjustments) return 'none';
    const adj = layer.adjustments;
    if (adj.brightness === 1.0 && adj.contrast === 1.0 && adj.saturate === 1.0 && adj.hueRotate === 0 && adj.blur === 0) {
        return 'none';
    }
    return `brightness(${adj.brightness}) contrast(${adj.contrast}) saturate(${adj.saturate}) hue-rotate(${adj.hueRotate}deg) blur(${adj.blur}px)`;
}

function resetAdjustments() {
    if (activeLayer.value?.adjustments) {
        activeLayer.value.adjustments = defaultAdjustments();
        saveState();
    }
}

function bakeAdjustmentsToActiveLayer() {
    const l = activeLayer.value;
    if (!l?.ctx) return;
    const c = document.createElement('canvas');
    c.width = l.ctx.canvas.width;
    c.height = l.ctx.canvas.height;
    const ctx = c.getContext('2d');
    ctx.filter = getLayerFilterCss(l);
    ctx.drawImage(l.ctx.canvas, 0, 0);
    l.ctx.clearRect(0, 0, c.width, c.height);
    l.ctx.drawImage(c, 0, 0);
    l.adjustments = defaultAdjustments();
    saveState();
    uiStore.addNotification('Filter adjustments baked into layer.', 'success');
}

async function enhancePrompt() {
    if (!prompt.value.trim()) return;
    uiStore.openModal('enhancePrompt', {
        onConfirm: async (opts) => {
            const task = await imageStore.enhanceImagePrompt({
                prompt: prompt.value,
                instructions: opts.instructions || '',
                mode: opts.mode || 'description',
                target: 'prompt'
            });
            if (task?.id) {
                const unwatch = watch(() => tasksStore.tasks.find(t => t.id === task.id), (t) => {
                    if (t?.status === 'completed' && t.result?.prompt) {
                        prompt.value = t.result.prompt;
                        unwatch();
                    }
                }, { deep: true });
            }
        }
    });
}

// ── TARGETED AI EDITING METHOD ──
async function executeTargetedAiEdit() {
    if (!prompt.value.trim()) {
        uiStore.addNotification('Please enter an edit prompt.', 'warning');
        return;
    }

    isProcessingTask.value = true;
    
    // 1. Render target source (Active layer OR Full composite)
    const comp = document.createElement('canvas'); 
    comp.width = imageCanvasRef.value.width; 
    comp.height = imageCanvasRef.value.height;
    const cc = comp.getContext('2d');

    if (aiEditTarget.value === 'active' && activeLayer.value?.ctx) {
        cc.globalAlpha = activeLayer.value.opacity;
        cc.drawImage(activeLayer.value.ctx.canvas, 0, 0);
    } else {
        // Flatten all visible layers
        layers.value.filter(l => l.visible).forEach(l => { 
            if (l.ctx) {
                cc.globalAlpha = l.opacity; 
                cc.globalCompositeOperation = l.blendMode || 'source-over';
                cc.drawImage(l.ctx.canvas, 0, 0); 
            }
        });
    }

    const b64 = comp.toDataURL('image/png').split(',')[1];
    const mask64 = (useInpaintMask.value && maskCanvasRef.value) ? maskCanvasRef.value.toDataURL('image/png').split(',')[1] : null;

    try {
        const tsk = await imageStore.editImage({ 
            base_image_b64: b64, 
            mask: mask64, 
            prompt: prompt.value, 
            negative_prompt: negativePrompt.value,
            model: selectedModel.value || authStore.user?.tti_binding_model_name, 
            width: comp.width, 
            height: comp.height,
            strength: editStrength.value
        });
        if (tsk?.id) {
            activeTaskId.value = tsk.id;
        } else {
            isProcessingTask.value = false;
        }
    } catch (e) {
        console.error("AI Edit failed:", e);
        isProcessingTask.value = false;
    }
}

async function generateNewLayerElement() {
    isProcessingTask.value = true;
    
    let colorInstruction = "";
    if (aiKeyScreenMode.value === 'magenta') colorInstruction = " on a solid clean bright magenta background, studio lighting, isolated subject";
    else if (aiKeyScreenMode.value === 'green') colorInstruction = " on a solid green screen background, studio lighting, isolated subject";
    else if (aiKeyScreenMode.value === 'white') colorInstruction = " on a solid clean seamless white background, isolated object";

    const fullPrompt = `${prompt.value}${colorInstruction}`;

    try {
        const tsk = await imageStore.generateImage({
            prompt: fullPrompt, 
            model: selectedModel.value || authStore.user?.tti_binding_model_name, 
            width: imageCanvasRef.value.width, 
            height: imageCanvasRef.value.height, 
            n: 1
        });
        if (tsk?.id) {
            activeTaskId.value = tsk.id;
            const unwatch = watch(() => tasksStore.tasks.find(t => t.id === tsk.id), async (t) => {
                if (t?.status === 'completed' && t.result) {
                    const res = Array.isArray(t.result) ? t.result[0] : t.result;
                    if (res?.id) {
                        await loadGeneratedAssetToLayer(res.id);
                    }
                    unwatch();
                } else if (['failed', 'cancelled'].includes(t?.status)) {
                    isProcessingTask.value = false;
                    unwatch();
                }
            }, { deep: true });
        } else {
            isProcessingTask.value = false;
        }
    } catch (e) { 
        console.error("Layer element generation failed:", e);
        isProcessingTask.value = false; 
    }
}

async function loadGeneratedAssetToLayer(id) {
    try {
        const res = await apiClient.get(`/api/image-studio/${id}/file`, { responseType: 'blob' });
        const img = new Image();
        img.onload = () => {
            addNewLayer(`AI Element (${prompt.value.slice(0, 15)})`);
            nextTick(() => {
                const l = activeLayer.value;
                if (l?.ctx) {
                    l.ctx.drawImage(img, 0, 0);

                    // Automatic Chroma Keying based on selected screen mode
                    if (aiKeyScreenMode.value === 'magenta') {
                        executeChromaKey({ targetCtx: l.ctx, hexColor: '#FF00FF', tolerance: 30, softness: 12, spillSuppression: true });
                    } else if (aiKeyScreenMode.value === 'green') {
                        executeChromaKey({ targetCtx: l.ctx, hexColor: '#00FF00', tolerance: 32, softness: 12, spillSuppression: true });
                    } else if (aiKeyScreenMode.value === 'white') {
                        executeChromaKey({ targetCtx: l.ctx, hexColor: '#FFFFFF', tolerance: 18, softness: 10, spillSuppression: false });
                    }

                    saveState(); 
                    isProcessingTask.value = false;
                    uiStore.addNotification('AI Element added and keyed out to transparent layer!', 'success');
                }
            });
        };
        img.src = URL.createObjectURL(res.data);
    } catch (e) {
        console.error("Failed to load asset to layer:", e);
        isProcessingTask.value = false;
    }
}

function applyQuickModifier(mod) {
    if (!prompt.value.trim()) {
        prompt.value = mod.prompt;
    } else if (!prompt.value.includes(mod.prompt)) {
        prompt.value = `${prompt.value}, ${mod.prompt}`;
    }
    if (mod.negative) {
        if (!negativePrompt.value.trim()) {
            negativePrompt.value = mod.negative;
        } else if (!negativePrompt.value.includes(mod.negative)) {
            negativePrompt.value = `${negativePrompt.value}, ${mod.negative}`;
        }
    }
}

async function loadAiResultOntoCanvas(imageId) {
    try {
        const res = await apiClient.get(`/api/image-studio/${imageId}/file`, { responseType: 'blob' });
        const img = new Image();
        img.onload = () => {
            if (outputAsNewLayer.value) {
                addNewLayer(`AI Edit (${prompt.value.slice(0, 15)})`);
                nextTick(() => {
                    const l = activeLayer.value;
                    if (l?.ctx) {
                        l.ctx.drawImage(img, 0, 0);
                        saveState();
                        uiStore.addNotification('AI Edit added as new layer.', 'success');
                    }
                });
            } else {
                // Replace active layer content
                const l = activeLayer.value;
                if (l?.ctx) {
                    l.ctx.clearRect(0, 0, l.ctx.canvas.width, l.ctx.canvas.height);
                    l.ctx.drawImage(img, 0, 0);
                    saveState();
                    uiStore.addNotification(`Layer '${l.name}' updated with AI result.`, 'success');
                }
            }
        };
        img.src = URL.createObjectURL(res.data);
    } catch (e) {
        console.error("Failed to load AI result:", e);
    }
}

function saveProject() {
    const projectData = {
        meta: { 
            prompt: prompt.value, 
            width: imageCanvasRef.value.width, 
            height: imageCanvasRef.value.height,
            version: '2.5'
        },
        layers: layers.value.map(l => ({ 
            id: l.id, 
            name: l.name, 
            opacity: l.opacity, 
            blendMode: l.blendMode || 'normal',
            visible: l.visible, 
            data: l.el ? l.el.toDataURL('image/png') : null 
        }))
    };
    const blob = new Blob([JSON.stringify(projectData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); 
    a.href = url; 
    a.download = `canvas_project_${Date.now()}.json`; 
    document.body.appendChild(a); 
    a.click(); 
    document.body.removeChild(a);
    const doc = docs.value[activeDocIndex.value];
    if (doc) doc.dirty = false;
    uiStore.addNotification('Multi-layer Project Saved.', 'success');
}

function saveCanvas() {
    const comp = document.createElement('canvas'); 
    comp.width = imageCanvasRef.value.width; 
    comp.height = imageCanvasRef.value.height;
    const cc = comp.getContext('2d');
    
    layers.value.filter(l => l.visible).forEach(l => { 
        if (l.ctx) {
            cc.globalAlpha = l.opacity; 
            cc.globalCompositeOperation = l.blendMode || 'source-over';
            cc.drawImage(l.ctx.canvas, 0, 0); 
        }
    });
    
    imageStore.saveCanvasAsNewImage({ 
        base_image_b64: comp.toDataURL('image/png').split(',')[1], 
        prompt: prompt.value || "Composition", 
        width: comp.width, 
        height: comp.height, 
        model: selectedModel.value 
    });
    const doc = docs.value[activeDocIndex.value];
    if (doc) doc.dirty = false;
}

// Throttled entry point — coalesces rapid bursts (adjustment sliders,
// successive AI task completions) into one undo snapshot at most once per
// 120 ms. Callers needing an immediate snapshot should call flushSaveState().
let saveStateTimer = null;

function saveState() {
    if (!imageCanvasRef.value) return;
    if (saveStateTimer) clearTimeout(saveStateTimer);
    saveStateTimer = setTimeout(_doSaveState, 120);
}

function flushSaveState() {
    if (saveStateTimer) { clearTimeout(saveStateTimer); saveStateTimer = null; }
    _doSaveState();
}

// Cheap per-layer thumbnail (48×48) used by the upgraded layer panel.
function refreshLayerThumbnail(layer) {
    if (!layer?.el) return;
    try {
        const t = document.createElement('canvas');
        t.width = 48; t.height = 48;
        const tc = t.getContext('2d');
        const w = layer.el.width || 48, h = layer.el.height || 48;
        const scale = Math.min(48 / w, 48 / h);
        const dw = w * scale, dh = h * scale;
        tc.drawImage(layer.el, (48 - dw) / 2, (48 - dh) / 2, dw, dh);
        layer.thumbnail = t.toDataURL('image/png');
    } catch { /* canvas may be zero-sized during init — ignore */ }
}

function refreshAllLayerThumbnails() {
    layers.value.forEach(refreshLayerThumbnail);
}

// Composite mini-thumbnail (96×96) stored on each history snapshot so the
// visual timeline can render without re-encoding every layer image later.
function generateCompositeThumbnail() {
    if (!imageCanvasRef.value) return null;
    try {
        const t = document.createElement('canvas');
        t.width = 96; t.height = 96;
        const tc = t.getContext('2d');
        const w = canvasWidth.value, h = canvasHeight.value;
        const scale = Math.min(96 / w, 96 / h);
        const dw = w * scale, dh = h * scale;
        const ox = (96 - dw) / 2, oy = (96 - dh) / 2;
        layers.value.filter(l => l.visible && l.el).forEach(l => {
            tc.globalAlpha = l.opacity;
            tc.globalCompositeOperation = l.blendMode || 'source-over';
            tc.drawImage(l.el, ox, oy, dw, dh);
        });
        return t.toDataURL('image/jpeg', 0.75);
    } catch { return null; }
}

function _doSaveState() {
    if (!imageCanvasRef.value) return;

    const layerSnapshots = layers.value.map(l => ({ 
        id: l.id, 
        name: l.name,
        order: l.order,
        v: l.visible, 
        o: l.opacity,
        b: l.blendMode || 'normal',
        lk: l.locked || false,
        adj: l.adjustments ? { ...l.adjustments } : defaultAdjustments(),
        data: l.el ? l.el.toDataURL('image/png') : null
    }));

    const maskData = maskCanvasRef.value ? maskCanvasRef.value.toDataURL('image/png') : null;

    const snapshot = {
        width: imageCanvasRef.value.width,
        height: imageCanvasRef.value.height,
        activeLayerId: activeLayerId.value,
        layers: layerSnapshots,
        maskData: maskData,
        thumb: generateCompositeThumbnail(),
        name: null,
        pinned: false
    };

    if (historyIndex.value < history.value.length - 1) {
        history.value = history.value.slice(0, historyIndex.value + 1);
    }
    history.value.push(snapshot);
    if (history.value.length > 30) {
        history.value.shift();
    }
    historyIndex.value = history.value.length - 1;

    refreshAllLayerThumbnails();

    // Mark the active tab dirty
    const doc = docs.value[activeDocIndex.value];
    if (doc) doc.dirty = true;
}

function undo() { 
    if (historyIndex.value > 0) { 
        historyIndex.value--; 
        applyHistory(history.value[historyIndex.value]); 
    } 
}

function redo() { 
    if (historyIndex.value < history.value.length - 1) { 
        historyIndex.value++; 
        applyHistory(history.value[historyIndex.value]); 
    } 
}

async function applyHistory(snapshot) {
    if (!snapshot) return;

    const w = snapshot.width || canvasWidth.value;
    const h = snapshot.height || canvasHeight.value;

    canvasWidth.value = w;
    canvasHeight.value = h;

    const restoredLayers = snapshot.layers.map(s => {
        const existing = layers.value.find(l => l.id === s.id);
        return {
            id: s.id,
            name: s.name,
            order: s.order,
            visible: s.v,
            opacity: s.o,
            blendMode: s.b || 'normal',
            locked: s.lk || false,
            thumbnail: existing?.thumbnail || null,
            adjustments: s.adj ? { ...s.adj } : defaultAdjustments(),
            el: existing?.el || null,
            ctx: existing?.ctx || null
        };
    });

    layers.value = restoredLayers;
    activeLayerId.value = snapshot.activeLayerId || 'base';

    await nextTick();

    snapshot.layers.forEach(s => {
        const l = layers.value.find(x => x.id === s.id);
        if (l?.ctx && s.data) {
            const img = new Image();
            img.onload = () => {
                l.ctx.clearRect(0, 0, w, h);
                l.ctx.drawImage(img, 0, 0);
            };
            img.src = s.data;
        }
    });

    if (maskCanvasRef.value && ctxMask.value) {
        ctxMask.value.clearRect(0, 0, w, h);
        if (snapshot.maskData) {
            const mImg = new Image();
            mImg.onload = () => {
                ctxMask.value.drawImage(mImg, 0, 0);
            };
            mImg.src = snapshot.maskData;
        }
    }
}

// ── LAYER PANEL HELPERS ──
function toggleLayerLock(layer) {
    if (!layer || layer.id === 'base') return;
    layer.locked = !layer.locked;
    saveState();
}

function startLayerRename(layer) {
    if (!layer || layer.id === 'base') return;
    editingLayerId.value = layer.id;
    editingLayerName.value = layer.name;
}

function commitLayerRename(layer) {
    if (editingLayerId.value !== layer.id) return;
    const name = (editingLayerName.value || '').trim();
    if (name) { layer.name = name; saveState(); }
    editingLayerId.value = null;
    editingLayerName.value = '';
}

function onLayerDragStart(layer, ev) {
    if (layer.id === 'base') { ev.preventDefault(); return; }
    draggingLayerId.value = layer.id;
    ev.dataTransfer.effectAllowed = 'move';
    try { ev.dataTransfer.setData('text/plain', layer.id); } catch {}
}
function onLayerDragOver(ev) {
    ev.preventDefault();
    ev.dataTransfer.dropEffect = 'move';
}
function onLayerDrop(targetLayer, ev) {
    ev.preventDefault();
    const srcId = draggingLayerId.value;
    if (!srcId || srcId === targetLayer.id || targetLayer.id === 'base') {
        draggingLayerId.value = null; dragOverLayerId.value = null; return;
    }
    const arr = layers.value;
    const srcIdx = arr.findIndex(l => l.id === srcId);
    const tgtIdx = arr.findIndex(l => l.id === targetLayer.id);
    if (srcIdx < 0 || tgtIdx < 0) { draggingLayerId.value = null; dragOverLayerId.value = null; return; }
    const [moved] = arr.splice(srcIdx, 1);
    arr.splice(tgtIdx, 0, moved);
    // Reassign order values to match the new array order
    arr.forEach((l, i) => { l.order = i; });
    draggingLayerId.value = null;
    dragOverLayerId.value = null;
    saveState();
}
function onLayerDragEnd() {
    draggingLayerId.value = null;
    dragOverLayerId.value = null;
}

// Compact blend-mode preset row for the layer panel
const blendQuickRow = [
    { value: 'normal', short: 'Nrm', label: 'Normal' },
    { value: 'multiply', short: 'Mul', label: 'Multiply' },
    { value: 'screen', short: 'Scr', label: 'Screen' },
    { value: 'overlay', short: 'Ovl', label: 'Overlay' },
    { value: 'soft-light', short: 'Sft', label: 'Soft Light' },
    { value: 'difference', short: 'Dif', label: 'Difference' }
];

// ── HISTORY TIMELINE HELPERS ──
function jumpToHistory(idx) {
    if (idx < 0 || idx >= history.value.length) return;
    historyIndex.value = idx;
    applyHistory(history.value[idx]);
}
function nameCurrentSnapshot() {
    if (historyIndex.value < 0 || !history.value[historyIndex.value]) return;
    const current = history.value[historyIndex.value];
    const name = window.prompt('Name this snapshot:', current.name || `Step ${historyIndex.value + 1}`);
    if (name !== null && name.trim()) {
        current.name = name.trim();
        current.pinned = true;
        history.value = [...history.value];
    }
}

// ── DOCUMENT TABS ──
async function serializeDoc() {
    if (!imageCanvasRef.value) return null;
    return {
        width: canvasWidth.value,
        height: canvasHeight.value,
        activeLayerId: activeLayerId.value,
        layers: layers.value.map(l => ({
            id: l.id,
            name: l.name,
            visible: l.visible,
            order: l.order,
            opacity: l.opacity,
            blendMode: l.blendMode || 'normal',
            locked: l.locked || false,
            adjustments: l.adjustments ? { ...l.adjustments } : defaultAdjustments(),
            data: l.el ? l.el.toDataURL('image/png') : null
        })),
        maskData: maskCanvasRef.value ? maskCanvasRef.value.toDataURL('image/png') : null,
        history: [...history.value],
        historyIndex: historyIndex.value,
        prompt: prompt.value,
        negativePrompt: negativePrompt.value,
        zoom: zoom.value,
        panX: panX.value,
        panY: panY.value
    };
}

async function restoreFromDocState(doc) {
    const s = doc.state;
    if (!s) return;
    canvasWidth.value = s.width;
    canvasHeight.value = s.height;
    layers.value = s.layers.map(l => ({
        id: l.id,
        name: l.name,
        visible: l.visible,
        order: l.order,
        opacity: l.opacity,
        blendMode: l.blendMode,
        locked: l.locked || false,
        thumbnail: null,
        adjustments: l.adjustments ? { ...l.adjustments } : defaultAdjustments(),
        el: null,
        ctx: null
    }));
    activeLayerId.value = s.activeLayerId || 'base';
    await nextTick();

    s.layers.forEach(slayer => {
        const l = layers.value.find(x => x.id === slayer.id);
        if (l?.ctx && slayer.data) {
            const img = new Image();
            img.onload = () => { l.ctx.clearRect(0, 0, s.width, s.height); l.ctx.drawImage(img, 0, 0); };
            img.src = slayer.data;
        }
    });

    if (maskCanvasRef.value && ctxMask.value) {
        ctxMask.value.clearRect(0, 0, s.width, s.height);
        if (s.maskData) {
            const mi = new Image();
            mi.onload = () => ctxMask.value.drawImage(mi, 0, 0);
            mi.src = s.maskData;
        }
    }

    history.value = [...(s.history || [])];
    historyIndex.value = s.historyIndex ?? 0;
    prompt.value = s.prompt || '';
    negativePrompt.value = s.negativePrompt || '';
    zoom.value = s.zoom || 1;
    panX.value = s.panX || 0;
    panY.value = s.panY || 0;

    await nextTick();
    refreshAllLayerThumbnails();
}

async function switchToDoc(index) {
    if (index === activeDocIndex.value) return;
    if (index < 0 || index >= docs.value.length) return;
    flushSaveState();
    const current = docs.value[activeDocIndex.value];
    current.state = await serializeDoc();
    activeDocIndex.value = index;
    const target = docs.value[index];
    if (target.state) {
        await restoreFromDocState(target);
    } else if (target.docId && target.docId !== 'new') {
        await loadImage(target.docId);
        await nextTick();
        target.state = await serializeDoc();
    } else {
        await initNewBlankCanvas();
        target.state = await serializeDoc();
    }
}

async function openNewDocTab() {
    const id = `doc_${Date.now()}`;
    docs.value.push({
        id,
        name: `Untitled ${docs.value.length + 1}`,
        docId: 'new',
        state: null,
        dirty: false
    });
    await switchToDoc(docs.value.length - 1);
}

async function closeDocTab(index) {
    if (docs.value.length <= 1) return;
    const doc = docs.value[index];
    if (doc.dirty) {
        const { confirmed } = await uiStore.showConfirmation({
            title: 'Close tab?',
            message: `"${doc.name}" has unsaved edits. Discard?`,
            confirmText: 'Discard',
            danger: true
        });
        if (!confirmed) return;
    }
    docs.value.splice(index, 1);
    let newIdx = activeDocIndex.value;
    if (index < newIdx) newIdx -= 1;
    if (newIdx >= docs.value.length) newIdx = docs.value.length - 1;
    if (newIdx < 0) newIdx = 0;
    if (newIdx === activeDocIndex.value && index !== activeDocIndex.value) {
        activeDocIndex.value = -1; // force switch
    }
    const wasActive = index === activeDocIndex.value;
    activeDocIndex.value = newIdx;
    const target = docs.value[newIdx];
    if (wasActive || target) {
        if (target?.state) await restoreFromDocState(target);
    }
}

function renameActiveDoc() {
    const doc = docs.value[activeDocIndex.value];
    if (!doc) return;
    const name = window.prompt('Tab name:', doc.name);
    if (name !== null && name.trim()) doc.name = name.trim();
}

// ── VIEWPORT ──
function fitToScreen() {
    if (!containerRef.value || !imageCanvasRef.value) return;
    const cw = containerRef.value.clientWidth, ch = containerRef.value.clientHeight;
    const iw = imageCanvasRef.value.width, ih = imageCanvasRef.value.height;
    zoom.value = Math.min((cw - 80) / iw, (ch - 80) / ih, 1);
    panX.value = 0;
    panY.value = 0;
}

function resetZoom() {
    zoom.value = 1;
    panX.value = 0;
    panY.value = 0;
}

function zoomIn() { zoom.value = Math.min(8, zoom.value + 0.25); }
function zoomOut() { zoom.value = Math.max(0.1, zoom.value - 0.25); }

// Normalises wheel deltas across browsers — Firefox reports `lines`
// (deltaMode=1) and some systems report `pages` (deltaMode=2), while
// Chrome/Safari usually report pixel values. Converting everything to
// pixel-equivalents keeps the zoom step consistent.
function normalizeWheelDelta(delta, mode) {
    if (mode === 1) return delta * 16;
    if (mode === 2) return delta * 100;
    return delta;
}

// Wheel is now a first-class zoom control across three input sources:
//   • Mouse roller (deltaY ≈ ±100 per tick, PWM pixels)
//   • Trackpad two-finger scroll (smooth sub-pixel deltaY)
//   • Trackpad pinch gesture (browser sets `ctrlKey: true`, small deltaY)
// Shift / Alt turn the wheel into a pan instead — matching Photoshop /
// Figma conventions and giving users a way to keep the canvas on-screen
// once they've zoomed past 100%.
function handleWheel(e) {
    const normalized = normalizeWheelDelta(e.deltaY, e.deltaMode);

    // Shift+Wheel → horizontal pan
    if (e.shiftKey && !e.ctrlKey) {
        panX.value -= normalized;
        return;
    }
    // Alt+Wheel → vertical pan
    if (e.altKey && !e.ctrlKey && !e.shiftKey) {
        panY.value -= normalized;
        return;
    }

    // Ctrl+Wheel = pinch gesture on trackpad → much finer step so a single
    // pinch feels like a smooth glide instead of a jump.
    const step = e.ctrlKey ? 0.005 : 0.0015;
    const ratio = Math.exp(-normalized * step);
    const newZoom = Math.min(8, Math.max(0.1, zoom.value * ratio));
    if (Math.abs(newZoom - zoom.value) < 1e-4) return;

    // Anchor the zoom to the cursor so the pixel under it stays put. The
    // canvas-stack is flex-centered inside the viewport with `transform:
    // translate(pan) scale(zoom)` and `transform-origin: center`, so we
    // solve the pan adjustment that keeps the cursor's local point fixed:
    //   cursor_screen = pan + zoom * local
    //   → new_pan = cursor_screen - zoomRatio * (cursor_screen - pan)
    if (containerRef.value) {
        const rect = containerRef.value.getBoundingClientRect();
        const mx = e.clientX - rect.left - rect.width / 2;
        const my = e.clientY - rect.top - rect.height / 2;
        const zoomRatio = newZoom / zoom.value;
        panX.value = mx - zoomRatio * (mx - panX.value);
        panY.value = my - zoomRatio * (my - panY.value);
    }
    zoom.value = newZoom;
}

function handleKeydown(e) {
    if (e.key === 'Escape' && isSaveModalOpen.value) {
        e.preventDefault();
        closeSaveModal();
        return;
    }
    if (e.key === 'Escape' && showShortcutsHelp.value) {
        e.preventDefault();
        showShortcutsHelp.value = false;
        return;
    }
    if (e.key === 'Escape' && !isSaveModalOpen.value && !showShortcutsHelp.value) {
        if (textEditor.value.visible) { e.preventDefault(); cancelText(); return; }
        if (cropRect.value) { e.preventDefault(); cancelCrop(); return; }
        if (selection.value.active) { e.preventDefault(); deselectAll(); return; }
    }
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (e.key === '?' || (e.shiftKey && e.key === '/')) {
        e.preventDefault();
        showShortcutsHelp.value = !showShortcutsHelp.value;
        return;
    }

    // Block all other editor shortcuts while a modal/overlay is open
    if (isSaveModalOpen.value || showShortcutsHelp.value) return;

    // ── Tool shortcuts (Photoshop-familiar) ──
    if (!e.ctrlKey && !e.metaKey && !e.altKey) {
        // Phase 2 shift-combos intercepted before plain-letter handlers
        if (e.shiftKey && e.key === 'C') { e.preventDefault(); setTool('crop'); return; }
        if (e.shiftKey && e.key === 'V') { e.preventDefault(); setTool('move'); return; }
        if (e.shiftKey && e.key === 'G') { e.preventDefault(); setTool('fill'); return; }
        if (e.shiftKey && e.key === 'D') { e.preventDefault(); setTool('dodge'); return; }
        if (e.shiftKey && e.key === 'B') { e.preventDefault(); setTool('burn'); return; }
        if (e.key === 'm' || e.key === 'M') { setTool(tool.value === 'marquee' ? 'ellipse-select' : 'marquee'); return; }
        if (e.key === 'l' || e.key === 'L') { setTool('lasso'); return; }
        if (e.key === 'j' || e.key === 'J') { setTool('heal'); return; }
        if (e.key === 's' || e.key === 'S') { setTool('smudge'); return; }
        if (e.key === 'b' || e.key === 'B') setTool('brush');
        if (e.key === 'e' || e.key === 'E') setTool('eraser');
        if (e.key === 'i' || e.key === 'I') setTool('eyedropper');
        if (e.key === 'k' || e.key === 'K') setTool('colorkey');
        if (e.key === 'w' || e.key === 'W') setTool('wand');
        if (e.key === 'c' || e.key === 'C') setTool('clone');
        if (e.key === 'g' || e.key === 'G') setTool('gradient');
        if (e.key === 't' || e.key === 'T') setTool('text');
        if (e.key === 'v' || e.key === 'V') setTool('pan');
        if (e.key === 'h' || e.key === 'H') setTool('pan');
        if (e.key === 'u' || e.key === 'U') setTool('line');
        if (e.key === 'r' || e.key === 'R') setTool('rect');
        if (e.key === 'o' || e.key === 'O') setTool('circle');
        // Foreground / Background swatch shortcuts
        if (e.key === 'x' || e.key === 'X') swapColors();
        if (e.key === 'd' || e.key === 'D') resetColors();
    }

    // ── Temporary Space = Move/Pan (hold to pan, release to restore prior tool) ──
    if (e.code === 'Space') {
        e.preventDefault();
        if (!toolBeforeSpace) {
            toolBeforeSpace = tool.value;
            setTool('pan');
        }
        return;
    }

    if (e.key === '[') brushSize.value = Math.max(1, brushSize.value - 5);
    if (e.key === ']') brushSize.value = Math.min(300, brushSize.value + 5);

    // ── File & Edit shortcuts (Photoshop-familiar) ──
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { 
        e.preventDefault(); 
        if (e.shiftKey) redo(); 
        else undo(); 
        return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') { 
        e.preventDefault(); 
        redo(); 
        return;
    }
    // Ctrl+Shift+S → Export / Save As… (format picker)
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 's') {
        e.preventDefault();
        openSaveModal();
        return;
    }
    // Ctrl+Shift+N → New Layer
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        addNewLayer();
        return;
    }
    // Ctrl+J → Duplicate Layer
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'j') {
        e.preventDefault();
        duplicateActiveLayer();
        return;
    }
    // Ctrl+S → Quick Save to Gallery
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 's') {
        e.preventDefault();
        saveCanvas();
        return;
    }
}

// Restore the tool that was temporarily replaced by Space-hold pan.
function handleKeyup(e) {
    if (e.code === 'Space' && toolBeforeSpace) {
        setTool(toolBeforeSpace);
        toolBeforeSpace = null;
        e.preventDefault();
    }
}
</script>

<style scoped>
@reference "tailwindcss";

.pattern-grid { 
    background-image: linear-gradient(45deg, #e5e7eb 25%, transparent 25%), linear-gradient(-45deg, #e5e7eb 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #e5e7eb 75%), linear-gradient(-45deg, transparent 75%, #e5e7eb 75%); 
    background-size: 20px 20px; 
    background-position: 0 0, 0 10px, 10px -10px, -10px 0px; 
}
.dark .pattern-grid { 
    background-image: linear-gradient(45deg, #1f2937 25%, transparent 25%), linear-gradient(-45deg, #1f2937 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #1f2937 75%), linear-gradient(-45deg, transparent 75%, #1f2937 75%); 
}
.layer-canvas { image-rendering: pixelated; }
.layer-item { 
    @apply flex items-center gap-2.5 p-2 rounded-xl cursor-pointer border-2 border-transparent transition-all hover:bg-gray-100 dark:hover:bg-gray-800 select-none; 
}
.layer-item.active { 
    @apply border-blue-500 bg-blue-50/80 dark:bg-blue-900/30 shadow-sm; 
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>