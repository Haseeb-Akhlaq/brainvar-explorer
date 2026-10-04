/**
 * The permission logic the interface branches on.
 *
 * These are presentation decisions, not access control — the API re-checks
 * `users.view_user` on every request. What they pin down is that the client
 * asks the same question the server answers, and that it fails closed when it
 * cannot tell.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchCurrentUser, hasPerm, PERMISSIONS, type User } from "../auth";

function makeUser(permissions: string[]): User {
  return {
    id: 1,
    email: "someone@example.com",
    fullName: "",
    orcid: "",
    isStaff: false,
    permissions,
  };
}

describe("hasPerm", () => {
  it("is true when the user holds the permission", () => {
    expect(hasPerm(makeUser(["users.view_user"]), PERMISSIONS.viewUsers)).toBe(true);
  });

  it("is false when the user holds other permissions", () => {
    expect(hasPerm(makeUser(["users.add_user", "brainvar.view_gene"]), PERMISSIONS.viewUsers)).toBe(
      false,
    );
  });

  it("is false for a signed-out visitor rather than throwing", () => {
    expect(hasPerm(null, PERMISSIONS.viewUsers)).toBe(false);
  });

  it("does not match on a prefix", () => {
    // "users.view_userprofile" must not satisfy "users.view_user".
    expect(hasPerm(makeUser(["users.view_userprofile"]), PERMISSIONS.viewUsers)).toBe(false);
  });

  it("is exact about the app label", () => {
    expect(hasPerm(makeUser(["view_user"]), PERMISSIONS.viewUsers)).toBe(false);
    expect(hasPerm(makeUser(["auth.view_user"]), PERMISSIONS.viewUsers)).toBe(false);
  });
});

describe("PERMISSIONS", () => {
  it("matches the codename Django generates for the users.User model", () => {
    // app_label.codename, where the codename is view_<model_name lowercased>.
    // If the model or app is ever renamed, the API stops recognising this
    // string and the panel silently disappears — hence pinning it here.
    expect(PERMISSIONS.viewUsers).toBe("users.view_user");
  });
});

describe("fetchCurrentUser", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function respondWith(status: number, body: unknown) {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: status >= 200 && status < 300,
        status,
        json: async () => body,
      }),
    );
  }

  const wire = {
    id: 7,
    email: "admin@example.com",
    full_name: "Ada Lovelace",
    orcid: "",
    is_staff: false,
  };

  it("maps the permission list off the wire", async () => {
    respondWith(200, { ...wire, permissions: ["users.view_user"] });
    const user = await fetchCurrentUser();
    expect(hasPerm(user, PERMISSIONS.viewUsers)).toBe(true);
  });

  it("treats a missing permissions field as no permissions", async () => {
    // A backend older than this feature omits the field. Defaulting to []
    // hides the gated controls, which is the safe direction to fail.
    respondWith(200, wire);
    const user = await fetchCurrentUser();
    expect(user?.permissions).toEqual([]);
    expect(hasPerm(user, PERMISSIONS.viewUsers)).toBe(false);
  });

  it("returns null without a session", async () => {
    respondWith(403, {});
    expect(await fetchCurrentUser()).toBeNull();
  });
});
