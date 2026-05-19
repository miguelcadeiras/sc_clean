# V2 Matching AI Rules

This document describes the current diagnostic rules used by `app_v2` to suggest
`wmsAI` or `agvAI` in the mismatch view.

The AI suggestion is diagnostic only. It does not change `match`, does not change
`desc`, and does not write validation rows to the database.

## Baseline Fields

- `match` keeps the original AGV vs WMS comparison.
- `desc = 2` keeps the original `+/-2` diagnostic.
- `VerifiedAI` is only a suggestion:
  - `wmsAI`: local physical evidence supports WMS position.
  - `agvAI`: local physical evidence supports AGV position.
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

The legacy `vRack` is still calculated and kept for compatibility. The AI
suggestion uses a separate physical grouping:

```text
encoder_segment
pallet_window
```

This avoids changing the baseline `match` and `desc` counts while we validate
the new physical reasoning.

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

Inside the physical pallet window:

1. Count `codePos` labels by position base.
2. If there are no local labels, return `False`.
3. If the winning position has fewer than 2 labels, return `False`.
4. If the winning position is not at least 2x the second position count, return
   `False` as ambiguous.
5. If the winning position equals WMS position, return `wmsAI`.
6. If the winning position equals AGV position and differs from WMS, return
   `agvAI`.
7. If the winning position matches neither WMS nor AGV, return `False`.

## Counters

The mismatch page compares the legacy and v2 baseline counts:

```text
False legacy/v2
+/-2 legacy/v2
```

Then it splits the v2 `+/-2` rows into:

```text
wmsAI
agvAI
remaining +/-2 to check
```

The expected relationship is:

```text
wmsAI + agvAI + remaining +/-2 to check = +/-2 v2
```

## Color Priority

Human validation has priority over AI coloring:

1. `verified = wms`: yellow row.
2. `verified = agv`: red row.
3. If no human validation exists:
   - `VerifiedAI = wmsAI`: green row.
   - `VerifiedAI = agvAI`: red row.
