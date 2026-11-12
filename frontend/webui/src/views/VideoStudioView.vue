<template>
    <!-- Header portals mirror the Image Studio pattern -->
    <Teleport to="#global-header-title-target" v-if="hasHeaderTarget">
        <div class="flex items-center gap-2 pointer-events-auto bg-gray-100/80 dark:bg-gray-800/80 px-3 py-1.5 rounded-xl border dark:border-gray-700/50 backdrop-blur-md transition-all shadow-inner">
            <div class="flex flex-col min-w-0">
                <span class="text-[9px] font-black uppercase tracking-widest text-primary leading-none">Video Studio</span>
                <h2 class="font-bold text-gray-800 dark:text-gray-200 text-xs truncate max-w-[220px]">
                    {{ activeProject?.title || 'No project selected' }}
                </h2>
            </div>
        </div>
    </Teleport>

    <Teleport to="#global-header-actions-target" v-if="hasHeaderTarget">
        <div class="flex items-center gap-2 pointer-events-auto">
            <button @click="refresh" class="btn-icon p-1.5 text-gray-500 hover:text-blue-600" title="Refresh">
                <IconRefresh class="w-4 h-4" :class="{ 'animate-spin': isLoading }" />
            </button>
            <button @click="newProject" class="btn btn-secondary px-3 py-2 text-xs font-bold flex items-center gap-1">
                <IconPlus class="w-4 h-4" />
                <span class="hidden sm:inline">New Project</span>
            </button>
        </div>
    </Teleport>

    <div class="h-full flex flex-col bg-gray-50 dark:bg-gray-950 overflow-hidden">
        <!-- No TTV notice -->
        <div v-if="!capabilities.ttv_available" class="p-6">
            <div class="max-w-xl mx-auto text-center p-8 rounded-2xl bg-white dark:bg-gray-900 border dark:border-gray-800 shadow-sm">
                <IconVideoCamera class="w-12 h-12 mx-auto mb-4 text-gray-400" />
                <h2 class="text-lg font-bold text-gray-800 dark:text-gray-200 mb-2">Text-to-Video is not configured</h2>
                <p class="text-sm text-gray-500 dark:text-gray-400">
                    Ask your administrator to activate a Text-to-Video (TTV) binding (e.g. <code class="text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">vllm_omni</code>) before creating video projects.
                </p>
            </div>
        </div>

        <div v-else class="grow min-h-0 flex overflow-hidden">
            <!-- ── CONTROLS DOCK (mirrors Image Studio pattern) ── -->
            <aside
                class="absolute inset-y-0 left-0 z-30 w-[360px] shrink-0 bg-white dark:bg-gray-900 border-r dark:border-gray-800 transform transition-transform duration-300 ease-in-out lg:relative lg:translate-x-0 flex flex-col shadow-2xl"
                :class="showMobileSidebar ? 'translate-x-0' : '-translate-x-full'"
            >
                <div class="p-3 border-b dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50 flex items-center justify-between shrink-0">
                    <div class="flex flex-col min-w-0">
                        <span class="text-[10px] font-black uppercase tracking-widest text-gray-400">Project Settings</span>
                        <span class="text-[10px] text-gray-500 truncate">
                            {{ activeProject ? `#${activeProject.title}` : 'No project selected' }}
                        </span>
                    </div>
                    <button @click="showMobileSidebar = false" class="lg:hidden p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg">
                        <IconXMark class="w-5 h-5 text-gray-500" />
                    </button>
                </div>

                <div v-if="!activeProject" class="grow flex items-center justify-center p-6 text-center text-xs text-gray-400">
                    Select a project from the sidebar to edit its settings.
                </div>

                <div v-else class="grow min-h-0 overflow-y-auto custom-scrollbar p-4 space-y-4">
                    <div>
                        <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Title</label>
                        <input v-model="edit.title" @change="saveProject" class="input-field w-full text-sm" />
                    </div>

                    <div>
                        <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Source Type</label>
                        <div class="grid grid-cols-3 gap-1">
                            <button
                                v-for="mode in sourceModes"
                                :key="mode.value"
                                @click="changeSourceType(mode.value)"
                                class="py-1.5 text-[10px] font-bold uppercase rounded-lg border transition-all"
                                :class="edit.source_type === mode.value
                                    ? 'bg-blue-500 text-white border-blue-500'
                                    : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-700'"
                            >
                                {{ mode.label }}
                            </button>
                        </div>
                    </div>

                    <div>
                        <div class="flex items-center justify-between mb-1">
                            <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400">Prompt</label>
                            <button
                                @click="edit.prompt = ''; saveProject()"
                                class="text-[9px] font-bold text-gray-400 hover:text-red-500 px-1.5 py-0.5 rounded transition-colors uppercase"
                            >
                                Clear
                            </button>
                        </div>
                        <textarea
                            v-model="edit.prompt"
                            @change="saveProject"
                            rows="5"
                            class="input-field w-full text-sm resize-none"
                            placeholder="Describe the video action, camera movement, mood..."
                        ></textarea>
                    </div>

                    <div>
                        <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Negative Prompt</label>
                        <textarea
                            v-model="edit.negative_prompt"
                            @change="saveProject"
                            rows="2"
                            class="input-field w-full text-xs resize-none"
                            placeholder="blurry, distorted, low quality..."
                        ></textarea>
                    </div>

                    <div>
                        <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Format</label>
                        <select v-model="selectedResolution" class="input-field w-full text-xs font-mono">
                            <option v-for="preset in RESOLUTION_PRESETS" :key="preset.value" :value="preset.value">
                                {{ preset.label }}
                            </option>
                            <option value="custom">Custom size…</option>
                        </select>

                        <div v-if="selectedResolution === 'custom'" class="grid grid-cols-2 gap-2 mt-2">
                            <div>
                                <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Width</label>
                                <input v-model.number="edit.width" @change="saveProject" type="number" min="64" max="1920" class="input-field w-full text-xs font-mono" />
                            </div>
                            <div>
                                <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Height</label>
                                <input v-model.number="edit.height" @change="saveProject" type="number" min="64" max="1080" class="input-field w-full text-xs font-mono" />
                            </div>
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-2">
                        <div>
                            <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Frames</label>
                            <input v-model.number="edit.num_frames" @change="saveProject" type="number" min="8" max="240" class="input-field w-full text-xs font-mono" />
                        </div>
                        <div>
                            <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">FPS</label>
                            <input v-model.number="edit.fps" @change="saveProject" type="number" min="1" max="60" class="input-field w-full text-xs font-mono" />
                        </div>
                        <div>
                            <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Steps</label>
                            <input v-model.number="edit.num_inference_steps" @change="saveProject" type="number" class="input-field w-full text-xs font-mono" placeholder="auto" />
                        </div>
                        <div>
                            <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Seed</label>
                            <input v-model.number="edit.seed" @change="saveProject" type="number" class="input-field w-full text-xs font-mono" placeholder="random" />
                        </div>
                    </div>

                    <div>
                        <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Guidance Scale</label>
                        <input v-model.number="edit.guidance_scale" @change="saveProject" type="number" step="0.1" class="input-field w-full text-xs" placeholder="model default" />
                    </div>

                    <div v-if="edit.source_type !== 't2v'" class="pt-3 border-t dark:border-gray-800 space-y-3">
                        <div>
                            <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">First Frame</label>
                            <div class="flex items-center gap-2">
                                <label class="btn btn-secondary btn-xs flex items-center gap-1 cursor-pointer">
                                    <IconArrowUpTray class="w-3 h-3" />
                                    <span>Upload</span>
                                    <input type="file" accept="image/*" @change="onUploadFirst" class="hidden" />
                                </label>
                                <button
                                    v-if="capabilities.tti_available"
                                    @click="openTtiModal('first')"
                                    class="btn btn-secondary btn-xs flex items-center gap-1"
                                >
                                    <IconSparkles class="w-3 h-3" />
                                    <span>Generate</span>
                                </button>
                            </div>
                            <!-- Preview: shows the actual first-frame on disk so the
                                 user can verify the upload / generation succeeded. -->
                            <div v-if="firstImageBlobUrl" class="mt-2 rounded-lg overflow-hidden border dark:border-gray-700 bg-black/20">
                                <img :src="firstImageBlobUrl" alt="First frame" class="w-full max-h-40 object-contain" />
                            </div>
                        </div>

                        <div v-if="edit.source_type === 'flf'">
                            <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Last Frame</label>
                            <div class="flex items-center gap-2">
                                <label class="btn btn-secondary btn-xs flex items-center gap-1 cursor-pointer">
                                    <IconArrowUpTray class="w-3 h-3" />
                                    <span>Upload</span>
                                    <input type="file" accept="image/*" @change="onUploadLast" class="hidden" />
                                </label>
                                <button
                                    v-if="capabilities.tti_available"
                                    @click="openTtiModal('last')"
                                    class="btn btn-secondary btn-xs flex items-center gap-1"
                                >
                                    <IconSparkles class="w-3 h-3" />
                                    <span>Generate</span>
                                </button>
                            </div>
                            <div v-if="lastImageBlobUrl" class="mt-2 rounded-lg overflow-hidden border dark:border-gray-700 bg-black/20">
                                <img :src="lastImageBlobUrl" alt="Last frame" class="w-full max-h-40 object-contain" />
                            </div>
                        </div>
                    </div>

                    <!-- ── MEDIA LIBRARY ──────────────────────────────────────── -->
                    <div class="pt-3 border-t dark:border-gray-800 space-y-3">
                        <div class="flex items-center justify-between">
                            <span class="text-[10px] font-black uppercase tracking-widest text-gray-400">Images ({{ imageLibrary.length }})</span>
                            <label class="text-[10px] font-bold text-blue-500 hover:underline cursor-pointer uppercase">
                                + Add
                                <input type="file" accept="image/*" multiple @change="onAddLibraryImages" class="hidden" />
                            </label>
                        </div>
                        <div v-if="imageLibrary.length === 0" class="text-[11px] text-gray-400 italic">No images yet. Add reference frames or photos here.</div>
                        <div v-else class="grid grid-cols-3 gap-1.5">
                            <div
                                v-for="im in imageLibrary"
                                :key="im.id"
                                class="relative group rounded-lg overflow-hidden border dark:border-gray-700 bg-black/20 aspect-square"
                            >
                                <img
                                    v-if="imageBlobs[im.id]"
                                    :src="imageBlobs[im.id]"
                                    class="w-full h-full object-cover"
                                    :alt="im.prompt || 'library image'"
                                />
                                <div v-else class="w-full h-full flex items-center justify-center text-[9px] text-gray-400 bg-gray-200 dark:bg-gray-800">
                                    Loading…
                                </div>
                                <div class="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-1 p-1">
                                    <button v-if="edit.source_type !== 't2v'" @click.stop="useImageAsAnchor(im.id, 'first')" class="text-[9px] font-black uppercase text-blue-200 hover:text-white">Use as First</button>
                                    <button v-if="edit.source_type === 'flf'" @click.stop="useImageAsAnchor(im.id, 'last')" class="text-[9px] font-black uppercase text-blue-200 hover:text-white">Use as Last</button>
                                    <button @click.stop="deleteLibraryImage(im.id)" class="text-[9px] font-black uppercase text-red-300 hover:text-white">Remove</button>
                                </div>
                                <span v-if="im.role === 'anchor_first'" class="absolute top-1 left-1 px-1 rounded bg-blue-600 text-white text-[8px] font-black">F</span>
                                <span v-if="im.role === 'anchor_last'" class="absolute top-1 right-1 px-1 rounded bg-purple-600 text-white text-[8px] font-black">L</span>
                            </div>
                        </div>
                    </div>

                    <!-- ── VIDEO TAKES (TILE GALLERY) ────────────────────────── -->
                    <div class="pt-3 border-t dark:border-gray-800 space-y-2">
                        <div class="flex items-center justify-between">
                            <span class="text-[10px] font-black uppercase tracking-widest text-gray-400">Takes ({{ videoLibrary.length }})</span>
                            <span class="text-[9px] text-gray-400 italic">Click to preview · + to add to timeline</span>
                        </div>
                        <div v-if="videoLibrary.length === 0" class="text-[11px] text-gray-400 italic">No rendered videos yet. Render takes to fill this gallery.</div>
                        <div v-else class="grid grid-cols-2 gap-2">
                            <div
                                v-for="(v, idx) in videoLibrary"
                                :key="v.id"
                                class="group relative aspect-video rounded-lg overflow-hidden border-2 transition-all cursor-pointer"
                                :class="previewVideoId === v.id
                                    ? 'border-blue-500 ring-2 ring-blue-500/30'
                                    : 'border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-600'"
                                @click="previewTake(v.id)"
                            >
                                <img
                                    v-if="videoThumbBlobs[v.id]"
                                    :src="videoThumbBlobs[v.id]"
                                    class="w-full h-full object-cover"
                                    :alt="`Take ${videoLibrary.length - idx}`"
                                />
                                <div v-else class="w-full h-full flex items-center justify-center bg-gray-200 dark:bg-gray-800">
                                    <IconVideoCamera class="w-6 h-6 text-gray-400 opacity-50" />
                                </div>

                                <!-- Order + type badge -->
                                <div class="absolute top-1 left-1 flex items-center gap-1">
                                    <span class="px-1.5 py-0.5 rounded bg-black/70 text-white text-[8px] font-mono font-black backdrop-blur">
                                        #{{ videoLibrary.length - idx }}
                                    </span>
                                    <span class="px-1.5 py-0.5 rounded bg-blue-600/80 text-white text-[8px] font-black uppercase backdrop-blur">
                                        {{ (v.source_type || 'render').slice(0, 4) }}
                                    </span>
                                </div>

                                <!-- Timeline toggle -->
                                <button
                                    @click.stop="selectedVideoIds.includes(v.id) ? removeFromTimeline(v.id) : addToTimeline(v.id)"
                                    class="absolute top-1 right-1 w-6 h-6 rounded-full flex items-center justify-center text-white text-[11px] font-black shadow-lg transition-all"
                                    :class="selectedVideoIds.includes(v.id)
                                        ? 'bg-blue-600 hover:bg-blue-700'
                                        : 'bg-black/60 hover:bg-blue-600'"
                                    :title="selectedVideoIds.includes(v.id) ? 'Remove from timeline' : 'Add to timeline'"
                                >
                                    {{ selectedVideoIds.includes(v.id) ? '−' : '+' }}
                                </button>

                                <!-- Delete on hover -->
                                <button
                                    @click.stop="deleteLibraryVideo(v.id)"
                                    class="absolute bottom-1 right-1 p-1 rounded bg-red-600/80 hover:bg-red-600 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                                    title="Delete this take"
                                >
                                    <IconTrash class="w-3 h-3" />
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- ── COMPOSER / TIMELINE ────────────────────────────────── -->
                    <div v-if="videoLibrary.length >= 2" class="pt-3 border-t dark:border-gray-800 space-y-2">
                        <div class="flex items-center justify-between">
                            <span class="text-[10px] font-black uppercase tracking-widest text-gray-400">Timeline</span>
                            <span class="text-[9px] text-gray-400 font-mono">{{ selectedVideoIds.length }} clip{{ selectedVideoIds.length === 1 ? '' : 's' }}</span>
                        </div>

                        <div v-if="selectedVideoIds.length === 0" class="text-[11px] text-gray-400 italic p-2 rounded-lg bg-gray-100/60 dark:bg-gray-800/40">
                            Add takes from the gallery above (tap <strong>+</strong>) to build a film timeline.
                        </div>

                        <!-- Horizontal timeline strip with move/remove controls -->
                        <div v-else class="flex items-center gap-1.5 overflow-x-auto custom-scrollbar p-2 rounded-lg bg-gradient-to-r from-gray-100 to-gray-50 dark:from-gray-800/60 dark:to-gray-900/60 border dark:border-gray-800">
                            <template v-for="(vid, i) in selectedVideoIds" :key="vid">
                                <div class="shrink-0 w-24 relative group">
                                    <div class="aspect-video rounded border-2 border-blue-500 overflow-hidden bg-black/50">
                                        <img
                                            v-if="videoThumbBlobs[vid]"
                                            :src="videoThumbBlobs[vid]"
                                            class="w-full h-full object-cover"
                                            alt=""
                                        />
                                        <div v-else class="w-full h-full flex items-center justify-center">
                                            <IconVideoCamera class="w-4 h-4 text-gray-400" />
                                        </div>
                                    </div>
                                    <span class="absolute top-0.5 left-0.5 px-1 py-0.5 rounded bg-blue-600 text-white text-[8px] font-black">
                                        {{ i + 1 }}
                                    </span>
                                    <div class="absolute inset-x-0 bottom-0 flex justify-between p-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button
                                            @click="moveTimelineItem(i, -1)"
                                            :disabled="i === 0"
                                            class="w-4 h-4 rounded bg-black/70 text-white text-[9px] font-black disabled:opacity-30 hover:bg-blue-600"
                                            title="Move left"
                                        >◀</button>
                                        <button
                                            @click="removeFromTimeline(vid)"
                                            class="w-4 h-4 rounded bg-red-600/80 text-white text-[9px] font-black hover:bg-red-600"
                                            title="Remove"
                                        >×</button>
                                        <button
                                            @click="moveTimelineItem(i, 1)"
                                            :disabled="i === selectedVideoIds.length - 1"
                                            class="w-4 h-4 rounded bg-black/70 text-white text-[9px] font-black disabled:opacity-30 hover:bg-blue-600"
                                            title="Move right"
                                        >▶</button>
                                    </div>
                                </div>
                                <span v-if="i < selectedVideoIds.length - 1" class="text-gray-400 text-[10px] shrink-0">→</span>
                            </template>
                        </div>

                        <div class="flex items-center gap-2">
                            <label class="text-[9px] font-black uppercase text-gray-400 tracking-widest">Transition</label>
                            <select v-model="composeTransition" class="input-field !py-1 !text-[10px] flex-1">
                                <option value="none">Hard cut</option>
                                <option value="crossfade">Crossfade</option>
                            </select>
                        </div>

                        <button
                            @click="composeTimeline"
                            :disabled="selectedVideoIds.length < 2 || isComposing"
                            class="btn btn-primary w-full py-2 text-[10px] font-black uppercase tracking-widest flex items-center justify-center gap-1 shadow-md"
                        >
                            <IconAnimateSpin v-if="isComposing" class="w-3 h-3 animate-spin" />
                            <span>{{ isComposing ? 'Composing…' : `Compose Film (${selectedVideoIds.length})` }}</span>
                        </button>

                        <div v-if="activeProject?.composition" class="pt-1 flex items-center justify-between gap-2">
                            <span class="text-[9px] text-emerald-600 dark:text-emerald-400 font-black uppercase">✓ Film ready</span>
                            <div class="flex items-center gap-1">
                                <button @click="playComposition" class="btn btn-secondary btn-xs text-[9px] flex items-center gap-1">
                                    <IconPlayCircle class="w-3 h-3" /> Play
                                </button>
                                <button @click="downloadComposition" class="btn btn-secondary btn-xs text-[9px]">Download</button>
                                <button @click="deleteComposition" class="btn btn-secondary btn-xs text-[9px] text-red-500">Clear</button>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="p-4 border-t dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50 shrink-0">
                    <button
                        @click="renderCurrent"
                        class="btn btn-primary w-full py-3 text-xs font-black uppercase tracking-widest shadow-xl shadow-blue-500/20 flex items-center justify-center gap-2"
                        :disabled="isRendering || !activeProject"
                    >
                        <IconAnimateSpin v-if="isRendering" class="w-4 h-4 animate-spin" />
                        <IconPlayCircle v-else class="w-4 h-4" />
                        <span>{{ isRendering ? 'Rendering…' : 'Render Video' }}</span>
                    </button>
                </div>
            </aside>

            <!-- Backdrop for mobile drawer -->
            <div v-if="showMobileSidebar" @click="showMobileSidebar = false" class="absolute inset-0 bg-black/40 z-20 lg:hidden backdrop-blur-sm"></div>

            <!-- ── MAIN VIEWPORT ── -->
            <main class="grow min-w-0 flex flex-col overflow-hidden">
                <!-- Empty selection -->
                <div v-if="!activeProject" class="flex-1 flex items-center justify-center p-8 text-center">
                    <div>
                        <IconVideoCamera class="w-12 h-12 mx-auto mb-3 text-gray-300" />
                        <p class="text-sm text-gray-500">Select a project from the sidebar, or create a new one.</p>
                    </div>
                </div>

                <div v-else class="flex-1 flex flex-col min-h-0 bg-black/5 dark:bg-gray-950">
                    <!-- Viewport -->
                    <div class="grow flex items-center justify-center p-4 overflow-hidden">
                        <!-- Render active -->
                        <div v-if="activeRenderTask && activeRenderTask.status !== 'completed' && activeRenderTask.status !== 'failed'" class="text-center text-gray-500">
                            <IconAnimateSpin class="w-12 h-12 mx-auto mb-3 animate-spin text-blue-500" />
                            <p class="text-xs font-bold uppercase tracking-widest">{{ activeRenderTask.progress }}% — {{ activeRenderTask.status }}</p>
                            <p class="text-[11px] text-gray-400 mt-1 max-w-sm mx-auto">{{ activeRenderTask.description }}</p>
                        </div>

                        <!-- Rendered video -->
                        <video v-else-if="videoBlobUrl && !videoError"
                            :key="videoKey"
                            ref="videoEl"
                            :src="videoBlobUrl"
                            controls
                            class="max-h-full max-w-full rounded-lg shadow-2xl"
                            @error="videoError = true"
                        ></video>

                        <!-- Empty state -->
                        <div v-else-if="!activeRenderTask" class="text-center text-gray-400">
                            <IconVideoCamera class="w-14 h-14 mx-auto mb-3 opacity-30" />
                            <p class="text-sm font-bold text-gray-500">No rendered video</p>
                            <p class="text-xs">Fill in your prompt in the controls, then click <strong>Render Video</strong>.</p>
                        </div>
                    </div>

                    <!-- Action bar -->
                    <div class="p-3 border-t dark:border-gray-800 bg-white dark:bg-gray-900 flex items-center justify-between gap-2 shrink-0">
                        <div class="text-[11px] text-gray-500 min-w-0">
                            <span v-if="activeRenderTask" class="font-bold uppercase tracking-widest text-[10px]">{{ activeRenderTask.status }} • {{ activeRenderTask.progress }}%</span>
                            <span v-else-if="activeProject?.updated_at" class="truncate">Updated {{ new Date(activeProject.updated_at).toLocaleString() }}</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <button v-if="activeProject?.video_filename" @click="downloadCurrent" class="btn btn-secondary text-xs flex items-center gap-1">
                                <IconDownload class="w-3.5 h-3.5" />
                                <span>Download</span>
                            </button>
                            <button @click="renderCurrent" class="btn btn-primary text-xs font-black uppercase tracking-widest flex items-center gap-2"
                                :disabled="isRendering">
                                <IconAnimateSpin v-if="isRendering" class="w-3.5 h-3.5 animate-spin" />
                                <IconPlayCircle v-else class="w-3.5 h-3.5" />
                                <span>Render</span>
                            </button>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    </div>

    <!-- TTI modal — the "Generate" buttons live in the controls dock and open
         this modal. Calls the atomic /generate-frame endpoint so the image is
         persisted server-side and reflected immediately. -->
    <div v-if="ttiModal.open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" @click.self="closeTtiModal">
        <div class="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md max-h-[90vh] flex flex-col">
            <div class="p-4 border-b dark:border-gray-800 flex items-center justify-between shrink-0">
                <h3 class="text-sm font-black uppercase tracking-widest text-gray-700 dark:text-gray-200">
                    Generate {{ ttiModal.slot === 'first' ? 'First' : 'Last' }} Frame
                </h3>
                <button @click="closeTtiModal" class="p-1 text-gray-400 hover:text-red-500"><IconXMark class="w-4 h-4" /></button>
            </div>
            <div class="p-4 space-y-3 overflow-y-auto custom-scrollbar">
                <div v-if="ttiModal.previewB64" class="rounded-lg overflow-hidden border dark:border-gray-700 bg-black/20">
                    <img :src="`data:image/png;base64,${ttiModal.previewB64}`" alt="Generated frame" class="w-full max-h-64 object-contain" />
                </div>

                <div>
                    <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Prompt</label>
                    <textarea v-model="ttiModal.prompt" rows="3" class="input-field w-full text-xs"></textarea>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    <div>
                        <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Width</label>
                        <input v-model.number="ttiModal.width" type="number" class="input-field w-full text-xs" />
                    </div>
                    <div>
                        <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Height</label>
                        <input v-model.number="ttiModal.height" type="number" class="input-field w-full text-xs" />
                    </div>
                </div>
            </div>
            <div class="p-4 border-t dark:border-gray-800 flex justify-end gap-2 shrink-0">
                <button @click="closeTtiModal" class="btn btn-secondary text-xs">
                    {{ ttiModal.previewB64 ? 'Done' : 'Cancel' }}
                </button>
                <button @click="generateTtiImage" :disabled="ttiModal.busy" class="btn btn-primary text-xs flex items-center gap-1">
                    <IconAnimateSpin v-if="ttiModal.busy" class="w-3.5 h-3.5 animate-spin" />
                    <span>{{ ttiModal.busy ? 'Generating…' : (ttiModal.previewB64 ? 'Regenerate' : 'Generate') }}</span>
                </button>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue';
