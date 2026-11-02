import assert from "node:assert/strict";
import test from "node:test";
import { byFmt } from "../src/lib/format.js";

test("missing currency values display as unavailable", () => {
  for (const fmt of ["usd_bn1", "inr_lc1"]) {
    for (const value of [null, undefined, NaN]) {
      assert.equal(byFmt(value, fmt), "–");
    }
  }
});

test("zero and signed currency values keep their formatting", () => {
  assert.equal(byFmt(0, "usd_bn1"), "$0.0bn");
  assert.equal(byFmt(0, "inr_lc1"), "₹0.0 lakh cr");
  assert.equal(byFmt(2.5, "usd_bn1"), "$2.5bn");
  assert.equal(byFmt(-2.5, "usd_bn1"), "−$2.5bn");
  assert.equal(byFmt(2.5, "inr_lc1"), "₹2.5 lakh cr");
  assert.equal(byFmt(-2.5, "inr_lc1"), "−₹2.5 lakh cr");
});
