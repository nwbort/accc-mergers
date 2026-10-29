import { FaBluesky, FaLinkedin } from 'react-icons/fa6';
import { BLUESKY_PROFILE_URL, LINKEDIN_PROFILE_URL } from '../config';

// The site's social accounts, one of which the navbar links to.
// hoverClass is spelled out in full so Tailwind's scanner sees it.
export const SOCIAL_PROFILES = {
  bluesky: {
    name: 'Bluesky',
    href: BLUESKY_PROFILE_URL,
    Icon: FaBluesky,
    hoverClass: 'hover:text-[#0085ff]',
  },
  linkedin: {
    name: 'LinkedIn',
    href: LINKEDIN_PROFILE_URL,
    Icon: FaLinkedin,
    hoverClass: 'hover:text-[#0a66c2]',
  },
};

// Which account the navbar's icon links to. Switch by changing this key.
export const NAVBAR_SOCIAL_PROFILE = SOCIAL_PROFILES.linkedin;
