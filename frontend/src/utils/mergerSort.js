/**
 * Sort order for the merger list.
 *
 * A sort value is `{field}-{asc|desc}` and lives in the `?sort=` search param,
 * so it has to survive being typed, shared and bookmarked — `normaliseSort`
 * folds anything unrecognised back to the default rather than leaving the
 * controls describing an order that isn't applied.
 */

export const DEFAULT_SORT = 'notification-desc';

// Each field carries the direction it should start in when selected — a date
// reads newest-first, a name reads A to Z — plus the wording for each
// direction, since "ascending" means something different to dates and names.
export const SORT_FIELDS = [
  { value: 'notification', label: 'Notification date', defaultDir: 'desc', asc: 'Oldest first', desc: 'Newest first' },
  { value: 'determination', label: 'Determination date', defaultDir: 'desc', asc: 'Oldest first', desc: 'Newest first' },
  { value: 'name', label: 'Merger name', defaultDir: 'asc', asc: 'A to Z', desc: 'Z to A' },
];

export const SORT_FIELDS_BY_VALUE = Object.fromEntries(SORT_FIELDS.map((f) => [f.value, f]));

const sortFieldOf = (sortBy) => sortBy.replace(/-(?:asc|desc)$/, '');

/** Fold a `?sort=` value that names no field we have back to the default. */
export const normaliseSort = (sortBy) => (
  SORT_FIELDS_BY_VALUE[sortFieldOf(sortBy || '')] ? sortBy : DEFAULT_SORT
);

/** Split a (normalised) sort value into its field and direction. */
export const splitSort = (sortBy) => ({
  field: sortFieldOf(sortBy),
  dir: sortBy.endsWith('-asc') ? 'asc' : 'desc',
});

// One shared collator: sorting the whole list calls this thousands of times,
// and constructing a collator per comparison is far slower than localeCompare.
const nameCollator = new Intl.Collator(undefined, { sensitivity: 'base', numeric: true });

export const sortMergers = (list, sortBy = DEFAULT_SORT) => {
  return [...list].sort((a, b) => {
    switch (sortBy) {
      case 'notification-asc': {
        const dateA = a.effective_notification_datetime || '';
        const dateB = b.effective_notification_datetime || '';
        return dateA.localeCompare(dateB);
      }
      case 'name-asc':
        return nameCollator.compare(a.merger_name || '', b.merger_name || '');
      case 'name-desc':
        return nameCollator.compare(b.merger_name || '', a.merger_name || '');
      case 'determination-desc': {
        const dateA = a.determination_publication_date;
        const dateB = b.determination_publication_date;
        if (!dateA && !dateB) return 0;
        if (!dateA) return 1;
        if (!dateB) return -1;
        return dateB.localeCompare(dateA);
      }
      case 'determination-asc': {
        const dateA = a.determination_publication_date;
        const dateB = b.determination_publication_date;
        if (!dateA && !dateB) return 0;
        if (!dateA) return 1;
        if (!dateB) return -1;
        return dateA.localeCompare(dateB);
      }
      case 'notification-desc':
      default: {
        const dateA = a.effective_notification_datetime || '';
        const dateB = b.effective_notification_datetime || '';
        return dateB.localeCompare(dateA);
      }
    }
  });
};