import { useVideoStore } from '../stores/video';
import { useTasksStore } from '../stores/tasks';
import { useUiStore } from '../stores/ui';
import { storeToRefs } from 'pinia';
import apiClient from '../services/api';

import IconVideoCamera from '../assets/icons/IconVideoCamera.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconPlayCircle from '../assets/icons/IconPlayCircle.vue';
import IconDownload from '../assets/icons/IconDownload.vue';
import IconXMark from '../assets/icons/IconXMark.vue';
import IconArrowUpTray from '../assets/icons/IconArrowUpTray.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconTrash from '../assets/icons/IconTrash.vue';

const store = useVideoStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();

const { projects, isLoading, capabilities, activeProjectId, activeProject } = storeToRefs(store);
const { tasks } = storeToRefs(tasksStore);

const hasHeaderTarget = ref(false);
const showMobileSidebar = ref(false);
const videoKey = ref(Date.now());
const videoError = ref(false);
const videoBlobUrl = ref(null);
const videoEl = ref(null);
const activeRenderTaskId = ref(null);
const firstImageBlobUrl = ref(null);
const lastImageBlobUrl = ref(null);

// Local editable mirror of the active project. Synced from activeProject,
// persisted via saveProject(). Matches the pattern used by Image Studio's dock.
const edit = reactive({
    title: '',
    prompt: '',
    negative_prompt: '',
    source_type: 't2v',
    width: 512,
    height: 512,
    num_frames: 48,
    fps: 12,
    num_inference_steps: null,
    guidance_scale: null,
    seed: null,
});

