// The source of each page that fetches nothing, keyed by route, for the check
// in routes.test.jsx that only such a page leaves `data` out of its route.
import nickTwort from '../pages/NickTwort.jsx?raw';
import privacy from '../pages/PrivacyPolicy.jsx?raw';
import copyright from '../pages/Copyright.jsx?raw';

export default {
  '/nick-twort': nickTwort,
  '/privacy': privacy,
  '/copyright': copyright,
};
