// frontend/webui/src/assets/icons/icon-maps.js

// UI Icons
import IconAlign from './ui/IconAlign.vue';
import IconBlockquote from './ui/IconBlockquote.vue';
import IconBold from './ui/IconBold.vue';
import IconChrome from './ui/IconChrome.vue';
import IconCode from './ui/IconCode.vue';
import IconFileText from './ui/IconFileText.vue';
import IconGather from './ui/IconGather.vue';
import IconGitBranch from './ui/IconGitBranch.vue';
import IconHash from './ui/IconHash.vue';
import IconItalic from './ui/IconItalic.vue';
import IconLatex from './ui/IconLatex.vue';
import IconLatexblock from './ui/IconLatexblock.vue';
import IconLayout from './ui/IconLayout.vue';
import IconLink from './ui/IconLink.vue';
import IconList from './ui/IconList.vue';
import IconMinus from './ui/IconMinus.vue';
import IconOrderedList from './ui/IconOrderedList.vue';
import IconPaperclip from './ui/IconPaperclip.vue';
import IconProgramming from './ui/IconProgramming.vue';
import IconSigma from './ui/IconSigma.vue';
import IconStrikethrough from './ui/IconStrikethrough.vue';
import IconTerminal from './ui/IconTerminal.vue';
import IconType from './ui/IconType.vue';
import IconImage from '../icons/IconPhoto.vue'; // Alias for consistency

// Language Icons
import IconAngular from './languages/IconAngular.vue';
import IconBash from './languages/IconBash.vue';
import IconC from './languages/IconC.vue';
import IconGraphviz from './languages/IconGraphviz.vue';
import IconJava from './languages/IconJava.vue';
import IconJavascript from './languages/IconJavascript.vue';
import IconJson from './languages/IconJson.vue';
import IconKotlin from './languages/IconKotlin.vue';
import IconMarkdown from './languages/IconMarkdown.vue';
import IconMermaid from './languages/IconMermaid.vue';
import IconPerl from './languages/IconPerl.vue';
import IconPhp from './languages/IconPhp.vue';
import IconPowershell from './languages/IconPowershell.vue';
import IconPython from './languages/IconPython.vue';
import IconReact from './languages/IconReact.vue';
import IconRProject from './languages/IconRProject.vue';
import IconRuby from './languages/IconRuby.vue';
import IconSvg from './languages/IconSvg.vue';
import IconSwift from './languages/IconSwift.vue';
import IconTypescript from './languages/IconTypescript.vue';
import IconVuejs from './languages/IconVuejs.vue';
import IconXml from './languages/IconXml.vue';
import IconYaml from './languages/IconYaml.vue';

// Manually map names to imported components
export const uiIconMap = {
    'align': IconAlign,
    'blockquote': IconBlockquote,
    'bold': IconBold,
    'chrome': IconChrome,
    'code': IconCode,
    'file-text': IconFileText,
    'gather': IconGather,
    'git-branch': IconGitBranch,
    'hash': IconHash,
    'italic': IconItalic,
    'latex': IconLatex,
    'latexBlock': IconLatexblock,
    'layout': IconLayout,
    'link': IconLink,
    'list': IconList,
    'minus': IconMinus,
    'ordered-list': IconOrderedList,
    'paperclip': IconPaperclip,
    'programming': IconProgramming,
    'sigma': IconSigma,
    'strikethrough': IconStrikethrough,
    'terminal': IconTerminal,
    'type': IconType,
    'image': IconImage,
    // Add aliases for icons that might have different names in different places
    'equation': IconSigma, 
};

export const languageIconMap = {
    'angular': IconAngular,
    'bash': IconBash,
    'c': IconC,
    'cplusplus': IconC,
    'csharp': IconC,
    'graphviz': IconGraphviz,
    'java': IconJava,
    'javascript': IconJavascript,
    'json': IconJson,
    'kotlin': IconKotlin,
    'markdown': IconMarkdown,
    'mermaid': IconMermaid,
    'perl': IconPerl,
    'php': IconPhp,
    'powershell': IconPowershell,
    'python': IconPython,
    'react': IconReact,
    'r-project': IconRProject,
    'ruby': IconRuby,
    'svg': IconSvg,
    'swift': IconSwift,
    'typescript': IconTypescript,
    'vuejs': IconVuejs,
    'xml': IconXml,
    'yaml': IconYaml,
    'html5': IconCode, // Fallback for now
    'css3': IconCode, // Fallback for now
    'go': IconCode, // Fallback
    'rust': IconCode, // Fallback
};