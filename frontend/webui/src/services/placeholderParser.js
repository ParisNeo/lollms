// frontend/webui/src/services/placeholderParser.js
/**
 * Parses a string for advanced placeholders and extracts their metadata.
 * Syntax: @<name>@ title: ... type: ... options: ... default: ... help: ... @</name>@
 * The inner content is optional. Simple syntax is just @<name>@.
 *
 * @param {string} template - The string containing placeholders.
 * @returns {Array<Object>} An array of placeholder objects.
 */
export function parsePlaceholders(template) {
    if (!template) return [];

    const placeholders = new Map();
    const regex = /@<([^>]+?)>@([\s\S]*?)@<\/\1>@|@<([^>]+?)>@/g;
    let match;

    while ((match = regex.exec(template)) !== null) {
        const name = match[1] || match[3];
        const attributesString = match[2] || '';

        if (!placeholders.has(name)) {
            const attributes = {
                name: name,
                title: name,
                type: 'str',
                options: [],
                default: '',
                help: '',
            };

            if (attributesString.trim()) {
                const lines = attributesString.trim().split('\n');
                lines.forEach(line => {
                    const [key, ...valueParts] = line.split(':');
                    const value = valueParts.join(':').trim();
                    if (key && value) {
                        const attrKey = key.trim().toLowerCase();
                        if (Object.prototype.hasOwnProperty.call(attributes, attrKey)) {
                            if (attrKey === 'options') {
                                // Filter out empty strings from options list
                                attributes.options = value.split(',').map(opt => opt.trim()).filter(Boolean);
                            } else {
                                attributes[attrKey] = value;
                            }
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

    return Array.from(placeholders.values());
}

export default {
    parse: parsePlaceholders
};