import SEO from '../components/SEO';
import { CARD } from '../utils/classNames';
import { STATIC_PAGE_META } from '../utils/pageMeta';

// Title and description live in the shared table so this page and the
// build-time prerenderer emit the same <head>.
const PAGE_META = STATIC_PAGE_META['/privacy'];

export default function PrivacyPolicy() {
  return (
    <>
      <SEO
        title={PAGE_META.title}
        description={PAGE_META.description}
        url="/privacy"
      />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">

        {/* Header */}
        <header className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">Privacy policy</h1>
          <p className="mt-1 text-sm text-gray-500">Last updated: 12 November 2026</p>
        </header>

        {/* 1. Introduction */}
        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">1. Introduction</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            Welcome to mergers.fyi (&#34;we&#34;, &#34;us&#34;, &#34;our&#34;). We are committed to protecting your privacy and
            handling your personal information in a transparent and secure manner.
          </p>
          <p className="text-gray-700 leading-relaxed">
            This Privacy Policy explains how we collect, use, and store your information when you use our website
            or our Android app.
          </p>
        </section>

        {/* 2. Information we collect */}
        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">2. Information we collect</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            We collect only the minimum personal information necessary to provide our services.
          </p>
          <p className="text-gray-700 leading-relaxed mb-3">Information you provide:</p>
          <ul className="list-disc list-inside text-gray-700 space-y-1 mb-4">
            <li>email address - when you sign up to receive our weekly email digest, on the website or in the app.</li>
          </ul>
          <p className="text-gray-700 leading-relaxed mt-4">
            We do not collect any other personal information. Section 7 explains what is kept on your own device,
            and section 8 what is involved in notifications.
          </p>
        </section>

        {/* 3. How we use your information */}
        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">3. How we use your information</h2>
          <p className="text-gray-700 leading-relaxed mb-3">We use your email address solely to:</p>
          <ul className="list-disc list-inside text-gray-700 space-y-1 mb-4">
            <li>send you the mergers.fyi weekly digest; and</li>
            <li>manage and maintain our email subscriber list.</li>
          </ul>
          <p className="text-gray-700 leading-relaxed mb-3">We do not use your information for:</p>
          <ul className="list-disc list-inside text-gray-700 space-y-1">
            <li>marketing unrelated products or services; or</li>
            <li>selling or renting your data to third parties</li>
          </ul>
        </section>

        {/* 4. Email delivery and third-party services */}
        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">4. Email delivery and third-party services</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            We use Resend to store email addresses and deliver our email digest, and to send the confirmation
            email when you sign up in the app.
          </p>
          <p className="text-gray-700 leading-relaxed mb-3">This means:</p>
          <ul className="list-disc list-inside text-gray-700 space-y-1 mb-4">
            <li>your email address is securely stored by Resend on our behalf; and</li>
            <li>Resend processes your data only to send emails for us.</li>
          </ul>
        </section>

        {/* 5. Data storage and security */}
        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">5. Data storage and security</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            We take reasonable steps to protect your information from misuse, loss, or unauthorised access.
          </p>
          <p className="text-gray-700 leading-relaxed">
            Your email address is stored securely through our email service provider (Resend), which implements
            its own security measures.
          </p>
        </section>

        {/* 6. Unsubscribing */}
        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">6. Unsubscribing</h2>
          <p className="text-gray-700 leading-relaxed mb-3">You can unsubscribe at any time by:</p>
          <ul className="list-disc list-inside text-gray-700 space-y-1 mb-4">
            <li>Clicking the &#34;unsubscribe&#34; link in any email we send</li>
          </ul>
          <p className="text-gray-700 leading-relaxed">
            Once you unsubscribe, your email address will be removed from our mailing list.
          </p>
        </section>

        {/* 7. What stays on your device */}
        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">7. What stays on your device</h2>
          <p className="text-gray-700 leading-relaxed mb-3">
            We do not use cookies to track you. To make following work, your browser (or, in the app, your
            phone) keeps some information locally:
          </p>
          <ul className="list-disc list-inside text-gray-700 space-y-1 mb-4">
            <li>the mergers and industries you follow, and whether you follow every Phase 2 matter;</li>
            <li>which updates you have already seen, so we can mark new ones;</li>
            <li>whether you have dismissed feedback popups and other banners; and</li>
            <li>display preferences, such as how the merger list is laid out.</li>
          </ul>
          <p className="text-gray-700 leading-relaxed mb-4">
            This stays on your device. Your follow list is only shared beyond it if you use notifications, as
            section 8 describes. You can clear it at any time by clearing this site&rsquo;s data in your browser,
            or the app&rsquo;s storage on your phone.
          </p>
          <h3 className="text-base font-semibold text-gray-900 mb-2">Usage counts</h3>
          <p className="text-gray-700 leading-relaxed">
            We count how often certain features of the website are used, such as following a merger, so we can
            understand where to focus our development efforts. These are daily totals only: nothing that could
            identify you, such as a cookie, IP address or device identifier, is attached to them or stored with
            them. We do not use any third-party analytics or traffic tracking scripts (e.g. Google Analytics).
          </p>
        </section>

        {/* 8. Notifications */}
        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">8. Notifications</h2>
          <p className="text-gray-700 leading-relaxed mb-4">
            Notifications about what you follow are delivered by Google&rsquo;s Firebase Cloud Messaging. On the
            website they are off unless you turn them on. The Android app uses the same service to learn when to
            check for updates, and sets it up when it starts.
          </p>
          <p className="text-gray-700 leading-relaxed mb-3">When notifications are in use:</p>
          <ul className="list-disc list-inside text-gray-700 space-y-1 mb-4">
            <li>
              Google issues your browser or app a push token: a random identifier for that browser or app
              install, not linked to your name or email address;
            </li>
            <li>
              that token is subscribed to a &ldquo;topic&rdquo; for each merger and industry you follow (and for
              new Phase 2 matters, if you follow them all), and Google keeps the token and its topics so it can
              deliver messages;
            </li>
            <li>
              on the website, the request to subscribe passes through our server, which hands it to Google and
              keeps nothing: not the token, not your topics, and no log of either; and
            </li>
            <li>
              the messages themselves carry no news and nothing about you. They only tell your browser or phone
              to check mergers.fyi, and it works out what is new and shows the notification itself.
            </li>
          </ul>
          <p className="text-gray-700 leading-relaxed mb-4">
            Google handles this under its own{' '}
            <a
              href="https://policies.google.com/privacy"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:text-primary-dark font-medium hover:underline transition-colors"
            >
              privacy policy
            </a>
            .
          </p>
          <p className="text-gray-700 leading-relaxed mb-3">To stop notifications:</p>
          <ul className="list-disc list-inside text-gray-700 space-y-1">
            <li>
              on the website, turn off &ldquo;Browser notifications&rdquo; in the notification panel, which deletes
              the token and with it every topic subscription (blocking notifications for mergers.fyi in your
              browser&rsquo;s settings also stops them); or
            </li>
            <li>
              in the app, turn its notifications off in your phone&rsquo;s settings. The app keeps its token so it
              still knows when to check for updates; uninstalling the app removes it.
            </li>
          </ul>
          <p className="text-gray-700 leading-relaxed mt-4">
            On the website, following does not depend on notifications: without them, updates still show in the
            notification panel when you visit.
          </p>
        </section>

        {/* 9. Access and correction */}
        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">9. Access and correction</h2>
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

        {/* 10. Changes to this policy */}
        <section className={`${CARD} p-8 mb-6`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">10. Changes to this policy</h2>
          <p className="text-gray-700 leading-relaxed">
            We may update this Privacy Policy from time to time. Any changes will be posted on this page
            with an updated effective date.
          </p>
        </section>

        {/* 11. Contact */}
        <section className={`${CARD} p-8`}>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">11. Contact</h2>
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
