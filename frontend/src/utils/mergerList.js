/**
 * The lightweight list of every merger (`mergers/list.json`), shared by the
 * /mergers page and the command palette.
 *
 * Both cache the file's whole payload, `{ mergers }`, under this key — the
 * page through useFetchData, which also enrols it in background refresh — so
 * whichever loads first serves the other.
 */
export const MERGERS_LIST_KEY = 'mergers-list';
