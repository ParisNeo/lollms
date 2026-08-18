<template>
    <!-- TELEPORT EDITOR TOOLBAR TO GLOBAL HEADER -->
    <Teleport to="#global-header-title-target" v-if="isComponentMounted && hasHeaderTarget">
        <div class="flex items-center bg-gray-100/90 dark:bg-gray-800/90 rounded-2xl p-1 gap-1 pointer-events-auto shadow-inner border border-gray-200 dark:border-gray-700/70 backdrop-blur-md relative z-[100] max-w-full overflow-x-auto no-scrollbar">
            <button 
                v-for="t in tools" 
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
    </Teleport>

    <Teleport to="#global-header-actions-target" v-if="isComponentMounted && hasHeaderTarget">
        <div class="flex items-center gap-1.5 pointer-events-auto relative z-[100]">
            <!-- Undo/Redo -->
            <button @click="undo" :disabled="historyIndex <= 0" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl disabled:opacity-30 transition-all text-gray-600 dark:text-gray-300" title="Undo (Ctrl+Z)"><IconUndo class="w-4 h-4" /></button>
            <button @click="redo" :disabled="historyIndex >= history.length - 1" class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl disabled:opacity-30 transition-all text-gray-600 dark:text-gray-300" title="Redo (Ctrl+Y)"><IconRedo class="w-4 h-4" /></button>
            
            <div class="h-5 w-px bg-gray-200 dark:bg-gray-700 mx-1"></div>

            <button @click="saveProject" class="btn btn-secondary btn-sm h-8 px-3 rounded-xl flex items-center gap-1.5" title="Save Multi-Layer Project File (.json)">
                <IconFolder class="w-3.5 h-3.5 text-amber-500"/> <span class="hidden sm:inline text-xs font-bold">Project</span>
            </button>
            <button @click="saveCanvas" class="btn btn-primary btn-sm h-8 px-3 rounded-xl flex items-center gap-1.5 shadow-lg shadow-blue-500/20" title="Flatten and Save PNG to Gallery">
                <IconSave class="w-3.5 h-3.5" /> <span class="hidden sm:inline text-xs font-bold">Save PNG</span>
            </button>
            
            <button @click="showMobileSidebar = !showMobileSidebar" class="lg:hidden btn btn-secondary p-1.5 ml-1 h-8 w-8 flex items-center justify-center rounded-xl"><IconAdjustmentsHorizontal class="w-4 h-4" /></button>
        </div>
    </Teleport>

    <div class="h-full flex flex-col bg-gray-100 dark:bg-gray-950 overflow-hidden relative select-none font-sans">
        
        <!-- Top Tool Options HUD (Floating Pill) -->
        <div class="absolute top-3 left-1/2 -translate-x-1/2 z-30 flex items-center gap-3 bg-white/95 dark:bg-gray-900/95 backdrop-blur-xl px-4 py-2 rounded-2xl shadow-2xl border border-gray-200/80 dark:border-gray-800 animate-in fade-in slide-from-top-3 max-w-[95vw] overflow-x-auto no-scrollbar">
            <!-- Active Tool Indicator -->
            <div class="flex items-center gap-1.5 pr-2 border-r dark:border-gray-800 shrink-0">
                <span class="text-[9px] font-black uppercase tracking-widest text-primary">{{ currentToolName }}</span>
            </div>

            <!-- Primary Color & Swatches -->
            <div class="flex items-center gap-1.5 shrink-0" v-if="['brush', 'line', 'rect', 'circle', 'text', 'gradient'].includes(tool)">
                <div class="relative w-6 h-6 rounded-lg overflow-hidden border dark:border-gray-700 shadow-sm cursor-pointer" :style="{ backgroundColor: color }">
                    <input type="color" v-model="color" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full">
                </div>
                <!-- Recent Swatches -->
                <div class="hidden sm:flex items-center gap-1">
                    <button 
                        v-for="swatch in recentColors" 
                        :key="swatch" 
                        @click="color = swatch" 
                        class="w-4 h-4 rounded-md border border-black/10 dark:border-white/10 hover:scale-110 transition-transform" 
                        :style="{ backgroundColor: swatch }"
                    ></button>
                </div>
            </div>
            
            <!-- Secondary Color (for Gradients) -->
            <div class="flex items-center gap-1.5 shrink-0" v-if="tool === 'gradient'">
                <span class="text-[9px] font-bold text-gray-400 uppercase">To</span>
                <div class="relative w-6 h-6 rounded-lg overflow-hidden border dark:border-gray-700 shadow-sm cursor-pointer" :style="{ backgroundColor: secondaryColor }">
                    <input type="color" v-model="secondaryColor" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full">
                </div>
            </div>

            <!-- Size / Thickness Slider -->
            <div class="flex items-center gap-2 shrink-0" v-if="['brush', 'eraser', 'line', 'rect', 'circle', 'text', 'clone', 'wand'].includes(tool)">
                <span class="text-[9px] font-black text-gray-400 uppercase tracking-widest">
                    {{ tool === 'text' ? 'Font' : (tool === 'wand' ? 'Tolerance' : 'Size') }}
                </span>
                <input 
                    type="range" 
                    v-model.number="brushSize" 
                    :min="tool === 'wand' ? 0 : 1" 
                    :max="tool === 'wand' ? 100 : 300" 
                    class="w-20 sm:w-28 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                >
                <span class="text-[9px] font-mono font-bold w-7 text-center bg-gray-100 dark:bg-gray-800 py-0.5 rounded">{{ brushSize }}</span>
            </div>

            <!-- Clone Tool Anchor State -->
            <div v-if="tool === 'clone'" class="flex items-center gap-2 border-l dark:border-gray-800 pl-3 shrink-0">
                <button @click="settingCloneAnchor = true" class="btn btn-xs h-6 px-2 text-[10px]" :class="settingCloneAnchor ? 'btn-primary' : 'btn-secondary'">
                    {{ settingCloneAnchor ? 'Click to Set Source...' : 'Set Anchor' }}
                </button>
            </div>

            <!-- Mask Clear Quick Button -->
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
            <!-- Central Viewport & Canvas Area -->
            <main 
                ref="containerRef" 
                class="grow bg-gray-200 dark:bg-black relative overflow-hidden flex items-center justify-center cursor-crosshair pattern-grid" 
                @wheel.prevent="handleWheel" 
                @mousedown="startAction" 
                @mousemove="handleMove" 
                @mouseup="endAction" 
                @mouseleave="endAction"
            >
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

                <!-- Layer Composition Container -->
                <div :style="combinedCanvasStyle" class="relative shadow-2xl origin-center canvas-stack">
                    <!-- Base Sizing Anchor Canvas -->
                    <canvas ref="imageCanvasRef" class="block bg-transparent layer-canvas"></canvas>

                    <!-- Render All Stacked Layers -->
                    <template v-for="layer in layers" :key="layer.id">
                        <canvas 
                            :ref="el => setLayerCanvasRef(layer, el)" 
                            v-show="layer.visible"
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
                        v-show="activeLayerId === 'mask' || showMaskOverlay"
                        class="absolute inset-0 opacity-50 layer-canvas pointer-events-none" 
                        style="z-index: 998"
                    ></canvas>

                    <!-- Shape & Interactive Drawing Preview Layer -->
                    <canvas 
                        ref="previewCanvasRef" 
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

                <!-- Viewport Navigation HUD (Bottom Left) -->
                <div class="absolute bottom-4 left-4 bg-white/90 dark:bg-gray-900/90 backdrop-blur-md rounded-2xl shadow-xl p-1.5 flex items-center gap-1.5 z-10 border dark:border-gray-800">
                    <button @click="zoomOut" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg" title="Zoom Out (-)"><IconMinus class="w-4 h-4" /></button>
                    <span class="text-[10px] font-black font-mono w-12 text-center select-none">{{ Math.round(zoom * 100) }}%</span>
                    <button @click="zoomIn" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg" title="Zoom In (+)"><IconPlus class="w-4 h-4" /></button>
                    <button @click="fitToScreen" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg text-blue-500 font-bold text-xs" title="Fit Canvas to View">Fit</button>
                    <button @click="resetZoom" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg text-gray-500 font-bold text-xs" title="100% 1:1">1:1</button>
                </div>
            </main>

            <!-- Right Inspector Sidebar (Layers & AI Controls) -->
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

                            <!-- User Graphic Layers -->
                            <div 
                                v-for="layer in sortedLayers" 
                                :key="layer.id" 
                                @click="activeLayerId = layer.id" 
                                class="layer-item group" 
                                :class="{'active': activeLayerId === layer.id}"
                            >
                                <button @click.stop="toggleLayerVisibility(layer)" class="p-1 text-gray-400 hover:text-blue-500">
                                    <IconEye v-if="layer.visible" class="w-3.5 h-3.5 text-blue-500"/>
                                    <IconEyeOff v-else class="w-3.5 h-3.5 text-gray-400"/>
                                </button>
                                
                                <span class="text-xs font-bold truncate grow" :class="layer.id === 'base' ? 'font-black' : ''">{{ layer.name }}</span>
                                
                                <button v-if="layer.id !== 'base'" @click.stop="deleteLayer(layer.id)" class="opacity-0 group-hover:opacity-100 p-1 text-red-400 hover:text-red-500 transition-opacity"><IconTrash class="w-3.5 h-3.5"/></button>
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
                            </div>
                        </div>
                    </div>

                    <!-- ── TAB 2: NON-DESTRUCTIVE ADJUSTMENTS ── -->
                    <div v-show="activeInspectorTab === 'adjust'" class="space-y-4">
                        <div class="flex justify-between items-center">
                            <span class="text-[9px] font-black text-gray-400 uppercase tracking-widest">Color & Filters</span>
                            <button @click="resetAdjustments" class="text-[9px] font-bold text-blue-500 uppercase hover:underline">Reset</button>
                        </div>

                        <div class="space-y-3 p-3 bg-gray-50 dark:bg-gray-800/60 rounded-2xl border dark:border-gray-700/60">
                            <!-- Brightness -->
                            <div class="space-y-1">
                                <div class="flex justify-between text-xs">
                                    <span class="text-[10px] font-bold text-gray-500">Brightness</span>
                                    <span class="font-mono text-[10px]">{{ Math.round(adjustments.brightness * 100) }}%</span>
                                </div>
                                <input type="range" v-model.number="adjustments.brightness" min="0" max="2" step="0.05" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                            </div>

                            <!-- Contrast -->
                            <div class="space-y-1">
                                <div class="flex justify-between text-xs">
                                    <span class="text-[10px] font-bold text-gray-500">Contrast</span>
                                    <span class="font-mono text-[10px]">{{ Math.round(adjustments.contrast * 100) }}%</span>
                                </div>
                                <input type="range" v-model.number="adjustments.contrast" min="0" max="2" step="0.05" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                            </div>

                            <!-- Saturation -->
                            <div class="space-y-1">
                                <div class="flex justify-between text-xs">
                                    <span class="text-[10px] font-bold text-gray-500">Saturation</span>
                                    <span class="font-mono text-[10px]">{{ Math.round(adjustments.saturate * 100) }}%</span>
                                </div>
                                <input type="range" v-model.number="adjustments.saturate" min="0" max="2" step="0.05" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                            </div>

                            <!-- Hue Rotation -->
                            <div class="space-y-1">
                                <div class="flex justify-between text-xs">
                                    <span class="text-[10px] font-bold text-gray-500">Hue Shift</span>
                                    <span class="font-mono text-[10px]">{{ adjustments.hueRotate }}°</span>
                                </div>
                                <input type="range" v-model.number="adjustments.hueRotate" min="0" max="360" step="5" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                            </div>

                            <!-- Blur -->
                            <div class="space-y-1">
                                <div class="flex justify-between text-xs">
                                    <span class="text-[10px] font-bold text-gray-500">Blur Filter</span>
                                    <span class="font-mono text-[10px]">{{ adjustments.blur }}px</span>
                                </div>
                                <input type="range" v-model.number="adjustments.blur" min="0" max="20" step="1" class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500">
                            </div>

                            <button @click="bakeAdjustmentsToActiveLayer" class="btn btn-secondary btn-xs w-full py-1.5 font-bold uppercase tracking-wider text-[9px] mt-2">
                                Bake Filter into Active Layer
                            </button>
                        </div>
                    </div>

                    <!-- ── TAB 3: TARGETED AI LAYER EDITING & INPAINTING ── -->
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

                        <!-- 2. Prompts -->
                        <div class="space-y-1.5">
                            <label class="text-[10px] font-bold text-gray-500">Edit / Inpaint Prompt</label>
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
import useEventBus from '../services/eventBus';

