import { defineStore } from 'pinia';
import { ref, readonly } from 'vue';
import { useUiStore } from './ui';

export const usePyodideStore = defineStore('pyodide', () => {
    const pyodide = ref(null);
    const isLoading = ref(false);
    const isReady = ref(false);
    const stdout = ref('');
    const activeCanvasSelector = ref(null);

    const PyodideAPI = {
        log: (...args) => {
            const message = args.join(' ');
            if (typeof message === 'string') {
                stdout.value += message + '\n';
            }
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
            
            window.pyodideAPI = PyodideAPI;
            const pyodideInstance = await window.loadPyodide();
            
            await pyodideInstance.runPythonAsync(`
                import sys
                import io
                import js

                class JsApiStream(io.StringIO):
                    def write(self, s):
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

    function wrapCodeForExecution(code) {
        // --- THIS IS THE NEW, ROBUST WRAPPER ---
        const escapedCode = code.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
        
        return `
import io
import base64
import os
import sys

def run_and_get_results():
    result = {'image': None, 'new_files': []}
    initial_files = set(os.listdir('.'))

    # Preemptively set Matplotlib backend to non-interactive 'Agg'
    # if the user code seems to be using it. This prevents the rogue UI.
    if 'matplotlib.pyplot' in """${escapedCode}""":
        try:
            import matplotlib
            matplotlib.use('Agg')
        except ImportError:
            # If matplotlib isn't installed yet, that's fine, we'll catch it later
            pass

    # Now, execute the user's code
    user_code = """${escapedCode}"""
    exec(user_code)
    
    # After execution, find any new files that were created
    final_files = set(os.listdir('.'))
    new_files_list = list(final_files - initial_files)
    
    # Filter out internal cache directories
    result['new_files'] = [f for f in new_files_list if f not in ['.matplotlib', '.config']]

    # Safely check if a plot was created and capture it
    if 'matplotlib.pyplot' in sys.modules:
        try:
            import matplotlib.pyplot as plt
            if plt.get_fignums():
                buf = io.BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                result['image'] = base64.b64encode(buf.read()).decode('utf-8')
                plt.close('all')
        except Exception:
            # Ignore if plot saving fails for any reason
            pass
    
    return result

run_and_get_results()
`;
    }

    async function runCode(code, canvasSelector = null) {
        const uiStore = useUiStore();
        if (!isReady.value) {
            return { output: null, error: "Pyodide not initialized.", image: null, usesCanvas: false, newFiles: [] };
        }
        
        stdout.value = '';
        activeCanvasSelector.value = canvasSelector;

        try {
            // --- UNIFIED EXECUTION PIPELINE ---

            // 1. Install packages from #micropip comment (e.g., pygame-web, python-pptx)
            const micropipMatch = code.match(/^#\s*micropip:\s*install\s+(.+)$/m);
            if (micropipMatch) {
                const packagesToInstall = micropipMatch[1].split(/\s+/).filter(p => p);
                if (packagesToInstall.length > 0) {
                    uiStore.addNotification(`Loading installer...`, 'info', 3000);
                    await pyodide.value.loadPackage('micropip');
                    const micropip = pyodide.value.pyimport('micropip');
                    uiStore.addNotification(`Installing: ${packagesToInstall.join(', ')}...`, 'info', 15000);
                    await micropip.install(packagesToInstall);
                    uiStore.addNotification('Installation complete.', 'success');
                }
            }

            // 2. Load standard Pyodide packages from imports (e.g., numpy)
            await pyodide.value.loadPackagesFromImports(code);

            if (canvasSelector) {
                 pyodide.value.globals.set("pyodide_canvas_selector", canvasSelector);
            }

            // 3. Determine if the app is interactive (needs modal)
            const usesPygame = /import\s+pygame/.test(code);

            // 4. Run the code and get results
            let resultData;
            // The single wrapper is now used for everything EXCEPT pygame
            if (usesPygame) {
                await pyodide.value.runPythonAsync(code);
                // Assume Pygame doesn't create files in this simple model
                resultData = new Map([['image', null], ['new_files', []]]);
            } else {
                const wrappedCode = wrapCodeForExecution(code);
                const pyResult = await pyodide.value.runPythonAsync(wrappedCode);
                resultData = pyResult.toJs();
            }

            return { 
                output: stdout.value.trim(), 
                error: null, 
                image: resultData.get('image'), 
                usesCanvas: usesPygame,
                newFiles: resultData.get('new_files') || []
            };
        } catch (error) {
            console.error("Pyodide execution error:", error);
            const errorMessage = error.name === 'PythonError' && error.message.includes('SystemExit')
                ? 'Application quit by user.'
                : stdout.value.trim() || error.toString();
            return { output: null, error: errorMessage, image: null, usesCanvas: false, newFiles: [] };
        } finally {
            activeCanvasSelector.value = null;
        }
    }
    
    async function readFile(filename) {
        if (!pyodide.value) return null;
        try {
            return pyodide.value.FS.readFile(filename, { encoding: 'binary' });
        } catch (e) {
            console.error(`Failed to read file ${filename} from Pyodide VFS:`, e);
            return null;
        }
    }

    return {
        isLoading: readonly(isLoading),
        isReady: readonly(isReady),
        activeCanvasSelector: readonly(activeCanvasSelector),
        initialize,
        runCode,
        readFile,
    };
});