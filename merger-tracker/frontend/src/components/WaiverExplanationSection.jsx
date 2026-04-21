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
//   2. \n followed by • → real paragraph break (bullet list item)
//   3. \n followed by [a-z]. → real paragraph break (lettered list item)
//   4. \n preceded by . or ) and followed by uppercase → real paragraph break
//   5. Everything else → layout break, join with a space
function cleanExplanation(text) {
  return text.replace(/\n/g, (_, offset, str) => {
    const before = str.slice(0, offset);
    const after = str.slice(offset + 1);
    const lastChar = before.slice(-1);

    if (lastChar === '-') return '';
    if (after.startsWith('•')) return '\n\n';
    if (/^[a-z]\./.test(after)) return '\n\n';
    if ((lastChar === '.' || lastChar === ')') && /^[A-Z]/.test(after)) return '\n\n';
    return ' ';
  });
}

// Group paragraphs into runs of plain text, bullet items (•), and lettered items (a. b. c.).
function groupSegments(paragraphs) {
  const segments = [];
  let i = 0;
  while (i < paragraphs.length) {
    const p = paragraphs[i];
    if (p.startsWith('•')) {
      const items = [];
      while (i < paragraphs.length && paragraphs[i].startsWith('•')) {
        items.push(paragraphs[i].replace(/^•\s*/, ''));
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

function WaiverExplanationSection({ events }) {
  const eventsArr = events || [];

  const explanationDetails = eventsArr
    .flatMap(e => e.determination_table_content || [])
    .find(item => typeof item.item === 'string' && item.item.startsWith('Explanation for\ndetermination'))
    ?.details;

  if (!explanationDetails) return null;

  const determinationEvent = eventsArr.find(e => e.is_determination_event && e.url_gh);

  const paragraphs = cleanExplanation(explanationDetails)
    .split('\n\n')
    .map(p => p.trim())
    .filter(Boolean);

  const segments = groupSegments(paragraphs);

  return (
    <CollapsibleCard
      icon={<ExplanationIcon />}
      iconBgClass="bg-emerald-100"
      title="Explanation for Determination"
      subtitle="Click to view the ACCC's reasoning for this waiver decision"
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
        <div className="space-y-3">
          {segments.map((seg, idx) => {
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
          })}
        </div>
      </div>
    </CollapsibleCard>
  );
}

export default WaiverExplanationSection;
