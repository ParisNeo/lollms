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

export function parsedMarkdown(content) {
    if (typeof content !== 'string') return '';
    const protectedContent = protectMath(content);
    // Use marked with our custom extension
    const rawHtml = marked.parse(protectedContent, { gfm: true, breaks: true, mangle: false, smartypants: false });
    return unprotectHtml(rawHtml);
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