// Icons
import IconPencil from '../assets/icons/IconPencil.vue';
import IconEraser from '../assets/icons/IconEraser.vue';
import IconUndo from '../assets/icons/IconUndo.vue';
import IconRedo from '../assets/icons/IconRedo.vue';
import IconSave from '../assets/icons/IconSave.vue';
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

// Dynamic Vector Icons
const IconHand = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M18 11V6a2 2 0 00-4 0v2a2 2 0 00-4 0v1a2 2 0 00-4 0v8a5 5 0 0010 0v-4a2 2 0 00-2-2z' })]) };
const IconLine = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M5 19L19 5' })]) };
const IconRect = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('rect', { x: '3', y: '3', width: '18', height: '18', rx: '2' })]) };
const IconWand = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M15 4V2M15 16V14M8 9h2M20 9h2M17.8 11.8L19 13M10.6 5.2L12 6.6M11.6 12.2l-8.4 8.6' })]) };
const IconEyedropper = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M19 11l-8-8-8.6 8.6a2 2 0 000 2.8l2.2 2.2a2 2 0 002.8 0L19 11zM14 6l4 4M2 22l3-3' })]) };
const IconGradient = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('rect', { x: '3', y: '3', width: '18', height: '18', rx: '2' }), h('path', { d: 'M3 3l18 18' })]) };

