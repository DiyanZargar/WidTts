export const tokens = {
  color: {
    void: '#040d0a',
    ink100: 'rgba(255,255,255,1)',
    ink60: 'rgba(255,255,255,0.72)',
    ink35: 'rgba(255,255,255,0.42)',
    warn: 'hsl(28, 85%, 58%)',
  },
  font: {
    display: '"Space Grotesk", sans-serif',
    body: '"Inter", sans-serif',
  },
  easing: {
    expoOut: [0.16, 1, 0.3, 1],
  },
  motion: { hoverMs: 200, flareMs: 900, breathSec: 4 },
};

// Radiant Emerald palette for /admin portal
export const adminPalette = {
  dim: 'hsl(165, 85%, 22%)',     // Deep rich emerald base shadow
  mid: 'hsl(160, 90%, 42%)',     // Vibrant emerald green emissive glow
  bright: 'hsl(155, 95%, 58%)',  // Luminescent mint/emerald rim light
  bloom: 'hsl(150, 100%, 82%)',  // Soft ethereal seafoam bloom
};

// Radiant Emerald palette for /user portal (unified with admin)
export const userPalette = {
  dim: 'hsl(165, 85%, 22%)',     // Deep rich emerald base shadow
  mid: 'hsl(160, 90%, 42%)',     // Vibrant emerald green emissive glow
  bright: 'hsl(155, 95%, 58%)',  // Luminescent mint/emerald rim light
  bloom: 'hsl(150, 100%, 82%)',  // Soft ethereal seafoam bloom
};
