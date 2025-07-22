<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router'; // Import useRoute and useRouter
import { useAuthStore } from '../stores/auth';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import IconBookOpen from '../assets/icons/IconBookOpen.vue';
import IconMagnifyingGlass from '../assets/icons/IconMagnifyingGlass.vue';
import IconXMark from '../assets/icons/IconXMark.vue';
import apiClient from '../services/api';
import { marked } from 'marked';
import hljs from 'highlight.js'; // Assuming you have highlight.js installed
import 'highlight.js/styles/github-dark.css'; // Or your preferred theme

// Configure marked to allow section IDs for smooth scrolling
marked.setOptions({
    gfm: true,
    breaks: true,
    // Add custom renderer to include IDs for headings
    highlight: function(code, lang) {
        const language = hljs.getLanguage(lang) ? lang : 'plaintext';
        return hljs.highlight(code, { language }).value;
    }
});

// Extend markdown renderer for heading IDs
const renderer = {
    heading(text, level, raw) {
        const escapedText = text.toLowerCase().replace(/[^\w]+/g, '-');
        return `
            <h${level} id="${escapedText}">
                ${text}
            </h${level}>`;
    }
};
marked.use({ renderer });


const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const userUiLevel = computed(() => authStore.user?.user_ui_level || 0);

const helpIndexMarkdown = ref(''); // Raw markdown for the index
const parsedHelpIndex = ref([]);    // Structured index for navigation
const helpContent = ref('');        // Current topic's markdown content
const isLoadingContent = ref(true); // Loading state for the main content area
const isLoadingIndex = ref(true);   // Loading state for the sidebar index
const searchQuery = ref('');       // Search query for the sidebar topics
const currentTopicFilename = ref(null); // The filename of the currently displayed topic
const currentSectionId = ref(null); // The ID of the section to scroll to

// Scrollable content area reference for scrolling to sections
const mainContentAreaRef = ref(null);

// Helper to strip markdown bolding from text for display in the sidebar
function stripMarkdownBold(text) {
    return text.replace(/\*\*(.*?)\*\*/g, '$1');
}

const filteredTopics = computed(() => {
    if (!parsedHelpIndex.value) return [];
    const query = searchQuery.value.toLowerCase();
    
    // Filter groups and items based on search query
    const filtered = parsedHelpIndex.value.map(group => {
        // Filter items within each group
        const filteredItems = group.items.filter(item => {
            const titleMatches = stripMarkdownBold(item.title).toLowerCase().includes(query);
            const descriptionMatches = item.description && item.description.toLowerCase().includes(query);
            return titleMatches || descriptionMatches;
        });

        // Check if group title itself matches if no items in it match
        const groupTitleMatches = stripMarkdownBold(group.title).toLowerCase().includes(query);

        if (filteredItems.length > 0 || groupTitleMatches) {
            return {
                ...group,
                items: filteredItems
            };
        }
        return null;
    }).filter(group => group !== null); // Remove nulls (groups with no matching content)

    return filtered;
});


