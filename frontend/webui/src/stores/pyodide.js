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

    async function installPackages(packages) {
        if (!isReady.value || !packages || packages.length === 0) {
            return false;
        }

        const uiStore = useUiStore();
        uiStore.addNotification('Loading installer...', 'info', 3000);
        try {
            await pyodide.value.loadPackage('micropip');
            const micropip = pyodide.value.pyimport('micropip');
            
            uiStore.addNotification(`Installing: ${packages.join(', ')}...`, 'info', 15000);
            await micropip.install(packages);
            uiStore.addNotification('Installation complete.', 'success');
            return true;
        } catch (error) {
            console.error("Micropip installation error:", error);
            
            let userMessage = `Failed to install packages.`;
            const errorString = error.message || '';

            if (errorString.includes("Unsupported content type")) {
                userMessage = "Installation failed: A package was not found on PyPI. Some packages require a direct URL to a wheel (.whl) file.";
            } else if (errorString.includes("Can't find a pure Python 3 wheel")) {
                userMessage = "An install failed: A required package may not be compatible with the browser environment (it's not a 'pure Python wheel').";
            } else if (errorString.includes('ValueError:')) {
                userMessage = `Installation error: ${errorString.split('ValueError: ')[1]}`;
            } else {
                 userMessage = `Installation error: ${errorString}`;
            }

            uiStore.addNotification(userMessage, 'error', 15000);
            return false;
        }
    }

    function createSyncWrapper(code) {
        const escapedCode = code.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
        return `
import io
import base64
import os
import sys

# Setup environment for non-interactive execution
try:
    import matplotlib
    matplotlib.use('Agg')
except ImportError:
    pass

initial_files = set(os.listdir('.'))

# --- Execute user code ---
exec("""${escapedCode}""")
# --- End user code ---

# --- Capture results ---
result = {'image': None, 'new_files': []}
final_files = set(os.listdir('.'))
new_files_list = list(final_files - initial_files)
result['new_files'] = [f for f in new_files_list if f not in ['.matplotlib', '.config']]

try:
    import matplotlib.pyplot as plt
    if 'matplotlib.pyplot' in sys.modules and plt.get_fignums():
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        result['image'] = base64.b64encode(buf.read()).decode('utf-8')
        plt.close('all')
except (ImportError, Exception):
    pass

result
`;
    }

    async function runCode(code, { canvasSelector = null, files = [] } = {}) {
        const uiStore = useUiStore();
        if (!isReady.value) {
            return { output: null, error: "Pyodide not initialized.", image: null, usesCanvas: false, newFiles: [] };
        }
        
        stdout.value = '';
        activeCanvasSelector.value = canvasSelector;

        try {
            // --- FEATURE: Write uploaded files to the VFS before execution ---
            if (files && files.length > 0) {
                uiStore.addNotification(`Loading ${files.length} file(s)...`, 'info');
                for (const file of files) {
                    const buffer = await file.arrayBuffer();
                    pyodide.value.FS.writeFile(file.name, new Uint8Array(buffer));
                }
                uiStore.addNotification('Files loaded into environment.', 'success');
            }

            const micropipMatch = code.match(/^#\s*micropip:\s*install\s+(.+)$/m);
            if (micropipMatch) {
                const packagesToInstall = micropipMatch[1].split(/\s+/).filter(p => p);
                if (packagesToInstall.length > 0) {
                    await installPackages(packagesToInstall);
                }
            }

            await pyodide.value.loadPackagesFromImports(code);

            if (canvasSelector) {
                 pyodide.value.globals.set("pyodide_canvas_selector", canvasSelector);
            }

            const usesCanvas = /#\s*pyodide:\s*uses-canvas/.test(code);
            const isAsyncScript = /import\s+asyncio/.test(code) && /async\s+def\s+main/.test(code);

            if (isAsyncScript) {
                await pyodide.value.runPythonAsync(code);
                return { output: stdout.value.trim(), error: null, image: null, usesCanvas: usesCanvas, newFiles: [] };
            } else {
                const wrappedCode = createSyncWrapper(code);
                const pyResult = await pyodide.value.runPythonAsync(wrappedCode);
                const resultData = pyResult ? pyResult.toJs() : new Map();
                return { 
                    output: stdout.value.trim(), 
                    error: null, 
                    image: resultData.get('image'), 
                    usesCanvas: usesCanvas,
                    newFiles: resultData.get('new_files') || []
                };
            }
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
        installPackages,
    };
});