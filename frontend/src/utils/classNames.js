/**
 * Shared Tailwind class strings used across multiple components.
 */

/** Prose styles for rendered markdown content (ReactMarkdown wrappers). */
export const PROSE_MARKDOWN = "text-gray-600 prose prose-sm max-w-none leading-relaxed [&>p]:mb-4 [&>ul]:mb-4 [&>ul]:list-disc [&>ul]:pl-5 [&>ul>li]:mb-2 [&>ol]:mb-4 [&>ol]:list-decimal [&>ol]:pl-5 [&>ol>li]:mb-2 [&_a]:underline";

/**
 * Base card container: a Material 3 card. White (surface-container-lowest) on
 * the tinted page, told apart by tone rather than by border or shadow, with
 * the Expressive scale's 24px corners.
 */
export const CARD = "bg-white rounded-2xl";

/**
 * Title of a content card on a detail page ("Acquirers", "Phase 1 duration",
 * "Sub-industries"): M3's title-medium. Darker and heavier than
 * SECTION_HEADING, which labels the fields and groups inside a card, so the
 * two don't read as one level.
 */
export const CARD_TITLE = "text-base font-semibold text-gray-900 tracking-tight";

/** Muted label heading: M3's label-medium. */
export const SECTION_HEADING = "text-xs font-semibold text-gray-500 tracking-wide";

/**
 * Buttons, as M3 Expressive's common buttons: full pills that square off a
 * little when pressed (`press-morph`). Filled for the main action, tonal for
 * a secondary one, text for the least.
 */
export const BUTTON_FILLED = "press-morph inline-flex items-center justify-center gap-2 rounded-full bg-primary text-white px-5 py-2.5 text-sm font-semibold hover:bg-primary-dark hover:shadow-card-hover disabled:opacity-50 disabled:cursor-not-allowed";
export const BUTTON_TONAL = "press-morph inline-flex items-center justify-center gap-2 rounded-full bg-secondary-container text-on-secondary-container px-5 py-2.5 text-sm font-semibold hover:shadow-card-hover disabled:opacity-50 disabled:cursor-not-allowed";