// Function to parse the help_index.md into a structured array
function parseHelpIndexMarkdown(markdown) {
    const lines = markdown.split('\n');
    const sections = [];
    let currentSection = null;

    lines.forEach(line => {
        if (line.startsWith('### ')) { // Section heading
            currentSection = {
                title: stripMarkdownBold(line.substring(4).trim()), // Strip bold for display
                items: []
            };
            sections.push(currentSection);
        } else if (line.startsWith('*   [')) { // List item (link)
            const match = line.match(/\*   \[\*\*(.*?)\*\*\]\(help\/([^\)#]+)(?:#([^\)]+))?\)\s*-\s*(.*)/); // Match title (bold), filename, optional section, and description
            if (match && currentSection) {
                currentSection.items.push({
                    title: stripMarkdownBold(match[1]), // Strip bold for display
                    filename: match[2],
                    sectionId: match[3] || null,
                    description: (match[4] || '').trim()
                });
            }
        }
    });
    return sections;
}

// Function to fetch a specific help topic's content
async function fetchHelpTopicContent(filename, sectionId = null) {
    isLoadingContent.value = true;
    
    // Update route with query params only if not already there,
    // or if we are actively selecting a new topic/section.
    const currentRouteTopic = route.query.topic;
    const currentRouteSection = route.query.section;

    if (searchQuery.value) {
        // If searching, always go through the search endpoint and don't update route.query.topic directly
        // The helpContent will be search results.
        router.replace({ query: { search: searchQuery.value } });
    } else if (filename && (filename !== currentRouteTopic || sectionId !== currentRouteSection)) {
        router.replace({ query: { topic: filename, section: sectionId } });
    } else if (!filename && !searchQuery.value && currentRouteTopic) {
        // Clear route query if no filename and no search and there's a topic in route
        router.replace({ query: {} });
    }


    try {
        let response;
        if (searchQuery.value) { // If search is active, fetch search results
            response = await apiClient.get(`/api/help/search`, { params: { query: searchQuery.value } });
            currentTopicFilename.value = null; // Indicate we're in search results mode
            currentSectionId.value = null;
        } else { // Otherwise, fetch specific topic
            response = await apiClient.get(`/api/help/topic`, { params: { topic_filename: filename } });
            currentTopicFilename.value = filename; // Update current topic being viewed
            currentSectionId.value = sectionId; // Store section ID for scrolling
        }
        
        helpContent.value = marked.parse(response.data);

        // Scroll to section after content is rendered
        nextTick(() => {
            if (sectionId && mainContentAreaRef.value) {
                const targetElement = mainContentAreaRef.value.querySelector(`#${sectionId.toLowerCase().replace(/[^\w]+/g, '-')}`);
                if (targetElement) {
                    targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            } else {
                // If no section or coming from search, scroll to top
                if (mainContentAreaRef.value) {
                    mainContentAreaRef.value.scrollTo({ top: 0, behavior: 'smooth' });
                }
            }
        });

    } catch (error) {
        helpContent.value = `<p class="text-red-500 dark:text-red-400">Failed to load help content: ${error.response?.data?.detail || error.message || 'Unknown error'}</p>`;
        console.error("Error fetching help topic:", error);
    } finally {
        isLoadingContent.value = false;
    }
}

// Initial load: Fetch index and then the default/route-specified topic
onMounted(async () => {
    isLoadingIndex.value = true;
    try {
        const indexResponse = await apiClient.get('/api/help/index');
        helpIndexMarkdown.value = indexResponse.data;
        parsedHelpIndex.value = parseHelpIndexMarkdown(indexResponse.data);
    } catch (error) {
        console.error("Error fetching help index:", error);
        parsedHelpIndex.value = [];
    } finally {
        isLoadingIndex.value = false;

        // After index is loaded, determine initial content to show
        if (route.query.search) {
            searchQuery.value = route.query.search;
            fetchHelpTopicContent(null, null); // Trigger search
        } else if (route.query.topic) {
            fetchHelpTopicContent(route.query.topic, route.query.section);
        } else {
            // Default topic if no specific query or search active
            const defaultFilename = `level_${userUiLevel.value}_beginner.md`; // Level-based default
            fetchHelpTopicContent(defaultFilename);
        }
    }
});

// Watch route for topic/section/search changes and fetch content
watch(route, (newRoute) => {
    // Only react to route changes if it's external (not triggered by selectTopic/searchQuery watch)
    if (newRoute.query.topic !== currentTopicFilename.value || 
        newRoute.query.section !== currentSectionId.value ||
        newRoute.query.search !== searchQuery.value) {
        
        if (newRoute.query.search) {
            searchQuery.value = newRoute.query.search;
        } else {
            searchQuery.value = ''; // Clear search if topic is selected
        }

        if (newRoute.query.topic) {
            fetchHelpTopicContent(newRoute.query.topic, newRoute.query.section);
        } else if (!newRoute.query.search) {
            // If no topic and no search, load default
            const defaultFilename = `level_${userUiLevel.value}_beginner.md`;
            fetchHelpTopicContent(defaultFilename);
        }
    }
}, { deep: true }); // Deep watch for nested query changes

// Watch searchQuery to trigger search or revert to topic view
watch(searchQuery, (newQuery) => {
    if (newQuery) {
        // Push search query to URL without filename
        router.replace({ query: { search: newQuery } }).catch(()=>{}); // Catch navigation errors
        fetchHelpTopicContent(null, null); // Trigger search
    } else {
        // If search query is cleared, revert to showing the current topic or default
        if (currentTopicFilename.value) {
            router.replace({ query: { topic: currentTopicFilename.value, section: currentSectionId.value } }).catch(()=>{});
            fetchHelpTopicContent(currentTopicFilename.value, currentSectionId.value);
        } else {
            // If no topic was previously selected, load the level-based default
            router.replace({ query: {} }).catch(()=>{});
            const defaultFilename = `level_${userUiLevel.value}_beginner.md`;
            fetchHelpTopicContent(defaultFilename);
        }
    }
});

// Update router URL when a topic is selected in the sidebar
function selectTopic(item) {
    searchQuery.value = ''; // Clear search when selecting a topic
    router.push({ query: { topic: item.filename, section: item.sectionId } });
}
</script>

<template>
  <PageViewLayout title="Contextual Help" :title-icon="IconBookOpen">
    <template #sidebar>
      <div class="px-3 py-2.5 text-sm font-medium text-gray-500 dark:text-gray-400">
        Your Current UI Level: <strong class="text-gray-800 dark:text-gray-200">{{ userUiLevel }}</strong>
        <span v-if="authStore.isAdmin" class="text-red-500 dark:text-red-400 ml-1">(Admin)</span>
      </div>
      <p class="px-3 py-2.5 text-xs text-gray-400 dark:text-gray-500">
        The content displayed here is tailored to your current UI experience level and admin status.
      </p>

      <div class="relative px-3 mb-4">
        <input 
          type="text" 
          v-model="searchQuery" 
          placeholder="Search help..."
          class="w-full rounded-md border-gray-300 bg-gray-100 dark:border-gray-600 dark:bg-gray-700/50 py-2 pl-10 pr-10 text-sm focus:border-blue-500 focus:ring-blue-500"
        />
        <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-6">
          <IconMagnifyingGlass class="h-4 w-4 text-gray-400" />
        </div>
        <button v-if="searchQuery" @click="searchQuery = ''" class="absolute inset-y-0 right-0 flex items-center pr-3" title="Clear search">
          <IconXMark class="h-4 w-4 text-gray-400 hover:text-gray-600" />
        </button>
      </div>

      <div v-if="isLoadingIndex" class="px-3 py-5 text-center">
        <p class="text-gray-500 dark:text-gray-400">Loading help index...</p>
      </div>
      <div v-else-if="filteredTopics.length === 0" class="px-3 py-5 text-center">
        <p class="text-gray-500 dark:text-gray-400">No topics found matching your search.</p>
      </div>
      <ul v-else class="space-y-1">
        <li v-for="group in filteredTopics" :key="group.title">
            <h3 class="px-3 py-2 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">{{ group.title }}</h3>
            <ul class="ml-2 border-l border-gray-300 dark:border-gray-600">
                <li v-for="item in group.items" :key="item.filename + (item.sectionId || '')">
                    <button 
                        @click="selectTopic(item)"
                        class="w-full text-left flex flex-col px-3 py-2.5 rounded-lg text-sm font-medium transition-colors"
                        :class="{
                            'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300': currentTopicFilename === item.filename && (!item.sectionId || currentSectionId === item.sectionId) && !searchQuery,
                            'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700': !(currentTopicFilename === item.filename && (!item.sectionId || currentSectionId === item.sectionId) && !searchQuery)
                        }"
                    >
                        <span>{{ item.title }}</span>
                        <span v-if="item.description" class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ item.description }}</span>
                    </button>
                </li>
            </ul>
        </li>
      </ul>
    </template>
    <template #main>
      <div v-if="isLoadingContent" class="text-center py-10">
        <p class="text-gray-500 dark:text-gray-400">Loading help content...</p>
      </div>
      <div v-else ref="mainContentAreaRef" class="prose dark:prose-invert max-w-none text-gray-800 dark:text-gray-100">
        <div v-html="helpContent"></div>
      </div>
    </template>
  </PageViewLayout>
</template>

<style>
/* Basic styling for markdown content, adjust as needed */
.prose h1, .prose h2, .prose h3, .prose h4, .prose h5, .prose h6 {
    border-bottom: 1px solid theme('colors.gray.200');
    padding-bottom: 0.3em;
    margin-top: 1.5em;
    margin-bottom: 1em;
    font-weight: 600;
    line-height: 1.25;
}
.prose h1 { font-size: 2.25em; }
.prose h2 { font-size: 1.75em; }
.prose h3 { font-size: 1.5em; }
.prose p { margin-bottom: 1em; line-height: 1.6; }
.prose ul, .prose ol { margin-bottom: 1em; padding-left: 1.5em; }
.prose li { margin-bottom: 0.5em; }
.prose code { 
    background-color: theme('colors.gray.200'); 
    color: theme('colors.gray.800'); 
    padding: 0.2em 0.4em; 
    border-radius: 3px; 
    font-size: 0.875em;
}
.prose pre {
    background-color: theme('colors.gray.800');
    color: theme('colors.gray.100');
    padding: 1em;
    border-radius: 5px;
    overflow-x: auto;
}
.prose a { color: theme('colors.blue.600'); text-decoration: underline; }
.prose a:hover { color: theme('colors.blue.500'); }

/* Dark mode adjustments */
.prose.dark .prose h1, .prose.dark .prose h2, .prose.dark .prose h3, .prose.dark .prose h4, .prose.dark .prose h5, .prose.dark .prose h6 {
    border-bottom-color: theme('colors.gray.700');
}
.prose.dark .prose code {
    background-color: theme('colors.gray.700');
    color: theme('colors.gray.200');
}
.prose.dark .prose pre {
    background-color: theme('colors.gray.900');
    color: theme('colors.gray.100');
}
.prose.dark .prose a { color: theme('colors.blue.400'); }
.prose.dark .prose a:hover { color: theme('colors.blue.300'); }

/* Image styling within markdown */
.prose img {
    max-width: 100%;
    height: auto;
    display: block; /* Ensures it takes full width of its container, no extra space below */
    margin: 1em auto; /* Center images within the prose block */
    border-radius: 8px; /* Slightly rounded corners for images */
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); /* Subtle shadow */
}

.prose.dark img {
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3); /* Darker shadow for dark mode */
}
</style>