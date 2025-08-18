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
    // This regex finds both advanced placeholders with definitions and simple placeholders.
    const regex = /@<([^>]+?)>@([\s\S]*?)@<\/\1>@|@<([^>]+?)>@/g;
    let match;

    while ((match = regex.exec(template)) !== null) {
        // match[1] is the name from an advanced placeholder, match[3] is from a simple one.
        const name = match[1] || match[3];
        const attributesString = match[2]; // This is undefined for simple placeholders

        if (!placeholders.has(name)) {
            const attributes = {
                name: name,
                title: name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()), // Prettify title
                type: 'str',
                options: [],
                default: '',
                help: '',
            };

            // If attributesString is not undefined, it's an advanced placeholder with definitions.
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

    return Array.from(placeholders.values());
}

/**
 * Cleans a template string by removing advanced placeholder definition blocks,
 * and then trims any leading whitespace or newlines that might be left over
 * from those blocks being at the start of the file.
 *
 * @param {string} template - The template string to clean.
 * @returns {string} The cleaned template string.
 */
export function cleanTemplate(template) {
    if (!template) return '';

    // This regex finds and removes the entire advanced placeholder block.
    // e.g., @<name>@...content...@</name>@ becomes an empty string.
    const regex = /@<([^>]+?)>@[\s\S]*?@<\/\1>@/g;
    
    const withoutDefinitions = template.replace(regex, '');

    // The user instruction "start from the first line that is not empty..."
    // suggests that the definitions are expected to be in a preamble.
    // After removing them, we might have leading whitespace.
    const lines = withoutDefinitions.split('\n');
    let firstContentLineIndex = -1;

    for (let i = 0; i < lines.length; i++) {
        if (lines[i].trim() !== '') {
            firstContentLineIndex = i;
            break;
        }
    }

    if (firstContentLineIndex !== -1) {
        return lines.slice(firstContentLineIndex).join('\n');
    }

    return ''; // Return empty if template was only definitions and whitespace
}


export default {
    parse: parsePlaceholders,
    clean: cleanTemplate,
};