/**
 * Shared Tailwind class strings used across multiple components.
 */

/** Prose styles for rendered markdown content (ReactMarkdown wrappers). */
export const PROSE_MARKDOWN = "text-gray-600 prose prose-sm max-w-none leading-relaxed [&>p]:mb-4 [&>ul]:mb-4 [&>ul]:list-disc [&>ul]:pl-5 [&>ul>li]:mb-2 [&>ol]:mb-4 [&>ol]:list-decimal [&>ol]:pl-5 [&>ol>li]:mb-2 [&_a]:underline";

/** Base card container: white background, rounded corners, subtle border and shadow. */
export const CARD = "bg-white rounded-2xl border border-gray-100 shadow-card";

/**
 * Title of a content card on a detail page ("Acquirers", "Phase 1 duration",
 * "Sub-industries"). Darker and heavier than SECTION_HEADING, which labels
 * the fields and groups inside a card, so the two don't read as one level.
 */
export const CARD_TITLE = "text-sm font-semibold text-gray-900 uppercase tracking-wider";

/** Uppercase, muted section heading label. */
export const SECTION_HEADING = "text-xs font-medium text-gray-500 uppercase tracking-wider";