const props = defineProps({ id: { type: String, default: null } });
const router = useRouter();
const imageStore = useImageStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const tasksStore = useTasksStore();
const { on, off } = useEventBus();

const isComponentMounted = ref(false);
const hasHeaderTarget = ref(false);
const showMobileSidebar = ref(false);
const activeInspectorTab = ref('layers'); // 'layers' | 'adjust' | 'ai'

const containerRef = ref(null);
const imageCanvasRef = ref(null);
const maskCanvasRef = ref(null);
const previewCanvasRef = ref(null);
const ctxMask = ref(null);
const ctxPreview = ref(null);

const activeLayerId = ref('base');
const tool = ref('brush');
const color = ref('#3B82F6');
const secondaryColor = ref('#EC4899');
const brushSize = ref(35);
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

const layers = ref([
    { id: 'base', name: 'Base Image Plate', visible: true, order: 0, el: null, ctx: null, opacity: 1.0, blendMode: 'normal' }
]);

const sortedLayers = computed(() => [...layers.value].sort((a, b) => b.order - a.order));
const activeLayer = computed(() => layers.value.find(l => l.id === activeLayerId.value) || layers.value[0]);

const cloneAnchor = ref(null);
const settingCloneAnchor = ref(false);
let isDragging = false, lastX = 0, lastY = 0, startX = 0, startY = 0;
const cursorX = ref(0), cursorY = ref(0);
const history = ref([]);
const historyIndex = ref(-1);

