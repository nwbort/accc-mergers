import CollapsibleCard from './CollapsibleCard';
import ExternalLinkIcon from './ExternalLinkIcon';

const ExplanationIcon = () => (
  <svg className="h-5 w-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
  </svg>
);

// Clean up PDF-extracted text by distinguishing layout line-breaks from real ones.
// Heuristics (in order of priority):
//   1. Hyphen before \n → word-wrap split, join directly (e.g. "post-\nacquisition")
//   2. \n followed by • or ▪ → real paragraph break (bullet list item)
//   3. \n followed by [a-z]. → real paragraph break (lettered list item)
//   4. \n preceded by . or ) and followed by uppercase → real paragraph break
//   5. Everything else → layout break, join with a space
function cleanExplanation(text) {
  return text.replace(/\n/g, (_, offset, str) => {
    const before = str.slice(0, offset);
    const after = str.slice(offset + 1);
    const lastChar = before.slice(-1);

    if (lastChar === '-') return '';
    if (after.startsWith('•') || after.startsWith('▪')) return '\n\n';
    if (/^[a-z]\./.test(after)) return '\n\n';
    if ((lastChar === '.' || lastChar === ')') && /^[A-Z]/.test(after)) return '\n\n';
    return ' ';
  });
}

// Group paragraphs into runs of plain text, bullet items (• or ▪), and lettered items (a. b. c.).
function groupSegments(paragraphs) {
  const segments = [];
  const isBullet = (p) => p.startsWith('•') || p.startsWith('▪');
  let i = 0;
  while (i < paragraphs.length) {
    const p = paragraphs[i];
    if (isBullet(p)) {
      const items = [];
      while (i < paragraphs.length && isBullet(paragraphs[i])) {
        items.push(paragraphs[i].replace(/^[•▪]\s*/, ''));
        i++;
      }
      segments.push({ type: 'bullets', items });
    } else if (/^[a-z]\.\s/.test(p)) {
      const items = [];
      while (i < paragraphs.length && /^[a-z]\.\s/.test(paragraphs[i])) {
        const match = paragraphs[i].match(/^([a-z]\.)\s*([\s\S]*)$/);
        items.push({ letter: match[1], text: match[2] });
        i++;
      }
      segments.push({ type: 'letters', items });
    } else {
      segments.push({ type: 'text', text: p });
      i++;
    }
  }
  return segments;
}

// Boilerplate paragraphs to skip — these appear verbatim in most determinations
// and don't add information for the reader.
const BOILERPLATE_PREFIXES = [
  'In making this notification waiver determination, the Australian Competition and Consumer Commission',
  'When making a determination in Phase 1, the Australian Competition',
  'For more information about the ACCC',
  'In conducting its competition assessment, the ACCC has considered the information and documents',
  'For the reasons given below, the ACCC has determined',
];

function isBoilerplate(p) {
  return BOILERPLATE_PREFIXES.some(prefix => p.startsWith(prefix));
}

function renderSegments(segments) {
  return segments.map((seg, idx) => {
    if (seg.type === 'bullets') {
      return (
        <ul key={idx} className="list-disc list-outside pl-5 space-y-1.5">
          {seg.items.map((item, j) => (
            <li key={j} className="text-sm text-gray-600 leading-relaxed">{item}</li>
          ))}
        </ul>
      );
    }
    if (seg.type === 'letters') {
      return (
        <ul key={idx} className="list-none space-y-1.5">
          {seg.items.map((item, j) => (
            <li key={j} className="flex gap-2 text-sm text-gray-600 leading-relaxed">
              <span className="flex-shrink-0 font-medium text-gray-700">{item.letter}</span>
              <span>{item.text}</span>
            </li>
          ))}
        </ul>
      );
    }
    return (
      <p key={idx} className="text-sm text-gray-600 leading-relaxed">{seg.text}</p>
    );
  });
}

