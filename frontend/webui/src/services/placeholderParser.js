// frontend/webui/src/services/placeholderParser.js
/**
 * Parses a string for advanced and standard placeholders and extracts their metadata.
 * Syntax 1: @<name>@ title: ... type: ... options: ... default: ... help: ... @</name>@
 * Syntax 2: @<name>@
 * Syntax 3: {{name}} or {{ name }} (excluding reserved system dynamic context tags)
 *
 * @param {string} template - The string containing placeholders.
 * @returns {Array<Object>} An array of placeholder objects.
 */
export function parsePlaceholders(template) {
    if (!template || typeof template !== 'string') return [];

    const placeholders = new Map();
    const systemTags = new Set(['date', 'time', 'datetime', 'user_name', 'username']);

    // 1. Match @<name>@ advanced definition blocks and simple @<name>@ placeholders
    const atRegex = /@<([^>]+?)>@([\s\S]*?)@<\/\1>@|@<([^>]+?)>@/g;
    let match;

    while ((match = atRegex.exec(template)) !== null) {
        const name = (match[1] || match[3] || '').trim();
        const attributesString = match[2];

        if (name && !placeholders.has(name)) {
            const attributes = {
                name: name,
                title: name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                type: 'str',
                options: [],
                default: '',
                help: '',
            };

            if (attributesString && attributesString.trim()) {
                const lines = attributesString.trim().split('\n');
                lines.forEach(line => {
                    const separatorIndex = line.indexOf(':');
                    if (separatorIndex === -1) return;

                    const key = line.substring(0, separatorIndex).trim().toLowerCase();
                    const value = line.substring(separatorIndex + 1).trim();

                    if (key && value !== '' && Object.prototype.hasOwnProperty.call(attributes, key)) {
                        if (key === 'options') {
                            attributes.options = value.split(',').map(opt => opt.trim()).filter(Boolean);
                        } else {
                            attributes[key] = value;
                        }
                    }
                });
            }
            
            if (!['str', 'text', 'int', 'float', 'bool'].includes(attributes.type)) {
                attributes.type = 'str';
            }

            placeholders.set(name, attributes);
        }
    }

    // 2. Match {{variable}} syntax (excluding dynamic context keywords)
    const curlyRegex = /\{\{\s*([a-zA-Z0-9_-]+)\s*\}\}/g;
    let curlyMatch;

    while ((curlyMatch = curlyRegex.exec(template)) !== null) {
        const name = curlyMatch[1].trim();
        if (name && !systemTags.has(name.toLowerCase()) && !placeholders.has(name)) {
            placeholders.set(name, {
                name: name,
                title: name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                type: 'str',
                options: [],
                default: '',
                help: `Value for ${name}`
            });
        }
    }

    return Array.from(placeholders.values());
}

/**
 * Cleans a template string by removing advanced placeholder definition blocks.
 *
 * @param {string} template - The template string to clean.
 * @returns {string} The cleaned template string.
 */
export function cleanTemplate(template) {
    if (!template || typeof template !== 'string') return '';

    // Remove @<name>@...definitions...@</name>@ blocks
    const regex = /@<([^>]+?)>@[\s\S]*?@<\/\1>@/g;
    const withoutDefinitions = template.replace(regex, '');

    return withoutDefinitions.trim();
}

export default {
    parse: parsePlaceholders,
    clean: cleanTemplate,
};