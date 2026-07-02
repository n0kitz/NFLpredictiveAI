import '@testing-library/jest-dom';

// jsdom in this setup exposes no localStorage; provide an in-memory
// implementation so persistence code (league settings, draft board) is
// testable.
if (typeof globalThis.localStorage === 'undefined') {
  const store = new Map<string, string>();
  const memoryStorage: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, value: string) => {
      store.set(key, String(value));
    },
  };
  Object.defineProperty(globalThis, 'localStorage', {
    value: memoryStorage,
    writable: true,
  });
  Object.defineProperty(window, 'localStorage', {
    value: memoryStorage,
    writable: true,
  });
}
