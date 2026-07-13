import { useParams } from 'react-router-dom';

/**
 * Reads a route param and URI-decodes it, falling back to the raw value if
 * decoding fails (e.g. a malformed `%` sequence) rather than throwing.
 *
 * @param {string} name - param name, as passed to react-router's useParams
 * @returns {string} the decoded param value
 */
export function useDecodedParam(name) {
  const params = useParams();
  const raw = params[name];
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}
