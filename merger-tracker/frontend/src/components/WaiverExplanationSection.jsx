import CollapsibleCard from './CollapsibleCard';

const ExplanationIcon = () => (
  <svg className="h-5 w-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
  </svg>
);

// Clean up PDF-extracted text by distinguishing layout line-breaks from real ones.
// Heuristics (in order of priority):
//   1. Hyphen before \n → word-wrap split, join directly (e.g. "post-\nacquisition")
//   2. \n followed by a list item pattern ([a-z].) → real paragraph break
//   3. \n preceded by . or ) and followed by an uppercase letter → real paragraph break
//   4. Everything else → layout break, join with a space
function cleanExplanation(text) {
  return text.replace(/\n/g, (_, offset, str) => {
    const before = str.slice(0, offset);
    const after = str.slice(offset + 1);
    const lastChar = before.slice(-1);

    if (lastChar === '-') return '';
    if (/^[a-z]\./.test(after)) return '\n\n';
    if ((lastChar === '.' || lastChar === ')') && /^[A-Z]/.test(after)) return '\n\n';
    return ' ';
  });
}

function WaiverExplanationSection({ events }) {
  const explanationDetails = (events || [])
    .flatMap(e => e.determination_table_content || [])
    .find(item => typeof item.item === 'string' && item.item.startsWith('Explanation for\ndetermination'))
    ?.details;

  if (!explanationDetails) return null;

  const paragraphs = cleanExplanation(explanationDetails)
    .split('\n\n')
    .map(p => p.trim())
    .filter(Boolean);

  return (
    <CollapsibleCard
      icon={<ExplanationIcon />}
      iconBgClass="bg-emerald-100"
      title="Explanation for Determination"
      subtitle="Click to view the ACCC's reasoning for this waiver decision"
    >
      <div className="mt-4 space-y-3">
        {paragraphs.map((para, idx) => (
          <p key={idx} className="text-sm text-gray-600 leading-relaxed">
            {para}
          </p>
        ))}
      </div>
    </CollapsibleCard>
  );
}

export default WaiverExplanationSection;