watch(activeProject, (p) => {
    if (!p) return;
    edit.title = p.title || '';
    edit.prompt = p.prompt || '';
    edit.negative_prompt = p.negative_prompt || '';
    edit.source_type = p.source_type || 't2v';
    edit.width = p.width ?? 512;
    edit.height = p.height ?? 512;
    edit.num_frames = p.num_frames ?? 48;
    edit.fps = p.fps ?? 12;
    edit.num_inference_steps = p.num_inference_steps ?? null;
    edit.guidance_scale = p.guidance_scale ?? null;
    edit.seed = p.seed ?? null;
}, { immediate: true });

const sourceModes = [
    { value: 't2v', label: 'T2V' },
    { value: 'i2v', label: 'Image+Text' },
    { value: 'flf', label: 'First+Last' },
];

// Standard video formats — mirrors Image Studio's aspect-ratio doctrine so
// users pick a known frame size instead of typing raw pixels.
const RESOLUTION_PRESETS = [
    { value: '512x512',   label: '512 × 512 · 1:1 Square' },
    { value: '768x512',   label: '768 × 512 · 3:2 Landscape' },
    { value: '512x768',   label: '512 × 768 · 2:3 Portrait' },
    { value: '960x544',   label: '960 × 544 · 16:9 Cinematic' },
    { value: '1024x576',  label: '1024 × 576 · 16:9 HD' },
    { value: '1344x768',  label: '1344 × 768 · 7:4 Widescreen' },
    { value: '1280x720',  label: '1280 × 720 · 16:9 HD' },
    { value: '1920x1080', label: '1920 × 1080 · 16:9 Full HD' },
    { value: '576x1024',  label: '576 × 1024 · 9:16 Portrait' },
    { value: '720x1280',  label: '720 × 1280 · 9:16 HD Portrait' },
    { value: '1080x1920', label: '1080 × 1920 · 9:16 Full HD Portrait' },
];

