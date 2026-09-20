/**
 * @vitest-environment jsdom
 */
import { afterEach, describe, expect, it } from "vitest";
import {
  clearOperatorToken,
  hasOperatorToken,
  readOperatorToken,
  writeOperatorToken,
} from "./operatorToken";

describe("operatorToken", () => {
  afterEach(() => {
    clearOperatorToken();
  });

  it("returns null when unset", () => {
    expect(readOperatorToken()).toBeNull();
    expect(hasOperatorToken()).toBe(false);
  });

  it("stores a trimmed token and can clear it", () => {
    writeOperatorToken("  secret-token  ");
    expect(readOperatorToken()).toBe("secret-token");
    expect(hasOperatorToken()).toBe(true);
    writeOperatorToken("   ");
    expect(readOperatorToken()).toBeNull();
  });
});
