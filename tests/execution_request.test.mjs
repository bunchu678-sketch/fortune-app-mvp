import assert from "node:assert/strict";
import test from "node:test";
import { executionRequestIds } from "../fortune-next-app/app/execution-request.ts";
test("retries retain one ID", () => { let n = 0; const ids = executionRequestIds(() => String(++n)); assert.equal(ids.key({ date: "2026-01-01" }), ids.key({ date: "2026-01-01" })); assert.equal(n, 1); });
test("changed conditions receive another ID", () => { let n = 0; const ids = executionRequestIds(() => String(++n)); assert.notEqual(ids.key({ date: "2026-01-01" }), ids.key({ date: "2026-01-02" })); });
test("boundary preview retains ID while selected calculation is separate", () => { let n = 0; const ids = executionRequestIds(() => String(++n)); const preview = ids.key({ birthDate: "1988-01-01" }); ids.key({ birthDate: "1988-01-01", choice: "before" }); assert.equal(ids.key({ birthDate: "1988-01-01" }), preview); });
test("completed new run receives new ID", () => { let n = 0; const ids = executionRequestIds(() => String(++n)); const first = ids.key({ date: "2026-01-01" }); ids.complete(); assert.notEqual(ids.key({ date: "2026-01-01" }), first); });
