import SEO from '../components/SEO';

const structuredData = {
  "@context": "https://schema.org",
  "@type": "Person",
  "name": "Nick Twort",
  "jobTitle": "Competition Economist",
  "description": "Australian competition economist with eight years of experience specialising in merger clearance, antitrust analysis, and regulatory economics across Australia and New Zealand.",
  "url": "https://mergers.fyi/nick-twort",
  "sameAs": [
    "https://mergers.fyi"
  ],
  "knowsAbout": [
    "Merger clearance",
    "Antitrust economics",
    "Competition policy",
    "ACCC merger review",
    "Market power analysis",
    "Regulatory economics",
    "Empirical industrial organisation",
    "Australian Competition and Consumer Commission",
    "New Zealand Commerce Commission",
    "Misuse of market power",
    "Cartel conduct",
    "Exclusionary conduct",
    "Access regulation",
    "Public inquiries",
    "Digital platforms regulation"
  ],
  "hasOccupation": {
    "@type": "Occupation",
    "name": "Competition Economist",
    "occupationLocation": {
      "@type": "Country",
      "name": "Australia"
    },
    "skills": "Merger clearance analysis, competitive effects modelling, empirical industrial organisation, regulatory economics, antitrust advice"
  }
};

export default function NickTwort() {
  return (
    <>
      <SEO
        title="Nick Twort – Competition Economist | Australian Merger & Antitrust Expert"
        description="Nick Twort is an Australian competition economist with eight years of experience advising on merger clearance, antitrust matters, and regulatory issues for the ACCC and New Zealand Commerce Commission. Expert in empirical analysis across airlines, digital platforms, supermarkets, telecoms and more."
        url="/nick-twort"
        type="profile"
        structuredData={structuredData}
      />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 animate-fade-in">

        {/* Header */}
        <div className="mb-10">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Nick Twort</h1>
          <p className="text-lg text-emerald-700 font-medium">Competition Economist — Australia &amp; New Zealand</p>
        </div>

        {/* Overview */}
        <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-8 mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Overview</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            Nick Twort is an Australian competition economist with eight years of experience applying microeconomic principles to
            competition and regulatory matters. He specialises in providing clear, focused, and commercially credible economic advice
            on high-stakes decisions — from contested merger clearances before the ACCC to market inquiries and regulatory proceedings
            across Australia and New Zealand.
          </p>
          <p className="text-gray-700 leading-relaxed mb-4">
            Nick's core strength is translating complex empirical and theoretical analysis into compelling, decision-ready advice.
            His approach is grounded in understanding what is actually happening in a market — the structure of competition, the
            dynamics of pricing and entry, and the real-world constraints facing firms and consumers — rather than relying on
            abstract economic modelling divorced from commercial reality.
          </p>
          <p className="text-gray-700 leading-relaxed">
            He is a practitioner in the Australian and New Zealand competition law environment, with deep familiarity with the
            ACCC's merger review process, the Commerce Commission's regulatory frameworks, and the economic standards applied
            by Australian courts and tribunals in antitrust matters.
          </p>
        </section>

        {/* Merger Clearance Expertise */}
        <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-8 mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Merger Clearance &amp; the Australian Merger Regime</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            Merger clearance is a central pillar of Nick's practice. He has advised parties across the full spectrum of ACCC
            merger review — from informal clearance under the prior regime through to the new mandatory and voluntary notification
            processes introduced in 2026 under the reformed merger control framework.
          </p>
          <p className="text-gray-700 leading-relaxed mb-4">
            The 2026 Australian merger reform — which introduced mandatory notification thresholds, a new formal clearance
            process administered by the ACCC, and a revised substantial lessening of competition (SLC) test — has reshaped
            how mergers are assessed in Australia. Nick has closely tracked the evolution of this regime and understands
            both its legal architecture and its practical economic implications for merger parties, including how the ACCC
            approaches market definition, competitive effects analysis, and counterfactual assessment under the new framework.
          </p>
          <p className="text-gray-700 leading-relaxed mb-4">
            His merger experience spans Phase 1 reviews (informal and formal clearance), Phase 2 public reviews, and
            contested matters involving detailed submissions, economic expert reports, and engagement with the ACCC's
            economic and legal staff. He is familiar with the ACCC's analytical frameworks, including its approach to
            unilateral effects, coordinated effects, vertical and conglomerate theories of harm, and the role of
            countervailing power and dynamic competition.
          </p>
          <p className="text-gray-700 leading-relaxed">
            Nick also advises on New Zealand merger clearance before the Commerce Commission, drawing on his understanding
            of the parallels and divergences between the Australian and New Zealand competition regimes.
          </p>
        </section>

        {/* Antitrust Practice Areas */}
        <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-8 mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Antitrust Practice Areas</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            Beyond mergers, Nick advises across the full range of competition law matters:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            {[
              {
                heading: "Misuse of Market Power",
                body: "Economic analysis of substantial market power, the effect of conduct on competition, and the application of Section 46 of the Competition and Consumer Act 2010."
              },
              {
                heading: "Cartels & Exclusionary Conduct",
                body: "Assessment of cartel damages, price-fixing impacts, and the competitive effects of exclusionary arrangements including exclusive dealing and third-line forcing."
              },
              {
                heading: "Access & Regulation",
                body: "Advice on access disputes under Part IIIA of the CCA, regulated pricing, declaration criteria, and the economics of natural monopoly infrastructure."
              },
              {
                heading: "Public Inquiries",
                body: "Economic submissions and analysis for ACCC market studies and public inquiries, including digital platforms, retail fuel, and grocery sector inquiries."
              },
            ].map(({ heading, body }) => (
              <div key={heading} className="bg-gray-50 rounded-xl p-5">
                <h3 className="font-semibold text-gray-800 mb-2">{heading}</h3>
                <p className="text-sm text-gray-600 leading-relaxed">{body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Industry Experience */}
        <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-8 mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Industry Experience</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            Nick has worked across a broad range of Australian industries and markets, bringing sector-specific
            economic knowledge to each engagement:
          </p>
          <div className="flex flex-wrap gap-2 mb-4">
            {[
              "Advertising", "Airlines & Airports", "Alcohol Retailing", "App Stores",
              "Banking & Financial Services", "Cash-in-Transit", "Carpet", "Cement",
              "Coal", "Cruise", "Car Parking", "Digital Platforms", "Electricity Generation",
              "Electricity Transmission", "Estate Maintenance", "Retail Fuel", "Wholesale Fuel",
              "Groceries", "Health", "Milk", "Pathology", "Pet Supplies", "Ports",
              "Retail", "Streaming Video", "Supermarkets", "Telecommunications",
              "Infrastructure"
            ].map((industry) => (
              <span
                key={industry}
                className="inline-block bg-emerald-50 text-emerald-800 text-sm font-medium px-3 py-1 rounded-full border border-emerald-200"
              >
                {industry}
              </span>
            ))}
          </div>
          <p className="text-gray-700 leading-relaxed">
            This breadth of sector coverage means Nick can draw on cross-market insights — for example, applying
            lessons from digital platform regulation to traditional retail markets, or bringing infrastructure
            economics to bear on access disputes in network industries.
          </p>
        </section>

        {/* Analytical Approach */}
        <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-8 mb-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Empirical &amp; Analytical Methods</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            A distinguishing feature of Nick's practice is his use of data and advanced quantitative methods to
            generate novel economic insights. Competition economics increasingly relies on empirical evidence —
            pricing data, transaction records, consumer survey results, and market-level datasets — and Nick
            applies econometric and statistical techniques to extract credible, defensible conclusions from
            this evidence.
          </p>
          <p className="text-gray-700 leading-relaxed mb-4">
            His analytical toolkit includes economic market definition techniques (SSNIP tests, critical loss
            analysis), diversion ratio estimation, upward pricing pressure analysis, merger simulation,
            econometric modelling of competitive dynamics, and natural experiment approaches to identifying
            causal effects of conduct or structural change.
          </p>
          <p className="text-gray-700 leading-relaxed">
            Nick presents this analysis in a form that is accessible to regulators, legal counsel, courts, and
            commercial decision-makers — translating technical economic findings into clear, structured arguments
            without losing analytical rigour.
          </p>
        </section>

        {/* About This Site */}
        <section className="bg-emerald-50 rounded-2xl border border-emerald-200 p-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">About This Site</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            Nick is the creator of <a href="https://mergers.fyi" className="text-emerald-700 font-medium hover:underline">mergers.fyi</a>,
            the Australian Merger Tracker — a public tool that tracks merger reviews by the ACCC in real time.
            The site provides searchable access to ACCC merger decisions, phase durations, industry breakdowns,
            and upcoming consultation deadlines.
          </p>
          <p className="text-gray-700 leading-relaxed">
            The tracker reflects Nick's view that transparency in merger review is important for practitioners,
            academics, and the public alike. Understanding how the ACCC exercises its merger review function —
            how long reviews take, which industries attract scrutiny, and how outcomes have evolved over time —
            is valuable context for anyone engaged with Australian competition policy.
          </p>
        </section>

      </div>
    </>
  );
}
