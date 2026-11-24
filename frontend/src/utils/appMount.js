// Whether the app has committed its first render. A page that renders as part
// of that first render is replacing the prerendered HTML of the same page
// (main.jsx), where a fade-in from transparent would only blink it; a page
// reached by navigating afterwards fades in as usual. Set by App.jsx in an
// effect, so a page's own render (StrictMode's doubled one included) reads it
// before it flips.
let settled = false;

export const hasAppSettled = () => settled;

export function markAppSettled() {
  settled = true;
}