const selectedResolution = computed({
    get: () => {
        const key = `${edit.width}x${edit.height}`;
        return RESOLUTION_PRESETS.some(p => p.value === key) ? key : 'custom';
    },
    set: (val) => {
        if (val === 'custom') return;
        const [w, h] = val.split('x').map(Number);
        edit.width = w;
        edit.height = h;
        saveProject();
    },
});

async function saveProject() {
    if (!activeProject.value) return;
    await store.updateProject(activeProject.value.id, {
        title: edit.title,
        prompt: edit.prompt,
        negative_prompt: edit.negative_prompt,
        source_type: edit.source_type,
        width: edit.width,
        height: edit.height,
        num_frames: edit.num_frames,
        fps: edit.fps,
        num_inference_steps: edit.num_inference_steps,
        guidance_scale: edit.guidance_scale,
        seed: edit.seed,
    });
}

async function changeSourceType(mode) {
    edit.source_type = mode;
    await saveProject();
}

async function onUploadFirst(event) {
    const file = event.target.files?.[0];
    if (!file || !activeProject.value) return;
    try {
        await store.uploadFirstImage(activeProject.value.id, file);
        activeProject.value.first_image = true;
        await store.fetchProjects();
    } catch (e) {
        uiStore.addNotification(e?.response?.data?.detail || 'Failed to upload first frame.', 'error');
    } finally {
        event.target.value = '';
    }
}

