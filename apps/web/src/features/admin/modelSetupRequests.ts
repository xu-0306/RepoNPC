/** Prevent an older list response from replacing a newly saved/tested setting. */
export class ModelSetupRequests {
  private generation = 0;

  async read<T>(
    load: () => Promise<T>,
    apply: (value: T) => void,
  ): Promise<void> {
    const generation = ++this.generation;
    try {
      const value = await load();
      if (generation === this.generation) apply(value);
    } catch (error) {
      if (generation === this.generation) throw error;
    }
  }

  async mutate<T>(
    save: () => Promise<T>,
    apply: (value: T) => void,
  ): Promise<T> {
    ++this.generation;
    const value = await save();
    ++this.generation;
    apply(value);
    return value;
  }
}

export function replaceSetting<T>(values: T[], saved: T, key: keyof T): T[] {
  return values.some((value) => value[key] === saved[key])
    ? values.map((value) => (value[key] === saved[key] ? saved : value))
    : [...values, saved];
}
