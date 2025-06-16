import { defineStore } from 'pinia';
import { ref, readonly } from 'vue';
import { useUiStore } from './ui';

export const usePyodideStore = defineStore('pyodide', () => {
    const pyodide = ref(null);
    const isLoading = ref(false);
    const isReady = ref(false);
    const stdout = ref('');

    // This object will be exposed to the Python environment
    const PyodideAPI = {
        log: (...args) => {
            stdout.value += args.join(' ') + '\n';
        },
        clear: () => {
            stdout.value = '';
        }
    };
    
    async function initialize() {
        if (isReady.value || isLoading.value) return;

        isLoading.value = true;
        const uiStore = useUiStore();
        uiStore.addNotification('Loading Python runtime...', 'info', 10000);

        try {
            if (typeof window.loadPyodide !== 'function') {
                throw new Error("Pyodide script not loaded from CDN.");
            }
            
            // Attach our API object to the global window scope so Python can see it
            window.pyodideAPI = PyodideAPI;

            const pyodideInstance = await window.loadPyodide();
            
            // Setup Python environment to redirect stdout by importing from the JS global scope
            await pyodideInstance.runPythonAsync(`
                import sys
                import io
                import js  # Import the entire js module

                class JsApiStream(io.StringIO):
                    def write(self, s):
                        # Access the object directly on the js module
                        js.pyodideAPI.log(s)
                
                sys.stdout = JsApiStream()
                sys.stderr = JsApiStream()

                print("Python runtime initialized.")
            `);
            
            pyodide.value = pyodideInstance;
            isReady.value = true;
            uiStore.addNotification('Python runtime ready!', 'success');
        } catch (error) {
            console.error("Failed to initialize Pyodide:", error);
            uiStore.addNotification(`Failed to load Python runtime. Error: ${error.message}`, 'error');
        } finally {
            isLoading.value = false;
        }
    }

    async function runCode(code) {
        if (!isReady.value) {
            useUiStore().addNotification('Python runtime is not ready.', 'warning');
            return { output: null, error: "Pyodide not initialized." };
        }
        
        stdout.value = ''; // Clear previous output
        try {
            await pyodide.value.loadPackagesFromImports(code);
            const result = await pyodide.value.runPythonAsync(code);
            // If the code returns a value, append it to the stdout
            if (result !== undefined && result !== null) {
                stdout.value += String(result);
            }
            return { output: stdout.value.trim(), error: null };
        } catch (error) {
            console.error("Pyodide execution error:", error);
            // The error message is already captured by the redirected stderr
            return { output: null, error: stdout.value.trim() || error.toString() };
        }
    }

    return {
        // State
        isLoading: readonly(isLoading),
        isReady: readonly(isReady),

        // Actions
        initialize,
        runCode,
    };
});