async function onUploadLast(event) {
    const file = event.target.files?.[0];
    if (!file || !activeProject.value) return;
    try {
        await store.uploadLastImage(activeProject.value.id, file);
        activeProject.value.last_image = true;
        await store.fetchProjects();
    } catch (e) {
        uiStore.addNotification(e?.response?.data?.detail || 'Failed to upload last frame.', 'error');
    } finally {
        event.target.value = '';
    }
}

const ttiModal = reactive({
    open: false,
    slot: 'first',
    busy: false,
    prompt: '',
    width: 512,
    height: 512,
    projectId: null,
    previewB64: null,
});

// ── Media library + composer ───────────────────────────────────────────
const imageLibrary = computed(() => activeProject.value?.images || []);
const videoLibrary = computed(() => activeProject.value?.videos || []);
const selectedVideoIds = ref([]);
const composeTransition = ref('none');
const composeTaskId = ref(null);
const compositionBlobUrl = ref(null);
const previewVideoId = ref(null);

// Auth-protected images must be fetched through apiClient (Bearer header) and
// rendered as blob URLs. `<img src="/api/...">` cannot send the Authorization
// header, so the server returns 401 and the tile shows a broken image. Keeping
// per-id blob caches sidesteps repeated fetches for the same thumbnail.
const imageBlobs = reactive({});       // imageId → object URL
const videoThumbBlobs = reactive({});  // videoId → object URL

