import assert from "node:assert/strict";
import test from "node:test";
import { readResetToken } from "../fortune-next-app/app/reset-link.ts";
const token="a".repeat(43);
test("fragment token is accepted",()=>assert.equal(readResetToken("https://app.example.test/reset-password#token="+token),token));
test("query token is never accepted",()=>assert.equal(readResetToken("https://app.example.test/reset-password?token="+token),""));
test("invalid token characters rejected",()=>assert.equal(readResetToken("https://app.example.test/reset-password#token=javascript:alert(1)"),""));
test("short long and invalid URLs rejected",()=>{for(const value of ["bad","https://app.example.test/#token=a","https://app.example.test/#token="+"a".repeat(201)])assert.equal(readResetToken(value),"");});
