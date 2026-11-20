import { Link } from 'react-router';

function Footer() {
  return (
    // An M3 surface container, its top corners rounded into the page.
    <footer className="mt-auto pt-12">
      <div className="mx-auto max-w-7xl rounded-t-3xl bg-surface-container px-6 sm:px-10 py-6">
        <div className="text-center text-xs text-gray-600 leading-relaxed">
          <span className="font-semibold text-gray-700">Disclaimer:</span> This is an unofficial website created by{' '}
          <Link
            to="/nick-twort"
            className="text-primary hover:text-primary-dark font-medium hover:underline transition-colors"
          >
            Nick Twort
          </Link>
          . The information on this site is provided for informational purposes only and should not be relied upon for legal or business decisions. No responsibility is accepted for any errors, omissions, or reliance on the information presented. <span className="whitespace-nowrap">For official merger information, please visit the</span>{' '}
          <a
            href="https://www.accc.gov.au/public-registers/acquisitions-and-mergers-registers/acquisitions-register"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:text-primary-dark font-medium hover:underline transition-colors"
          >
            ACCC website
          </a>
          . For enquiries or feedback, please use the{' '}
          <Link
            to="/feedback"
            className="text-primary hover:text-primary-dark font-medium hover:underline transition-colors"
          >
            feedback form
          </Link>{' '}
          or contact{' '}
          <a
            href="mailto:nick@mergers.fyi"
            className="text-primary hover:text-primary-dark font-medium hover:underline transition-colors"
          >
            nick@mergers.fyi
          </a>
          .{' '}
          <Link
            to="/privacy"
            className="text-primary hover:text-primary-dark font-medium hover:underline transition-colors"
          >
            Privacy Policy
          </Link>
          .{' '}
          <Link
            to="/copyright"
            className="text-primary hover:text-primary-dark font-medium hover:underline transition-colors"
          >
            Copyright
          </Link>
          .
        </div>
      </div>
    </footer>
  );
}

export default Footer;
