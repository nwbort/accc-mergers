import SEO from '../components/SEO';

export default function PrivacyPolicy() {
  return (
    <>
      <SEO
        title="Privacy policy"
        description="How mergers.fyi collects, uses, and protects your personal information."
        url="/privacy"
      />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 animate-fade-in">

        {/* Header */}
        <div className="mb-10">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Privacy Policy</h1>
          <p className="text-sm text-gray-500">Last updated: 13 April 2026</p>
        </div>

        {/* 1. Introduction */}
        <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-8 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">1. Introduction</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            Welcome to mergers.fyi (&#34;we&#34;, &#34;us&#34;, &#34;our&#34;). We are committed to protecting your privacy and
            handling your personal information in a transparent and secure manner.
          </p>
          <p className="text-gray-700 leading-relaxed">
            This Privacy Policy explains how we collect, use, and store your information when you use our website.
          </p>
        </section>

        {/* 2. Information We Collect */}
        <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-8 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">2. Information We Collect</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            We collect only the minimum personal information necessary to provide our services.
          </p>
          <p className="text-gray-700 leading-relaxed mb-3">Information you provide:</p>
          <ul className="list-disc list-inside text-gray-700 space-y-1 mb-4">
            <li>email address</span> - when you sign up to receive our weekly email digest.</li>
          </ul>
          <p className="text-gray-700 leading-relaxed mt-4">
            We do not collect any other personal information.
          </p>
        </section>

        {/* 3. How We Use Your Information */}
        <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-8 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">3. How We Use Your Information</h2>
          <p className="text-gray-700 leading-relaxed mb-3">We use your email address solely to:</p>
          <ul className="list-disc list-inside text-gray-700 space-y-1 mb-4">
            <li>send you the mergers.fyi weekly digest; and</li>
            <li>manage and maintain our email subscriber list.</li>
          </ul>
          <p className="text-gray-700 leading-relaxed mb-3">We do not use your information for:</p>
          <ul className="list-disc list-inside text-gray-700 space-y-1">
            <li>marketing unrelated products or services</li>
            <li>selling or renting your data to third parties</li>
          </ul>
        </section>

        {/* 4. Email Delivery and Third-Party Services */}
        <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-8 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">4. Email Delivery and Third-Party Services</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            We use Resend to store email addresses and deliver our email digest.
          </p>
          <p className="text-gray-700 leading-relaxed mb-3">This means:</p>
          <ul className="list-disc list-inside text-gray-700 space-y-1 mb-4">
            <li>your email address is securely stored by Resend on our behalf; and</li>
            <li>Resend processes your data only to send emails for us.</li>
          </ul>
        </section>

        {/* 5. Data Storage and Security */}
        <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-8 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">5. Data Storage and Security</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            We take reasonable steps to protect your information from misuse, loss, or unauthorised access.
          </p>
          <p className="text-gray-700 leading-relaxed">
            Your email address is stored securely through our email service provider (Resend), which implements
            its own security measures.
          </p>
        </section>

        {/* 6. Unsubscribing */}
        <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-8 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">6. Unsubscribing</h2>
          <p className="text-gray-700 leading-relaxed mb-3">You can unsubscribe at any time by:</p>
          <ul className="list-disc list-inside text-gray-700 space-y-1 mb-4">
            <li>Clicking the &#34;unsubscribe&#34; link in any email we send</li>
          </ul>
          <p className="text-gray-700 leading-relaxed">
            Once you unsubscribe, your email address will be removed from our mailing list.
          </p>
        </section>

        {/* 7. Cookies and Analytics */}
        <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-8 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">7. Cookies and Analytics</h2>
          <p className="text-gray-700 leading-relaxed">
            We do not use cookies to track individual users. The only data stored locally in your browser
            is used to remember the specific mergers you have chosen to follow. We do not collect or
            transmit the list of mergers you have selected to track.
          </p>
        </section>

        {/* 8. Access and Correction */}
        <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-8 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">8. Access and Correction</h2>
          <p className="text-gray-700 leading-relaxed">
            If you would like to access, update, or delete your email address, you can contact us at{' '}
            <a
              href="mailto:help@mergers.fyi"
              className="text-primary hover:text-primary-dark font-medium hover:underline transition-colors"
            >
              help@mergers.fyi
            </a>
            .
          </p>
        </section>

        {/* 9. Changes to This Policy */}
        <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-8 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">9. Changes to This Policy</h2>
          <p className="text-gray-700 leading-relaxed">
            We may update this Privacy Policy from time to time. Any changes will be posted on this page
            with an updated effective date.
          </p>
        </section>

        {/* 10. Contact */}
        <section className="bg-white rounded-2xl border border-gray-100 shadow-card p-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">10. Contact</h2>
          <p className="text-gray-700 leading-relaxed">
            If you have any questions about this Privacy Policy, you can contact us at{' '}
            <a
              href="mailto:help@mergers.fyi"
              className="text-primary hover:text-primary-dark font-medium hover:underline transition-colors"
            >
              help@mergers.fyi
            </a>
            .
          </p>
        </section>

      </div>
    </>
  );
}
