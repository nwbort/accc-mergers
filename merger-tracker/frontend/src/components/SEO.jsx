import { Helmet } from 'react-helmet-async';

/**
 * SEO component for managing meta tags, Open Graph, Twitter Cards, and structured data
 *
 * @param {Object} props
 * @param {string} props.title - Page title
 * @param {string} props.description - Page description
 * @param {string} [props.url] - Canonical URL
 * @param {string} [props.image] - Open Graph image URL
 * @param {string} [props.imageAlt] - Alt text for the Open Graph image
 * @param {string} [props.type='website'] - Open Graph type (e.g. 'website', 'article')
 * @param {string} [props.locale='en_AU'] - Open Graph locale
 * @param {string} [props.publishedTime] - ISO date the article was published (type='article')
 * @param {string} [props.modifiedTime] - ISO date the article was last modified (type='article')
 * @param {string} [props.section] - Article section / category (type='article')
 * @param {Object} [props.structuredData] - JSON-LD structured data
 */
export default function SEO({
  title,
  description,
  url,
  image,
  imageAlt = 'Australian Merger Tracker',
  type = 'website',
  locale = 'en_AU',
  publishedTime,
  modifiedTime,
  section,
  structuredData
}) {
  const siteTitle = 'Australian Merger Tracker';
  const fullTitle = title ? `${title} | ${siteTitle}` : siteTitle;
  const siteUrl = 'https://mergers.fyi';
  const canonicalUrl = url ? `${siteUrl}${url}` : siteUrl;
  const ogImage = image || `${siteUrl}/og-image.png`;

  return (
    <Helmet>
      {/* Basic Meta Tags */}
      <title>{fullTitle}</title>
      <meta name="description" content={description} />

      {/* Canonical URL */}
      {url && <link rel="canonical" href={canonicalUrl} />}

      {/* Open Graph Tags */}
      <meta property="og:type" content={type} />
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:url" content={canonicalUrl} />
      <meta property="og:site_name" content={siteTitle} />
      <meta property="og:locale" content={locale} />
      <meta property="og:image" content={ogImage} />
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />
      <meta property="og:image:alt" content={imageAlt} />

      {/* Article Tags */}
      {type === 'article' && publishedTime && (
        <meta property="article:published_time" content={publishedTime} />
      )}
      {type === 'article' && modifiedTime && (
        <meta property="article:modified_time" content={modifiedTime} />
      )}
      {type === 'article' && section && (
        <meta property="article:section" content={section} />
      )}

      {/* Twitter Card Tags */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={ogImage} />

      {/* Structured Data (JSON-LD) */}
      {structuredData && (
        <script type="application/ld+json">
          {JSON.stringify(structuredData)}
        </script>
      )}
    </Helmet>
  );
}