function _revokeMap(map) {
    for (const key of Object.keys(map)) {
        try { URL.revokeObjectURL(map[key]); } catch (_) {}
        delete map[key];
    }
}

async function _fetchBlobIntoMap(url, map, key) {
    if (map[key]) return;                 // already cached
    try {
        const res = await apiClient.get(url, { responseType: 'blob' });
        map[key] = URL.createObjectURL(res.data);
    } catch (e) {
        console.warn('Failed to load media blob:', url, e);
    }
}

async function loadImageThumbBLOB(imageId) {
    if (!activeProject.value) return;
    await _fetchBlobIntoMap(
        `/api/video-studio/projects/${activeProject.value.id}/images/${imageId}`,
        imageBlobs,
        imageId
    );
}

async function loadVideoThumbBLOB(videoId) {
    if (!activeProject.value) return;
    await _fetchBlobIntoMap(
        `/api/video-studio/projects/${activeProject.value.id}/videos/${videoId}/thumbnail`,
        videoThumbBlobs,
        videoId
    );
}

// Click a take tile to load its specific MP4 into the main viewport.
async function previewTake(videoId) {
    previewVideoId.value = videoId;
    if (!activeProject.value) return;
    _revokeIfSet(videoBlobUrl);
    videoError.value = false;
    try {
        const res = await apiClient.get(
            `/api/video-studio/projects/${activeProject.value.id}/videos/${videoId}`,
            { responseType: 'blob' }
        );
        videoBlobUrl.value = URL.createObjectURL(res.data);
        videoKey.value = Date.now();
    } catch (e) {
        console.warn('Failed to preview take:', e);
        videoError.value = true;
    }
}

// Reorder helper used by the timeline arrows.
function moveTimelineItem(index, direction) {
    const target = index + direction;
    if (target < 0 || target >= selectedVideoIds.value.length) return;
    const item = selectedVideoIds.value.splice(index, 1)[0];
    selectedVideoIds.value.splice(target, 0, item);
}

const composeTask = computed(() => {
    if (!composeTaskId.value) return null;
    return tasks.value.find(t => t.id === composeTaskId.value) || null;
});
const isComposing = computed(() =>
    !!composeTask.value
    && composeTask.value.status !== 'completed'
    && composeTask.value.status !== 'failed'
);

async function loadMediaLibrary() {
    if (!activeProject.value) return;
    try {
        const res = await apiClient.get(`/api/video-studio/projects/${activeProject.value.id}/videos`);
        const vids = res.data?.videos || [];
        if (activeProject.value) {
            activeProject.value.videos = vids;
            activeProject.value.composition = res.data?.composition || null;
        }
    } catch (e) { /* non-fatal */ }
    try {
        const res = await apiClient.get(`/api/video-studio/projects/${activeProject.value.id}/images`);
        if (activeProject.value) activeProject.value.images = res.data?.images || [];
    } catch (e) { /* non-fatal */ }
    // Drop any timeline ids that no longer exist.
    const validIds = new Set((activeProject.value?.videos || []).map(v => v.id));
    selectedVideoIds.value = selectedVideoIds.value.filter(id => validIds.has(id));

    // Purge blob cache entries for media that no longer exists.
    const validImageIds = new Set((activeProject.value?.images || []).map(i => i.id));
    for (const key of Object.keys(imageBlobs)) {
        if (!validImageIds.has(key)) {
            try { URL.revokeObjectURL(imageBlobs[key]); } catch (_) {}
            delete imageBlobs[key];
        }
    }
    const validVideoIds = new Set((activeProject.value?.videos || []).map(v => v.id));
    for (const key of Object.keys(videoThumbBlobs)) {
        if (!validVideoIds.has(key)) {
            try { URL.revokeObjectURL(videoThumbBlobs[key]); } catch (_) {}
            delete videoThumbBlobs[key];
        }
    }

    // Prefetch all thumbnails in parallel — same auth-aware path as the video
    // viewport. Failures are non-fatal (a placeholder icon stays visible).
    await Promise.all([
        ...(activeProject.value?.images || []).map(im => loadImageThumbBLOB(im.id)),
        ...(activeProject.value?.videos || []).map(v => loadVideoThumbBLOB(v.id)),
    ]);
}

async function onAddLibraryImages(event) {
    const files = Array.from(event.target.files || []);
    if (!files.length || !activeProject.value) return;
    for (const file of files) {
        try {
            const form = new FormData();
            form.append('file', file);
            await apiClient.post(
                `/api/video-studio/projects/${activeProject.value.id}/images`,
                form,
                { headers: { 'Content-Type': 'multipart/form-data' } }
            );
        } catch (e) {
            console.warn('Library image upload failed:', e);
        }
    }
    event.target.value = '';
    await loadMediaLibrary();
}

