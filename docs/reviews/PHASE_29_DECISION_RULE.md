# Phase 29 preregistered decision rule

This rule is committed before the dogfood snapshot and final Full-vs-Lite
scores exist. It must not be changed after either result is observed.

## Architecture-dependent categories

Full passes the intelligence gate only if it demonstrates a clear advantage in
at least three of these five categories, with no category showing a material
trustworthiness regression:

1. dependency-aware corroboration;
2. temporal and correction intelligence;
3. grounded refusal and uncertainty honesty;
4. longitudinal material-change explanation;
5. Research usefulness and canonical question reevaluation.

“Clear advantage” means the blinded rubric shows a higher mean score than Lite
on the category and at least one blinded case provides a concrete Full-only
structural result. A tie is not an advantage.

## Guardrails

The gate is falsified if Full materially loses on factual or citation
correctness, or if either side’s effective provider/model/configuration fails
the frozen contract. Fallback is operationally allowed but invalidates the
comparison when the requested contract requires a different effective route.

Basic retrieval, latency, and provider cost are reported separately; they do
not erase a structural-category failure. If Full wins fewer than three
architecture-dependent categories, classify the thesis as partially proven or
Lite-equivalent according to the observed results rather than moving the
threshold.

The final report must show category scores, case-level evidence, latency/cost,
effective execution configuration, blind-scoring method, dogfood limitations,
and the resulting KEEP/SIMPLIFY/CONTEXTUALIZE/DEFER/REMOVE decisions.
