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

export function parsedMarkdown(content) {
    if (typeof content !== 'string') return '';
    const protectedContent = protectMath(content);
    const rawHtml = marked.parse(protectedContent, { gfm: true, breaks: true, mangle: false, smartypants: false });
    return unprotectHtml(rawHtml);
};

export function getContentTokensWithMathProtection(text) {
    if (!text) return [];
    const protectedText = protectMath(text);
    const tokens = Array.from(marked.lexer(protectedText, { mangle: false, smartypants: false }));

    return tokens.map(token => {
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