async function useImageAsAnchor(imageId, role) {
    if (!activeProject.value) return;
    const im = imageLibrary.value.find(i => i.id === imageId);
    if (!im) return;
    try {
        // Fetch blob, then post as anchor so the server writes _first/_last.png.
        const blob = await apiClient.get(
            `/api/video-studio/projects/${activeProject.value.id}/images/${imageId}`,
            { responseType: 'blob' }
        );
        const b64 = await new Promise((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(typeof r.result === 'string' ? r.result.split(',').pop() : '');
            r.onerror = () => reject(r.error);
            r.readAsDataURL(blob.data);
        });
        await apiClient.post(
            `/api/video-studio/projects/${activeProject.value.id}/${role}-image`,
            { b64_image: b64 }
        );
        activeProject.value[`${role}_image`] = true;
        await store.fetchProjects();
        await loadMediaLibrary();
    } catch (e) {
        uiStore.addNotification(e?.response?.data?.detail || `Failed to set ${role} frame.`, 'error');
    }
}

async function deleteLibraryImage(imageId) {
    if (!activeProject.value) return;
    try {
        await apiClient.delete(`/api/video-studio/projects/${activeProject.value.id}/images/${imageId}`);
        await store.fetchProjects();
        await loadMediaLibrary();
    } catch (e) {
        uiStore.addNotification('Failed to remove image.', 'error');
    }
}

async function deleteLibraryVideo(videoId) {
    if (!activeProject.value) return;
    const { confirmed } = await uiStore.showConfirmation({
        title: 'Delete this take?',
        message: 'The video file will be removed from the project.',
        confirmText: 'Delete', danger: true,
    });
    if (!confirmed) return;
    try {
        await apiClient.delete(`/api/video-studio/projects/${activeProject.value.id}/videos/${videoId}`);
        await store.fetchProjects();
        await loadMediaLibrary();
    } catch (e) {
        uiStore.addNotification('Failed to delete video.', 'error');
    }
}

function addToTimeline(id) {
    if (!selectedVideoIds.value.includes(id)) selectedVideoIds.value.push(id);
}
function removeFromTimeline(id) {
    selectedVideoIds.value = selectedVideoIds.value.filter(v => v !== id);
}

async function composeTimeline() {
    if (!activeProject.value || selectedVideoIds.value.length < 2) return;
    try {
        const res = await apiClient.post(
            `/api/video-studio/projects/${activeProject.value.id}/compose`,
            { video_ids: [...selectedVideoIds.value], transition: composeTransition.value }
        );
        composeTaskId.value = res.data?.id || null;
    } catch (e) {
        uiStore.addNotification(e?.response?.data?.detail || 'Failed to start composition.', 'error');
    }
}

async function loadCompositionBlob() {
    if (compositionBlobUrl.value) {
        try { URL.revokeObjectURL(compositionBlobUrl.value); } catch (_) {}
        compositionBlobUrl.value = null;
    }
    if (!activeProject.value?.composition) return;
    try {
        const res = await apiClient.get(
            `/api/video-studio/projects/${activeProject.value.id}/composed`,
            { responseType: 'blob' }
        );
        compositionBlobUrl.value = URL.createObjectURL(res.data);
    } catch (e) { /* noop */ }
}

function playComposition() {
    if (!compositionBlobUrl.value) return;
    // Route the composed film through the viewport as the current video.
    if (videoBlobUrl.value) {
        try { URL.revokeObjectURL(videoBlobUrl.value); } catch (_) {}
    }
    videoBlobUrl.value = compositionBlobUrl.value;
    videoKey.value = Date.now();
    videoError.value = false;
}

async function downloadComposition() {
    if (!activeProject.value?.composition) return;
    try {
        const res = await apiClient.get(
            `/api/video-studio/projects/${activeProject.value.id}/composed`,
            { responseType: 'blob' }
        );
        const url = URL.createObjectURL(res.data);
        const a = document.createElement('a');
        a.href = url; a.download = `${activeProject.value.title}_film.mp4`;
        document.body.appendChild(a); a.click();
        document.body.removeChild(a); URL.revokeObjectURL(url);
    } catch (e) {
        uiStore.addNotification('Failed to download composition.', 'error');
    }
}

async function deleteComposition() {
    if (!activeProject.value) return;
    try {
        await apiClient.delete(`/api/video-studio/projects/${activeProject.value.id}/composed`);
        await store.fetchProjects();
        await loadMediaLibrary();
    } catch (e) {
        uiStore.addNotification('Failed to clear composition.', 'error');
    }
}

const activeRenderTask = computed(() => {
    if (!activeRenderTaskId.value) return null;
    return tasks.value.find(t => t.id === activeRenderTaskId.value) || null;
});

const isRendering = computed(() =>
    !!activeRenderTask.value
    && activeRenderTask.value.status !== 'completed'
    && activeRenderTask.value.status !== 'failed'
);

function _revokeIfSet(refHolder) {
    if (refHolder.value) {
        try { URL.revokeObjectURL(refHolder.value); } catch (_) {}
        refHolder.value = null;
    }
}

async function loadFrameBlobs() {
    _revokeIfSet(firstImageBlobUrl);
    _revokeIfSet(lastImageBlobUrl);

    const project = activeProject.value;
    if (!project) return;

    const jobs = [];
    if (project.first_image) {
        jobs.push(
            apiClient
                .get(`/api/video-studio/projects/${project.id}/first-image`, { responseType: 'blob' })
                .then(res => { firstImageBlobUrl.value = URL.createObjectURL(res.data); })
                .catch(e => console.warn('Failed to load first-frame image blob:', e))
        );
    }
    if (project.last_image) {
        jobs.push(
            apiClient
                .get(`/api/video-studio/projects/${project.id}/last-image`, { responseType: 'blob' })
                .then(res => { lastImageBlobUrl.value = URL.createObjectURL(res.data); })
                .catch(e => console.warn('Failed to load last-frame image blob:', e))
        );
    }
    if (jobs.length) await Promise.all(jobs);
}

