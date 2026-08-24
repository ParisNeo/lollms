<template>
    <div class="bg-white/90 dark:bg-gray-800/90 rounded-2xl border border-gray-200/80 dark:border-gray-700/70 p-4 shadow-sm animate-pulse flex flex-col justify-between h-full">
        <!-- Top Bar Skeleton -->
        <div>
            <div class="flex items-start gap-3.5 mb-3.5">
                <div class="w-12 h-12 rounded-xl shrink-0 bg-gray-200 dark:bg-gray-700"></div>
                <div class="grow min-w-0 mt-0.5">
                    <div class="h-4 w-3/4 rounded-md bg-gray-200 dark:bg-gray-700 mb-2"></div>
                    <div class="flex gap-1.5">
                        <div class="h-3.5 w-14 rounded-md bg-gray-200/80 dark:bg-gray-700/80"></div>
                        <div class="h-3.5 w-12 rounded-md bg-gray-200/60 dark:bg-gray-700/60"></div>
                    </div>
                </div>
            </div>
            
            <!-- Description Bars -->
            <div class="space-y-2 py-2">
                <div class="h-3 rounded bg-gray-200/80 dark:bg-gray-700/80"></div>
                <div class="h-3 rounded bg-gray-200/80 dark:bg-gray-700/80"></div>
                <div class="h-3 w-4/5 rounded bg-gray-200/60 dark:bg-gray-700/60"></div>
            </div>
        </div>
        
        <!-- Bottom Action Bar Skeleton -->
        <div class="pt-3 border-t border-gray-100 dark:border-gray-750 mt-4 flex items-center justify-between gap-3">
            <div class="h-8 grow rounded-lg bg-gray-200 dark:bg-gray-700"></div>
            <div class="flex gap-1.5 shrink-0">
                <div class="h-7 w-7 rounded-lg bg-gray-200/80 dark:bg-gray-700/80"></div>
                <div class="h-7 w-7 rounded-lg bg-gray-200/80 dark:bg-gray-700/80"></div>
            </div>
        </div>
    </div>
</template>