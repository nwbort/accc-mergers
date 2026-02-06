function Footer() {
  return (
    <footer className="border-t border-gray-200/60 mt-auto bg-white/50 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="text-center text-xs text-gray-500 leading-relaxed">
          <span className="font-semibold text-gray-600">Disclaimer:</span> This is an unofficial website created by{' '}
          <a
            href="https://nick.twort.co.nz/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:text-primary-dark font-medium hover:underline transition-colors"
          >
            Nick Twort
          </a>
          . The information on this site is provided for informational purposes only and should not be relied upon for legal or business decisions. No responsibility is accepted for any errors, omissions, or reliance on the information presented. For official merger information, please visit the{' '}
          <a
            href="https://www.accc.gov.au/public-registers/mergers-and-acquisitions-registers/acquisitions-register"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:text-primary-dark font-medium hover:underline transition-colors"
          >
            ACCC website
          </a>
          .
        </div>
      </div>
    </footer>
  );
}

export default Footer;