// Render the structured "Statement of reasons" that detailed Phase 1
// determinations place after the table. Blocks come pre-classified from the
// Python parser as headings, paragraphs, bullet lists, or lettered lists.
function renderStatementOfReasons(blocks) {
  const filtered = blocks.filter(b => {
    if (b.type !== 'paragraph') return true;
    return !isBoilerplate((b.text || '').trim());
  });

  return filtered.map((b, idx) => {
    if (b.type === 'heading') {
      return (
        <h3 key={idx} className="text-sm font-semibold text-gray-900 mt-2">{b.text}</h3>
      );
    }
    if (b.type === 'paragraph') {
      return (
        <p key={idx} className="text-sm text-gray-600 leading-relaxed">
          {b.number && <span className="text-gray-400 mr-2">{b.number}</span>}
          {b.text}
        </p>
      );
    }
    if (b.type === 'bullet_list') {
      return (
        <ul key={idx} className="list-disc list-outside pl-5 space-y-1.5">
          {b.items.map((item, j) => (
            <li key={j} className="text-sm text-gray-600 leading-relaxed">{item}</li>
          ))}
        </ul>
      );
    }
    if (b.type === 'lettered_list') {
      return (
        <ul key={idx} className="list-none space-y-1.5">
          {b.items.map((item, j) => (
            <li key={j} className="flex gap-2 text-sm text-gray-600 leading-relaxed">
              <span className="flex-shrink-0 font-medium text-gray-700">({item.letter})</span>
              <span>{item.text}</span>
            </li>
          ))}
        </ul>
      );
    }
    return null;
  });
}

function findExplanationDetails(events) {
  for (const e of events) {
    for (const item of e.determination_table_content || []) {
      if (typeof item.item !== 'string') continue;
      const normalised = item.item.toLowerCase().replace(/\s+/g, ' ').trim();
      if (normalised.startsWith('explanation for determination') ||
          normalised.startsWith('reasons for determination')) {
        return item.details;
      }
    }
  }
  return null;
}

function findStatementOfReasons(events) {
  for (const e of events) {
    if (e.determination_statement_of_reasons && e.determination_statement_of_reasons.length) {
      return e.determination_statement_of_reasons;
    }
  }
  return null;
}

function DeterminationExplanationSection({ merger }) {
  const eventsArr = merger?.events || [];

  const statementBlocks = findStatementOfReasons(eventsArr);
  const inlineDetails = findExplanationDetails(eventsArr);

  // Detailed Phase 1 reasons (section 2) take precedence over the placeholder
  // "Reasons for determination" row that just points to section 2.
  const hasDetailed = !!statementBlocks;
  const hasInline = !!inlineDetails && !inlineDetails.toLowerCase().includes('set out in section');

  if (!hasDetailed && !hasInline) return null;

  const determinationEvent = eventsArr.find(e => e.is_determination_event && e.url_gh);
  const isWaiver = !!merger?.is_waiver;
  const title = isWaiver ? 'Explanation for Determination' : 'Reasons for Determination';
  const subtitle = isWaiver
    ? "Click to view the ACCC's reasoning for this waiver decision"
    : "Click to view the ACCC's reasoning for this determination";

  let content;
  if (hasDetailed) {
    content = (
      <div className="space-y-3">
        {renderStatementOfReasons(statementBlocks)}
      </div>
    );
  } else {
    const rawParagraphs = cleanExplanation(inlineDetails)
      .split('\n\n')
      .map(p => p.trim())
      .filter(p => p && !isBoilerplate(p));

    if (rawParagraphs.length > 0 && (rawParagraphs[0].startsWith('•') || rawParagraphs[0].startsWith('▪'))) {
      rawParagraphs[0] = rawParagraphs[0].replace(/^[•▪]\s*/, '');
    }

    const segments = groupSegments(rawParagraphs);
    content = <div className="space-y-3">{renderSegments(segments)}</div>;
  }

  return (
    <CollapsibleCard
      icon={<ExplanationIcon />}
      iconBgClass="bg-emerald-100"
      title={title}
      subtitle={subtitle}
    >
      <div className="mt-4">
        {determinationEvent && (
          <div className="mb-4">
            <a
              href={determinationEvent.url_gh}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-primary hover:text-primary-dark transition-colors font-medium"
            >
              View determination document
              <ExternalLinkIcon className="h-3 w-3" />
            </a>
          </div>
        )}
        {content}
      </div>
    </CollapsibleCard>
  );
}

export default DeterminationExplanationSection;
