const STORAGE_KEY = "x402.operator-token";

export function readOperatorToken(): string | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (!value) return null;
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  } catch {
    return null;
  }
}

export function writeOperatorToken(token: string): void {
  const trimmed = token.trim();
  if (!trimmed) {
    clearOperatorToken();
    return;
  }
  localStorage.setItem(STORAGE_KEY, trimmed);
}

export function clearOperatorToken(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore quota / private-mode */
  }
}

export function hasOperatorToken(): boolean {
  return readOperatorToken() !== null;
}
