# V2 Matching AI Rules

This document describes the current `app_v2` physical-window rules used to
correct the calculated AGV position before comparing it against WMS.

The rule is still read-only at the database level: it does not write validation
rows to the database. It does change the v2 in-memory `pos`, `match`, and `desc`
calculation so we can compare the new matching result against legacy.

## Baseline Fields

- `pos_legacy` keeps the position assigned by the legacy `vRack` logic.
- `pos_rack` is the candidate position read directly in the same physical
  `rack` as the pallet.
- `pos_physical` is the candidate position inferred from encoder reset and
  physical pallet-window evidence.
- `pos_sequence` is the candidate position inferred from the rack-position
  sequence when a rack with pallets is missing its own `codePos`.
- `pos` is replaced by `pos_rack` when the same-rack candidate changes the
  legacy position and equals WMS position.
- `pos` is replaced by `pos_physical` only when the physical candidate is
  strong enough and equals WMS position.
- `pos` is replaced by `pos_sequence` only when the sequence candidate changes
  the legacy position and equals WMS position.
- `match` and `desc` are calculated from the final v2 `pos`.
- `VerifiedAI` is only a suggestion:
  - `wmsAI`: same-rack, physical-window, or sequence evidence changed legacy
    position and now supports WMS.
  - `agvAI`: physical evidence confirms the AGV/legacy position over WMS.
  - `False`: evidence is not strong enough or does not match either side.

## Position Parsing

Example:

```text
UBG100100102
UBG1 001 001 02
```

- `UBG1`: warehouse sector.
- `001`: aisle.
- `001`: position.
- `02`: level.

The position base is the first 10 characters:

```text
UBG1001001
```

Labels ending in `XX` are valid position evidence:

```text
UBG1001001XX
```

This confirms position `UBG1001001`. It only lacks level information. Level is
not used for the current position decision.

## Physical Window Logic

The rule does not use `+/-10 id_Vector` anymore.

The legacy `vRack` is still calculated and kept in `pos_legacy` for comparison.
V2 also creates a separate physical grouping:

```text
encoder_segment
pallet_window
```

When the physical grouping has strong local position evidence and the winning
position equals WMS, v2 uses that position for the actual matching comparison.
If the physical winner confirms AGV/legacy instead, v2 keeps the mismatch and
marks it as `agvAI`. If the winner is a third position, v2 does not change the
matching result.

For each `codeUnit`, the algorithm:

1. Uses the row where the pallet barcode was read.
2. Detects encoder resets when `x` drops strongly from the previous row.
   Example:

```text
x = 2.34
x = 0.30
```

This means the encoder reset and a new physical bay/segment started, even if the
`ZERO` label is missing from the database.

The current reset rule is conservative. A reset is inferred only when:

```text
prev_x > 1.8
current_x < 0.8
current_x < prev_x - 0.8
```

3. Assigns each row to an `encoder_segment`.
4. Splits each segment into pallet windows of `1.2 m`:

```text
0.0 <= x < 1.2
1.2 <= x < 2.4
2.4 <= x < 3.6
```

5. For the pallet being analyzed, only `codePos` labels in the same
   `encoder_segment` and same `1.2 m` pallet window are counted.

Labels before an encoder reset must not be used to validate a pallet after the
reset. Labels after an encoder reset must not be used to validate a pallet before
the reset.

## Decision Rules

Direct same-rack evidence has priority over the pallet-window rule. If the
physical `rack` where the pallet was read has a dominant `codePos`, v2 uses that
as `pos_rack`. This handles cases where a rigid `1.2 m` window boundary splits a
position label and its pallet into different windows even though they belong to
the same rack.

Example:

```text
rack 6990
x=1.16 -> UBG100412903
x=1.33 -> PA20220530173701745
```

The same-rack candidate is:

```text
UBG1004129
```

If it equals WMS and differs from legacy, v2 applies it and marks `wmsAI`.

Inside the physical pallet window:

1. Count `codePos` labels by position base.
2. If there are no local labels, return `False`.
3. If the winning position has fewer than 2 labels, return `False`.
4. If the winning position is not at least 2x the second position count, return
   `False` as ambiguous.
5. If the winning position is accepted, assign it to `pos_physical`.
6. If `pos_physical` differs from `pos_legacy` and equals WMS position, replace
   `pos` with `pos_physical` and mark `VerifiedAI = wmsAI`.
7. If `pos_physical` equals `pos_legacy`, still differs from WMS, and the row is
   `+/-2`, keep the mismatch and mark `VerifiedAI = agvAI`.
8. If the winning position matches neither WMS nor AGV, leave `VerifiedAI =
   False`.

## Sequence Interpolation Logic

Some racks have pallets but no readable `codePos`. In those cases, v2 can infer
the missing position from neighboring racks.

The sequence rule is conservative:

1. Build a dominant `codePos` base per physical `rack`.
2. Only infer a rack that has a `codeUnit` and no direct rack position.
3. Find the closest previous and next racks with known positions.
4. Both known positions must share the same position prefix, for example
   `UBG1006`.
5. The sequence between the known racks must move exactly `2` positions per
   rack.
6. The missing rack is assigned the interpolated position.
7. V2 only applies this candidate to `pos` when it equals WMS position.

Example:

```text
rack 7335 -> UBG1006019
rack 7336 -> UBG1006017
rack 7337 -> pallet unit, no codePos
rack 7338 -> UBG1006013
rack 7339 -> UBG1006011
```

The inferred position for rack `7337` is:

```text
UBG1006015
```

## Counters

The mismatch page compares the legacy and v2 baseline counts:

```text
False legacy/v2
+/-2 legacy/v2
```

Then it shows how v2 changed the `+/-2` set:

```text
resolved +/-2
wmsAI
agvAI
remaining +/-2 to check
```

`resolved +/-2` is:

```text
+/-2 legacy - +/-2 v2
```

The remaining v2 `+/-2` relationship is:

```text
agvAI + remaining +/-2 to check = +/-2 v2
```

## Color Priority

Human validation has priority over AI coloring:

1. `verified = wms`: yellow row.
2. `verified = agv`: red row.
3. If no human validation exists:
   - `VerifiedAI = wmsAI`: green row.
   - `VerifiedAI = agvAI`: red row.

## Production Cache

V2 persists the heavy virtual-rack calculation in MySQL:

```text
v2_virtual_rack_cache
v2_virtual_rack_cache_meta
```

The cache is keyed by `id_inspection` and `id_Vector`. It is considered valid
while the source inspection keeps the same row count and max `id_Vector`.

V2 can also persist the legacy summary counters used by the optional
`&legacy=1` header comparison:

```text
v2_legacy_matching_summary_cache
```

Warm or refresh the virtual-rack cache before using a large inspection in
production:

```bash
python manage.py warm_v2_virtual_rack_cache 348
```

By default, the v2 page does not calculate legacy counters. To compare against
legacy in the page, add:

```text
&legacy=1
```

To warm both virtual-rack cache and legacy summary cache:

```bash
python manage.py warm_v2_virtual_rack_cache 348 --legacy
```

`/readedAnalysis` uses the v2 corrected matching result for its aggregate
charts and persists the final chart payload in:

```text
v2_readed_analysis_cache
```

Warm the default aggregate chart (`asile=All`, `level=All`) with:

```bash
python manage.py warm_v2_virtual_rack_cache 348 --readed-analysis
```

Refresh every inspection:

```bash
python manage.py warm_v2_virtual_rack_cache --all
```

The page can still rebuild the cache automatically if it is missing or stale,
but warming it ahead of time avoids doing that work during a user request.
