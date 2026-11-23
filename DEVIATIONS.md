# Deviations and corrections log (reported in Section 6)

D1. First test run (before any scenario run): V11 failed in 9 of its 9 cases (8 scenario cases + 1 mutation case).
    Cause: the test compared the `position` field of the combined (security + personal data) ranking.
    Positions in the combined ranking legitimately change with the personal-data declaration. Section 5.5 (P1)
    requires equality of "the ranking restricted to the security-scope indicators", that is, the relative order
    of the security indicators with their weights, gap scores and priority scores. The test was corrected to
    compare that restricted ranking. The engine was not changed. All tests were re-run afterwards.
D2. The JSON repository stores one relationship term and one relationship note per indicator, as given in Table A4.
    Section 4.2/A.1 states that it stores a term and a note for each individual source reference. Table A4 gives
    only one note per indicator, so per-reference terms cannot be derived from it without inventing them.
    Not implemented per reference. To be corrected in the text of Section 4 (store term and note per indicator).
D3. Rounding to one decimal uses half-up on the exact fraction (integer arithmetic). Section 4.3 does not state the
    tie rule. Exact ties are flagged in every metric (`exact_rounding_tie`) and counted in Section 6.
D4. The engine rejects "not applicable" for indicators that Table A3 marks "Always applicable", and for SG-04, SC-04
    and SO-05 requires the corresponding scenario context flag to be false. This is an implementation decision that
    follows Table A3; it is not stated in Section 4.3.
D5. The manual comparison compares reduced fractions (exact value equality) and displayed values. The engine stores
    canonical, unreduced numerators and denominators. Section 5.7 says "integer numerators and denominators"; equality
    of the reduced fractions is the exact-value equivalent. 
D6. The reference calculation for the manual comparison was produced by an independent program using exact rational
    arithmetic from the specification text. It was not performed by hand by the researcher. It is independent of the
    engine code, not a human hand calculation (Section 5.7 and Section 7).
D7. No version-control history exists for this project. The dated record required by Section 5.7 step 2 is the file
    manual/hand_results_2026-11-23.json with its SHA-256 (ddc8e813aac5de614ac3485989ce11f730b941253b43954b807c05081d0ee5ca)
    and the UTC time stored inside it. It was produced when the results directory was empty (no engine output existed).
D8. The Django layer (form, report page, SQLite storage) was added after the first complete evaluation run. In line with
    Section 5.9, all runs were repeated on the final code. All 24 scenario outputs, the summary and the sensitivity
    results of the repeated run are byte-identical to those of the first run.

D9. Section 5.7 was revised after the runs. The original text (hand calculation by the researcher) is archived unchanged in
    spec/archive/section_5_7_original_manual_comparison.txt (SHA-256 95199a48bf8d403ec500f03f6ada54b2aae26535044531eb9dd6713b4c051b5b), archived at 2026-11-23T14:17:38+00:00.
    The revised procedure (independent reference implementation) is summarized in spec/archive/section_5_7_revised_summary.txt.
    The original plan was not carried out. The revision describes the comparison that was performed.
D10. Corrections made to the wording of Section 4 after the runs (documentation only, no repository or scenario change, hashes unchanged):
    (a) relationship term and note stored per indicator, not per source reference; (b) the not-applicable rule of Appendix A.1.
    Repository and scenario hashes in FREEZE_MANIFEST.json and results/run_manifest.json are unchanged.
