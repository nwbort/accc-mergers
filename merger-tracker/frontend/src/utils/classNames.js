/**
 * Shared Tailwind class strings used across multiple components.
 *
 * These centralise the light + dark variants for the app's recurring idioms so
 * dark mode stays consistent and we don't repeat long class strings. See
 * src/context/ThemeContext.jsx for how the `dark` class gets toggled.
 */

/** Prose styles for rendered markdown content (ReactMarkdown wrappers). */
export const PROSE_MARKDOWN = "text-gray-600 dark:text-gray-300 prose prose-sm max-w-none leading-relaxed [&>p]:mb-4 [&>ul]:mb-4 [&>ul]:list-disc [&>ul]:pl-5 [&>ul>li]:mb-2 [&>ol]:mb-4 [&>ol]:list-decimal [&>ol]:pl-5 [&>ol>li]:mb-2 [&_a]:underline";

/**
 * The dominant "surface card" idiom: a white panel with a soft border and card
 * shadow. Use in place of repeating `bg-white ... border border-gray-100
 * shadow-card` so the dark variant lives in one place. Compose with rounding
 * and padding at the call site, e.g. `${SURFACE_CARD} rounded-2xl p-6`.
 */
export const SURFACE_CARD = "bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 shadow-card";
