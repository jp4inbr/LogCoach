import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AuthContext, useAuth } from "./auth-context.js";

describe("useAuth", () => {
  it("devolve o valor do AuthContext", () => {
    const value = { token: "t", email: "a@b.com", login() {}, logout() {} };
    const wrapper = ({ children }) => (
      <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
    );
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current).toBe(value);
  });

  it("fora de um provider devolve null", () => {
    const { result } = renderHook(() => useAuth());
    expect(result.current).toBeNull();
  });
});
