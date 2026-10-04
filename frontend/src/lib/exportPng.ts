/**
 * Serialize the chart SVG and download a 2× PNG — the web-app answer to the
 * original script's PDF output.
 *
 * The SVG carries literal hex colours (see ExpressionChart), so the raster
 * needs no external stylesheet. It does still need the image to load, and
 * that is where this used to fail in production: the SVG was handed to the
 * <img> as a `blob:` URL, and the deployed Content-Security-Policy allows
 * `img-src 'self' data:` but not `blob:`. The load was refused, `onload`
 * never fired, and the button did nothing at all — no error, no download.
 *
 * A `data:` URL renders under that policy unchanged, so the export no longer
 * depends on the header being widened for it. Failures are also reported now
 * rather than swallowed, which is what made the original bug invisible.
 */

/** Rejects rather than hanging when the browser refuses to load the SVG. */
function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () =>
      reject(new Error("The chart could not be rendered as an image."));
    img.src = src;
  });
}

export async function exportChartPng(
  container: HTMLElement | null,
  filename: string,
): Promise<void> {
  // Explicitly the chart, not "the first SVG in this box" — the card also
  // holds the toolbar, and an icon added there would otherwise be exported
  // instead, silently and with no clue why.
  const svg =
    container?.querySelector<SVGSVGElement>("svg.chart-svg") ??
    container?.querySelector("svg");
  if (!svg) throw new Error("The chart is not ready yet.");

  const xml = new XMLSerializer().serializeToString(svg);
  const source = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(xml)}`;
  const img = await loadImage(source);

  // clientWidth is 0 if the card is hidden; the viewBox is the honest size.
  const width = svg.clientWidth || svg.viewBox.baseVal.width;
  const height = svg.clientHeight || svg.viewBox.baseVal.height;
  const scale = 2;

  const canvas = document.createElement("canvas");
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Could not prepare the image.");
  ctx.scale(scale, scale);

  // The SVG has no background of its own. Without this the PNG is
  // transparent, which renders the dark theme's pale labels and axes
  // invisible anywhere they land on white — a document, Slack, a slide.
  const surface = getComputedStyle(document.documentElement)
    .getPropertyValue("--surface")
    .trim();
  ctx.fillStyle = surface || "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(img, 0, 0, width, height);

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/png"),
  );
  if (!blob) throw new Error("Could not encode the image.");

  // A blob: href on the anchor is fine under the same policy — CSP governs
  // what the page loads, not what it hands the user to save.
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  // Revoking in the same tick can cancel the download before the browser has
  // read the blob; one turn of the event loop is enough.
  setTimeout(() => URL.revokeObjectURL(href), 0);
}
