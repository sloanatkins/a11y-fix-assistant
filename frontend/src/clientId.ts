// A random ID for this browser, so the API only shows this browser's scans.
// It isn't a login: clearing site data or switching devices starts fresh.

const STORAGE_KEY = "a11y-client-id";

// still works for this visit if the browser blocks storage
let memoryId: string | null = null;

function makeId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function getClientId(): string {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) return saved;
    const created = makeId();
    window.localStorage.setItem(STORAGE_KEY, created);
    return created;
  } catch {
    memoryId = memoryId ?? makeId();
    return memoryId;
  }
}
