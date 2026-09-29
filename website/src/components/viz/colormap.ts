// Colour maps for thermograms. Inferno is perceptually uniform with monotonic
// lightness (the "semantic heat" exception to one-hue sequential scales) and
// reads correctly for colour-blind viewers; grayscale is the plain alternative.
// No rainbow maps: they invent edges in smooth temperature fields.

const INFERNO_STOPS = [
  "#000004", "#1b0c41", "#4a0c6b", "#781c6d", "#a52c60",
  "#cf4446", "#ed6925", "#fb9b06", "#f7d13d", "#fcffa4",
];

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function buildLut(stops: string[]): Uint8ClampedArray {
  const rgb = stops.map(hexToRgb);
  const lut = new Uint8ClampedArray(256 * 3);
  for (let i = 0; i < 256; i++) {
    const p = (i / 255) * (rgb.length - 1);
    const k = Math.min(rgb.length - 2, Math.floor(p));
    const f = p - k;
    for (let c = 0; c < 3; c++) lut[i * 3 + c] = rgb[k][c] + (rgb[k + 1][c] - rgb[k][c]) * f;
  }
  return lut;
}

export const COLORMAPS = {
  inferno: { label: "Inferno", lut: buildLut(INFERNO_STOPS), css: INFERNO_STOPS },
  gray: { label: "Grayscale", lut: buildLut(["#000000", "#ffffff"]), css: ["#000000", "#ffffff"] },
} as const;

export type ColormapKey = keyof typeof COLORMAPS;

export const gradientCss = (key: ColormapKey, direction = "to right") =>
  `linear-gradient(${direction}, ${COLORMAPS[key].css.join(", ")})`;
