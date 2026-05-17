import { marked } from 'marked';

const mathPlaceholders = new Map();
let mathCounter = 0;

function protectMath(text) {
    if (!text) return text;
    mathCounter = 0;
    mathPlaceholders.clear();

    return text.replace(/(\$\$[\s\S]*?\$\$|\$[\s\S]*?\$)/g, (match) => {
        const placeholder = `<!--MATH_PLACEHOLDER_${mathCounter}-->`;
        mathPlaceholders.set(placeholder, match);
        mathCounter++;
        return placeholder;
    });
}

function unprotectHtml(html) {
    if (!html || mathPlaceholders.size === 0) return html;
    let result = html;
    for (const [placeholder, original] of mathPlaceholders.entries()) {
        const regex = new RegExp(placeholder.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&'), 'g');
        result = result.replace(regex, original);
    }
    return result;
}

// Custom extension to handle [N] citations
const citationExtension = {
  name: 'citation',
  level: 'inline',
  start(src) { return src.match(/\[\d+\]/)?.index; },
  tokenizer(src, tokens) {
    const rule = /^\[(\d+)\]/;
    const match = rule.exec(src);
    if (match) {
      return {
        type: 'citation',
        raw: match[0],
        index: match[1]
      };
    }
  },
  renderer(token) {
    return `<button class="citation-btn text-blue-500 hover:underline font-mono text-xs align-super cursor-pointer select-none px-0.5 rounded hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors" data-index="${token.index}">[${token.index}]</button>`;
  }
};

marked.use({ extensions: [citationExtension] });

/**
 * Aggressively strips or escapes tags that can break the host UI
 * when rendered via v-html.
 */
/**
 * Detects "Naked Code" - raw HTML/Code blocks not wrapped in backticks
 * and wraps them to prevent them from executing in the main UI.
 */
function wrapNakedCode(text) {
    if (!text) return text;
    
    // If text looks like a full HTML file but has no markdown fences
    if ((text.includes('<!DOCTYPE') || text.includes('<html')) && !text.includes('```')) {
        return "```html\n" + text + "\n```";
    }
    
    // If text starts with many imports or definitions (Python/JS) but no fences
    const codeStartRegex = /^(import\s|from\s|const\s|function\s|def\s|class\s)/;
    if (codeStartRegex.test(text.trim()) && !text.includes('```')) {
        return "```\n" + text + "\n```";
    }
    
    return text;
}

/**
 * Ensures markdown tables have proper spacing before and after to be recognized by the parser.
 */
function normalizeTables(text) {
    if (!text || typeof text !== 'string') return text;
    const tableSeparatorRegex = /^(\|?\s*:?-+:?\s*\|?)+$/gm;
    if (!tableSeparatorRegex.test(text)) return text;

    const lines = text.split('\n');
    const result = [];
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.match(tableSeparatorRegex)) {
            if (i > 0 && lines[i-1].includes('|')) {
                if (i > 1 && lines[i-2].trim() !== '' && !lines[i-2].includes('|')) {
                    result.splice(result.length - 1, 0, '');
                }
            }
        }
        result.push(line);
    }
    return result.join('\n');
}

function sanitizeDangerousTags(html) {
    if (!html) return html;

    // Check if we are inside a widget context (handled by MessageContentRenderer)
    // If not specifically flagged, we continue stripping.

    // 1. Aggressively strip style and script blocks, even if unclosed (prevents global CSS leaks)
    // Note: lollms_inline contents are extracted RAW in the renderer to bypass this.
    let clean = html.replace(/<style[\s\S]*?(?:<\/style>|$)/gi, '');
    clean = clean.replace(/<script[\s\S]*?(?:<\/script>|$)/gi, '');
    
    // 2. Strip link tags (prevents external CSS loading)
    clean = clean.replace(/<link[^>]*?(?:>|$)/gi, '');

    // 3. Neutralize inline style attributes on ANY tag (prevents layout shifting)
    clean = clean.replace(/\sstyle\s*=\s*["'][^"']*["']/gi, '');
    
    // 4. Neutralize event handlers (onclick, etc)
    clean = clean.replace(/\son\w+\s*=\s*["'][^"']*["']/gi, '');

    return clean;
}

export function parsedMarkdown(content) {
    if (!content) return '';
    
    // [FIX] Auto-fence detection for pure Mermaid diagrams
    const trimmed = content.trim();
    if (trimmed.startsWith('graph ') || trimmed.startsWith('flowchart ') || trimmed.startsWith('sequenceDiagram') || trimmed.startsWith('classDiagram')) {
        if (!trimmed.startsWith('```')) {
            content = `\`\`\`mermaid\n${trimmed}\n\`\`\``;
        }
    }
  
    if (typeof content !== 'string') return '';
    
    const wrappedContent = wrapNakedCode(content);
    
    // Safety guard for pre-processing
    let normalizedContent = wrappedContent;
    try {
        normalizedContent = normalizeTables(wrappedContent);
    } catch (e) {
        console.warn("Markdown pre-processing (tables) failed:", e);
    }

    const protectedContent = protectMath(normalizedContent);
    
    // Use marked with our custom extension
    const rawHtml = marked.parse(protectedContent, { 
        gfm: true, 
        breaks: true, 
        mangle: false, 
        headerIds: false,
        smartypants: false 
    });
    
    // Once and for all: Isolated the output from the host UI
    return sanitizeDangerousTags(unprotectHtml(rawHtml));
};

// New helper function to tokenize non-code parts
function tokenizeMarkdownPart(markdown) {
    if (!markdown.trim()) {
        return [{ type: 'space', raw: markdown }];
    }
    const protectedText = protectMath(markdown);
    const markedTokens = Array.from(marked.lexer(protectedText, { mangle: false, smartypants: false }));

    return markedTokens.map(token => {
        const unprotectedToken = { ...token };
        if (unprotectedToken.raw) {
            unprotectedToken.raw = unprotectHtml(unprotectedToken.raw);
        }
        if (unprotectedToken.text) { 
            unprotectedToken.text = unprotectHtml(unprotectedToken.text);
        }
        return unprotectedToken;
    });
}


// New custom tokenizer that robustly separates code blocks
function customTokenizer(text) {
    if (!text) return [];

    // This regex splits the text by code blocks, capturing the blocks themselves.
    // It now handles optional leading whitespace (^\s*) on the lines with the fences.
    const codeBlockRegex = /(^\s*```[\s\S]*?^\s*```\s*?$)/gm;
    const parts = text.split(codeBlockRegex);

    const tokens = [];

    for (let i = 0; i < parts.length; i++) {
        const part = parts[i];
        if (!part) continue;

        if (i % 2 === 1) { // This part is a captured code block
            const codeBlockMatch = part.match(/^\s*```(\w*)\r?\n([\s\S]*?)\r?\n?^\s*```\s*?$/m);
            if (codeBlockMatch) {
                tokens.push({
                    type: 'code',
                    lang: codeBlockMatch[1] || 'plaintext',
                    text: codeBlockMatch[2],
                    raw: part
                });
            } else {
                // If regex fails (e.g., malformed block), treat it as plain text.
                tokens.push(...tokenizeMarkdownPart(part));
            }
        } else { // This part is the text between code blocks
            tokens.push(...tokenizeMarkdownPart(part));
        }
    }
    return tokens;
}

export function getContentTokensWithMathProtection(text) {
    return customTokenizer(text);
}

