import { useState } from 'react';
import { getTeamColors, getTeamLogoUrl } from '../theme/teamColors';

interface Props {
  abbr: string;
  /** Pixel size (width = height). Default 40. */
  size?: number;
  className?: string;
}

/**
 * Displays an ESPN CDN team logo.
 * Falls back to a colored circle with the abbreviation if the image fails to load.
 */
export default function TeamLogo({ abbr, size = 40, className = '' }: Props) {
  const [errored, setErrored] = useState(false);
  const colors = getTeamColors(abbr);

  if (errored) {
    return (
      <span
        className={`inline-flex items-center justify-center rounded-md font-display font-bold text-white shrink-0 ${className}`}
        style={{
          width: size,
          height: size,
          backgroundColor: colors.primary,
          fontSize: size * 0.3,
        }}
      >
        {abbr}
      </span>
    );
  }

  return (
    <img
      src={getTeamLogoUrl(abbr)}
      alt={abbr}
      width={size}
      height={size}
      className={`object-contain shrink-0 ${className}`}
      onError={() => setErrored(true)}
    />
  );
}