async function loadVideoBlob() {
    if (videoBlobUrl.value) {
        try { URL.revokeObjectURL(videoBlobUrl.value); } catch (_) {}
        videoBlobUrl.value = null;
    }
    videoError.value = false;

    if (!activeProject.value?.video_filename) return;
    try {
        const res = await apiClient.get(
            `/api/video-studio/projects/${activeProject.value.id}/video`,
            { responseType: 'blob' }
        );
        videoBlobUrl.value = URL.createObjectURL(res.data);
        videoKey.value = Date.now();
    } catch (e) {
        console.warn('Failed to load rendered video blob:', e);
        videoError.value = true;
    }
}

watch(
    () => [activeProject.value?.id, activeProject.value?.first_image, activeProject.value?.last_image],
    () => { loadFrameBlobs(); },
    { immediate: true }
);

watch(
    () => [activeProject.value?.id, activeProject.value?.video_filename],
    () => { loadVideoBlob(); },
    { immediate: true }
);

watch(tasks, async () => {
    if (activeRenderTask.value) {
        if (activeRenderTask.value.status === 'completed') {
            await store.fetchProjects();
            videoError.value = false;
            await loadVideoBlob();
            await loadMediaLibrary();
        }
    }
    if (composeTask.value && composeTask.value.status === 'completed') {
        composeTaskId.value = null;
        await store.fetchProjects();
        await loadMediaLibrary();
        await loadCompositionBlob();
        uiStore.addNotification('Film composed successfully.', 'success', 2500);
    } else if (composeTask.value && composeTask.value.status === 'failed') {
        composeTaskId.value = null;
        uiStore.addNotification('Composition failed. Check the task log.', 'error');
    }
}, { deep: true });

// Reload media library and composition blob when the project changes.
watch(() => activeProject.value?.id, async (id) => {
    selectedVideoIds.value = [];
    previewVideoId.value = null;
    if (!id) {
        _revokeIfSet(compositionBlobUrl);
        _revokeMap(imageBlobs);
        _revokeMap(videoThumbBlobs);
        return;
    }
    _revokeMap(imageBlobs);
    _revokeMap(videoThumbBlobs);
    await loadMediaLibrary();
    await loadCompositionBlob();
});

async function newProject() {
    if (isRendering.value) {
        uiStore.addNotification(
            'A render is in progress. Wait for it to finish before creating a new project.',
            'warning'
        );
        return;
    }
    try {
        await store.createProject({
            title: 'Untitled Video',
            prompt: '',
            source_type: 't2v',
            width: 512,
            height: 512,
            num_frames: 48,
            fps: 12,
        });
    } catch (e) {
        console.error('Failed to create video project:', e);
        uiStore.addNotification(
            e?.response?.data?.detail || 'Failed to create video project.',
            'error'
        );
    }
}

async function renderCurrent() {
    if (!activeProject.value) return;
    // Ensure any pending edits are saved before kicking off the render.
    await saveProject();
    try {
        const task = await store.renderProject(activeProject.value.id);
        activeRenderTaskId.value = task.id;
        videoError.value = false;
    } catch (e) {
        uiStore.addNotification('Failed to start render.', 'error');
    }
}

function downloadCurrent() {
    store.downloadVideo(activeProject.value);
}

watch(() => projects.value.length, (length) => {
    if (length > 0 && !activeProjectId.value) {
        activeProjectId.value = projects.value[0].id;
    }
});

async function refresh() {
    await Promise.all([store.fetchProjects(), store.fetchCapabilities()]);
}

function openTtiModal(slot) {
    if (!activeProject.value) return;
    ttiModal.slot = slot;
    ttiModal.projectId = activeProject.value.id;
    ttiModal.prompt = activeProject.value.prompt || '';
    ttiModal.width = activeProject.value.width || 512;
    ttiModal.height = activeProject.value.height || 512;
    ttiModal.previewB64 = null;
    ttiModal.open = true;
}

async function onNewProjectEvent() {
    await newProject();
}

async function generateTtiImage() {
    if (!ttiModal.prompt.trim()) return;
    const projectId = ttiModal.projectId || activeProject.value?.id;
    if (!projectId) {
        uiStore.addNotification('Select a project before generating a frame.', 'error');
        return;
    }

    ttiModal.busy = true;
    try {
        const res = await apiClient.post(
            `/api/video-studio/projects/${projectId}/generate-frame`,
            {
                prompt: ttiModal.prompt,
                role: ttiModal.slot,
                width: ttiModal.width,
                height: ttiModal.height,
            }
        );
        const data = res.data || {};
        ttiModal.previewB64 = data.b64_image || null;

        if (data.project && activeProject.value && data.project.id === activeProject.value.id) {
            activeProject.value.first_image = !!data.project.first_image;
            activeProject.value.last_image = !!data.project.last_image;
            activeProject.value.updated_at = data.project.updated_at;
        }
        await store.fetchProjects();
    } catch (e) {
        const detail = e?.response?.data?.detail || 'Failed to generate reference image.';
        uiStore.addNotification(detail, 'error');
    } finally {
        ttiModal.busy = false;
    }
}

function closeTtiModal() {
    ttiModal.open = false;
    ttiModal.previewB64 = null;
}

onMounted(async () => {
    hasHeaderTarget.value = !!document.getElementById('global-header-title-target')
        && !!document.getElementById('global-header-actions-target');
    window.addEventListener('lollms:new-video-project', onNewProjectEvent);
    await Promise.all([store.fetchProjects(), store.fetchCapabilities()]);
    if (!activeProjectId.value && projects.value.length) {
        activeProjectId.value = projects.value[0].id;
    }
    await loadMediaLibrary();
    await loadCompositionBlob();
});

onUnmounted(() => {
    window.removeEventListener('lollms:new-video-project', onNewProjectEvent);
    videoEl.value = null;
    if (videoBlobUrl.value) {
        try { URL.revokeObjectURL(videoBlobUrl.value); } catch (_) {}
        videoBlobUrl.value = null;
    }
    _revokeIfSet(firstImageBlobUrl);
    _revokeIfSet(lastImageBlobUrl);
    _revokeIfSet(compositionBlobUrl);
    _revokeMap(imageBlobs);
    _revokeMap(videoThumbBlobs);
});
</script>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>