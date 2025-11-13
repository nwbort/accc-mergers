function Footer() {
  return (
    <footer className="bg-white border-t border-gray-200 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center text-sm text-gray-600">
          <p className="mb-2">
            <strong>Disclaimer:</strong> This is an unofficial website created by{' '}
            <a
              href="https://nicktwort.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:text-primary-dark underline"
            >
              Nick Twort
            </a>
            .
          </p>
          <p className="mb-2">
            The information on this site is provided for informational purposes
            only and should not be relied upon for legal or business decisions.
          </p>
          <p>
            No responsibility is accepted for any errors, omissions, or reliance
            on the information presented. For official merger information, please
            visit the{' '}
            <a
              href="https://www.accc.gov.au/business/mergers/public-merger-reviews"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:text-primary-dark underline"
            >
              ACCC website
            </a>
            .
          </p>
        </div>
      </div>
    </footer>
  );
}

export default Footer;
