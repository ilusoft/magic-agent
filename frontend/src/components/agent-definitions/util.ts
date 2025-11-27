import type { KeyValueEntry } from './types';

const generateId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

export const createKeyValueEntry = (key = '', value = ''): KeyValueEntry => ({
  id: generateId(),
  key,
  value,
});

export const entriesFromRecord = (record: Record<string, string> | undefined | null) => {
  if (!record) {
    return [] as KeyValueEntry[];
  }

  return Object.entries(record).map(([key, value]) => createKeyValueEntry(key, value));
};

export const recordFromEntries = (entries: KeyValueEntry[]) => {
  return entries
    .filter((entry) => entry.key.trim().length > 0)
    .reduce<Record<string, string>>((accumulator, entry) => {
      accumulator[entry.key.trim()] = entry.value;
      return accumulator;
    }, {});
};
