// Retain IDs across retries and boundary-confirmation resubmits; clear after a completed UI run.
export function executionRequestIds(makeId: () => string = () => crypto.randomUUID()) {
  const ids = new Map<string, string>();
  return {
    key(payload: Record<string, unknown>) {
      const serialized = JSON.stringify(payload);
      if (!ids.has(serialized)) ids.set(serialized, makeId());
      return ids.get(serialized)!;
    },
    complete() { ids.clear(); },
  };
}