const tools = [ 
    { id: 'pan', name: 'Pan / Move Canvas', icon: IconHand, shortcut: 'Space' }, 
    { id: 'eyedropper', name: 'Eyedropper Sample', icon: IconEyedropper, shortcut: 'I' },
    { id: 'brush', name: 'Drawing Brush', icon: IconPencil, shortcut: 'B' }, 
    { id: 'eraser', name: 'Eraser', icon: IconEraser, shortcut: 'E' }, 
    { id: 'wand', name: 'Magic Wand Transparency', icon: IconWand, shortcut: 'W' },
    { id: 'gradient', name: 'Color Gradient', icon: IconGradient, shortcut: 'G' },
    { id: 'clone', name: 'Clone Stamp', icon: IconArrowPath, shortcut: 'C' },
    { id: 'text', name: 'Text Layer', icon: IconType, shortcut: 'T' }, 
    { id: 'line', name: 'Line', icon: IconLine, shortcut: 'U' }, 
    { id: 'rect', name: 'Rectangle', icon: IconRect, shortcut: 'R' }, 
    { id: 'circle', name: 'Ellipse', icon: IconCircle, shortcut: 'O' } 
];

const currentToolName = computed(() => tools.find(t => t.id === tool.value)?.name || 'Studio Tool');
const compatibleModels = computed(() => dataStore.availableTtiModels);
const showCursor = computed(() => ['brush', 'eraser', 'circle', 'text', 'clone', 'wand', 'eyedropper'].includes(tool.value));
const combinedCanvasStyle = computed(() => ({ transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})` }));
const activeTask = computed(() => tasksStore.tasks.find(t => t.id === activeTaskId.value));

onMounted(async () => {
    isComponentMounted.value = true;
    uiStore.setPageTitle({ title: '', icon: null });
    nextTick(() => hasHeaderTarget.value = !!document.getElementById('global-header-title-target'));
    
    on('task:completed', onTaskCompleted);
    
    if (maskCanvasRef.value) ctxMask.value = maskCanvasRef.value.getContext('2d');
    if (previewCanvasRef.value) ctxPreview.value = previewCanvasRef.value.getContext('2d');
    
    if (props.id && props.id !== 'new') {
        await loadImage(props.id);
    } else {
        initNewBlankCanvas();
    }

    if (authStore.user) {
        selectedModel.value = authStore.user.iti_binding_model_name || authStore.user.tti_binding_model_name || '';
    }
    
    window.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => { 
    isComponentMounted.value = false; 
    off('task:completed', onTaskCompleted); 
    window.removeEventListener('keydown', handleKeydown); 
});

function initNewBlankCanvas() {
    const defaultW = 1024, defaultH = 1024;
    imageCanvasRef.value.width = defaultW;
    imageCanvasRef.value.height = defaultH;
    
    [maskCanvasRef, previewCanvasRef].forEach(c => { 
        if (c.value) {
            c.value.width = defaultW; 
            c.value.height = defaultH; 
        }
    });

    nextTick(() => {
        const base = layers.value.find(l => l.id === 'base') || layers.value[0];
        if (base?.el) {
            base.el.width = defaultW;
            base.el.height = defaultH;
            base.ctx = base.el.getContext('2d');
            base.ctx.fillStyle = '#FFFFFF';
            base.ctx.fillRect(0, 0, defaultW, defaultH);
        }
        saveState();
        fitToScreen();
    });
}

async function loadImage(id) {
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

        imageCanvasRef.value.width = w; 
        imageCanvasRef.value.height = h;
        
        [maskCanvasRef, previewCanvasRef].forEach(c => { 
            if (c.value) {
                c.value.width = w; 
                c.value.height = h; 
            }
        });

        await nextTick();
        const base = layers.value.find(l => l.id === 'base') || layers.value[0];
        if (base?.el) {
            base.el.width = w;
            base.el.height = h;
            base.ctx = base.el.getContext('2d');
            base.ctx.drawImage(img, 0, 0);
        }
        
        saveState(); 
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
        if (imageCanvasRef.value && (el.width !== imageCanvasRef.value.width || el.height !== imageCanvasRef.value.height)) {
            el.width = imageCanvasRef.value.width;
            el.height = imageCanvasRef.value.height;
        }
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
        blendMode: 'normal'
    });
    activeLayerId.value = id;
    nextTick(() => {
        const l = layers.value.find(x => x.id === id);
        if (l && l.el) {
            l.el.width = imageCanvasRef.value.width; 
            l.el.height = imageCanvasRef.value.height;
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
        blendMode: srcLayer.blendMode
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
    if (!recentColors.value.includes(hex)) {
        recentColors.value.unshift(hex);
        if (recentColors.value.length > 7) recentColors.value.pop();
    }
    uiStore.addNotification(`Sampled Color: ${hex}`, 'info', 1000);
}

function startAction(e) {
    if (e.button !== 0) return;
    const { x, y } = getPointerPos(e);
    
    if (tool.value === 'eyedropper') {
        sampleColorAtPoint(x, y);
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
    
    if (tool.value === 'text') {
        const t = window.prompt("Enter text layer content:");
        if (t) { 
            const c = getActiveContext(); 
            c.fillStyle = color.value; 
            c.font = `bold ${brushSize.value * 1.5}px sans-serif`; 
            c.fillText(t, x, y); 
            saveState(); 
        }
        isDragging = false;
    } else if (['brush', 'eraser', 'clone'].includes(tool.value)) {
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
    saveState(); 
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

function getLayerFilterCss(layer) {
    if (layer.id !== activeLayerId.value) return 'none';
    const adj = adjustments.value;
    return `brightness(${adj.brightness}) contrast(${adj.contrast}) saturate(${adj.saturate}) hue-rotate(${adj.hueRotate}deg) blur(${adj.blur}px)`;
}

function resetAdjustments() {
    adjustments.value = { brightness: 1.0, contrast: 1.0, saturate: 1.0, hueRotate: 0, blur: 0 };
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
    resetAdjustments();
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
            model: selectedModel.value, 
            width: comp.width, 
            height: comp.height,
            strength: editStrength.value
        });
        if (tsk?.id) {
            activeTaskId.value = tsk.id;
        }
    } catch (e) {
        console.error("AI Edit failed:", e);
        isProcessingTask.value = false;
    }
}

async function onTaskCompleted(t) { 
    if (t.id === activeTaskId.value) { 
        isProcessingTask.value = false; 
        if (t.status === 'completed' && t.result) {
            const res = Array.isArray(t.result) ? t.result[0] : t.result;
            if (res?.id) {
                await loadAiResultOntoCanvas(res.id);
            }
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
}

function saveState() {
    if (!imageCanvasRef.value) return;

    const layerSnapshots = layers.value.map(l => ({ 
        id: l.id, 
        name: l.name,
        order: l.order,
        v: l.visible, 
        o: l.opacity,
        b: l.blendMode || 'normal',
        data: l.el ? l.el.toDataURL('image/png') : null
    }));

    const maskData = maskCanvasRef.value ? maskCanvasRef.value.toDataURL('image/png') : null;

    const snapshot = {
        width: imageCanvasRef.value.width,
        height: imageCanvasRef.value.height,
        activeLayerId: activeLayerId.value,
        layers: layerSnapshots,
        maskData: maskData
    };

    if (historyIndex.value < history.value.length - 1) {
        history.value = history.value.slice(0, historyIndex.value + 1);
    }
    history.value.push(snapshot);
    if (history.value.length > 30) {
        history.value.shift();
    }
    historyIndex.value = history.value.length - 1;
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
    
    const restoredLayers = snapshot.layers.map(s => {
        const existing = layers.value.find(l => l.id === s.id);
        return {
            id: s.id,
            name: s.name,
            order: s.order,
            visible: s.v,
            opacity: s.o,
            blendMode: s.b || 'normal',
            el: existing?.el || null,
            ctx: existing?.ctx || null
        };
    });

    layers.value = restoredLayers;
    activeLayerId.value = snapshot.activeLayerId || 'base';

    await nextTick();

    const w = snapshot.width || imageCanvasRef.value.width;
    const h = snapshot.height || imageCanvasRef.value.height;

    snapshot.layers.forEach(s => {
        const l = layers.value.find(x => x.id === s.id);
        if (l && l.el && s.data) {
            l.el.width = w;
            l.el.height = h;
            l.ctx = l.el.getContext('2d');
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

function zoomIn() { zoom.value = Math.min(6, zoom.value + 0.25); }
function zoomOut() { zoom.value = Math.max(0.1, zoom.value - 0.25); }
function handleWheel(e) { 
    if (e.ctrlKey || tool.value === 'pan') { 
        const delta = e.deltaY * -0.0015;
        zoom.value = Math.min(Math.max(0.1, zoom.value + delta), 6); 
    } 
}

function handleKeydown(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    
    if (e.key === 'b' || e.key === 'B') setTool('brush');
    if (e.key === 'e' || e.key === 'E') setTool('eraser');
    if (e.key === 'i' || e.key === 'I') setTool('eyedropper');
    if (e.key === 'w' || e.key === 'W') setTool('wand');
    if (e.key === 'c' || e.key === 'C') setTool('clone');
    if (e.key === 'g' || e.key === 'G') setTool('gradient');
    if (e.key === 't' || e.key === 'T') setTool('text');
    if (e.key === ' ' || e.key === 'h' || e.key === 'H') setTool('pan');
    
    if (e.key === '[') brushSize.value = Math.max(1, brushSize.value - 5);
    if (e.key === ']') brushSize.value = Math.min(300, brushSize.value + 5);

    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { 
        e.preventDefault(); 
        if (e.shiftKey) redo(); 
        else undo(); 
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') { 
        e.preventDefault(); 
        redo(); 
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        saveCanvas();
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