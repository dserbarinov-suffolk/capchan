# Writing Technical Design Documents (TDDs)

Instructions for any design document written in this repo.
Read this file in full before writing a TDD, and follow it exactly.

You are writing a Technical Design Document (TDD).
The TDD will be reviewed by a human and then handed to a coding agent for implementation.
Its job is to pin down every decision that crosses a contract boundary, and to stay silent on everything the implementer can decide for itself.

You are to use language in the style of Simplified Technical English:

- Active voice. The component that acts is the subject of the sentence.
  ("The worker writes claims," not "claims are written.")
- One instruction or fact per sentence. Keep sentences under ~20 words.
- State behavior positively. Say what the system does before what it forbids.
- No gerund/participle chains as nouns.
  Prefer "extract claims" over "the extraction of claims" / "claim extraction processing."
- Noun clusters max 3 words. Break up "source-plan-bound extraction result contract."
- One term per concept, every time — see the glossary below. Never vary a defined term for style.

You are to avoid elements of style in your language - what's a virtue in prose is a defect in a TDD.

**Sizing gate (apply BEFORE writing):**
One TDD = one independently shippable and revertable unit of work.
If the architecture diagram would need more than ~6 components, or the doc would need more than 3–4 sequence diagrams, or any diagram cannot be drawn in simple ASCII — the scope is too big or too low-level.
Stop and propose a split into multiple TDDs instead of writing one.

**Structure (use these sections, in order):**

1. **Context & Problem** — 2–4 sentences on what exists today and what's broken or missing.

2. **Goals** — bulleted, measurable where possible.

3. **Non-Goals & Forbidden Approaches** — two explicit lists:
   - _Non-goals_: scope this design will not address.
   - _Forbidden approaches_: solutions the implementer must NOT use, even where they seem natural (e.g. "do not add a GSI", "do not introduce a new Lambda", "do not denormalize this table").
     Include the common/obvious approach if it was considered and rejected.

4. **Requirements** — the constraints driving the design.
   Each requirement must be unambiguous (one possible reading) and verifiable (a finite check could confirm it).

5. **Invariants** — statements that must be true before AND after this work ships (backward compatibility guarantees, data integrity rules, idempotency properties).
   These constrain every implementation decision, including ones this doc doesn't anticipate.

6. **Proposed Architecture** — prose description supported by a C4 Container-level diagram in plain ASCII.
   One sentence per component stating its responsibility.

7. **Key Interactions** — sequence diagrams in plain ASCII for the 2–4 flows that exercise the most architectural surface.

8. **Data Model** — entities, relationships, key access patterns.
   Schema sketches are fine; full DDL is not.

9. **APIs / Interfaces** — endpoint/interface names, methods, and purpose.
   No request/response schemas or signatures UNLESS the type itself is a contract decision — i.e. if the implementer chose a different shape, the PR would be rejected.
   Those types must be pinned here exactly.

10. **Behavior & Domain Rules** — each business rule stated once in prose, then anchored with 1–3 concrete worked examples (inputs → expected outcome), always including the ugliest edge case.
    Examples are normative: if prose and example conflict, the example wins and the doc must be fixed.

11. **Acceptance Criteria** — observable, contract-level checks that define "done".
    Written so they can be turned directly into tests.
    If the work is large, group criteria into ordered milestones; each milestone is a verification gate the implementation must pass before proceeding.

12. **Cross-Cutting Concerns** — auth, observability, error handling, etc.
    One short paragraph each, only where this design deviates from or adds to repo conventions.
    Don't restate what AGENTS.md already covers.

13. **Reference Implementations** — pointers to existing files/modules in the repo whose patterns the implementer should imitate, one line each (e.g. "error handling: follow src/handlers/x.ts").

14. **Alternatives Considered** — bulleted, one line each, with the chosen option and a half-sentence on why.
    Link an ADR if the justification needs more.

15. **Halt Conditions** — anything unresolved goes here, phrased as an explicit instruction: "If implementation touches X, stop and ask before proceeding."
    No ambient open questions; every item is either resolved before handoff or converted into a halt condition.

**Style constraints:**

- Avoid the `Elegant variation` antipattern:
  Use one token per concept and use it identically every time.
  Do not give the same concept many names, and one name for many concepts:
  "final wiki placement" / "final pages" / "page metadata" / PageMetadata / "planned target page metadata" / "target page metadata" / "planned page metadata" / "planned target page."
  Likewise "route hint" appears as "route hints," "legacy route hints," "metadata-only hint," "route rationale," and "source-plan route rationale."
  Each rename forces the reviewer to decide is this a new thing or the same thing?
- Follow the `No undefined terms` rule:
  Define terms before use in a glossary in the **Context & Problem** section.
- Avoid the `Stacked negation` antipattern: do not negate already negative concepts:
  "Do not publish unsupported claims as supported"
  "Tests prove no extraction output contains final page paths as authority."
- Stop `Specification by prohibition` abuse:
  "Halt Conditions", "Non-Goals & Forbidden Approaches" - these should be used only when they stop the agent from making specific mistakes or choosing valid-looking but inappropriate design decisions based on it's reading of the TDD.
  The TDD must be self-contained - don't make it a conversation summary of a conversation that happened in chat.
  If you need to refer to outside context, use a normative markdown link to a document.
  Be selective, targeted and precise.
- Avid `Weak words and uncalibrated modals` antipattern:
  "Relevant page contracts" (relevant by what test?).
  "source span when available" (available when? decided by whom?)
  "may show summarized gaps" (must|can|may|cannot are used colloquially)
  Each require interpretation and must be banned as "weak phrases" that punt a hidden decision to the reader.
- Avoid `Nominalization and hidden actors` antipattern:
  No abstract nouns doing actions: "Extraction," "Projection," "synthesis," "placement," "ingestion," "coverage claims" - unqualified, these are "zombie nouns" and oppose the rule that characters should be subjects and actions should be verbs.
  When combined with the agentless passive ("output must be accepted only through a schema-validated artifact" — accepted by what?), the reviewer cannot answer the basic spec question: which component is responsible for which behavior.
  Compound-noun pile-ups make it worse: "extraction target set," "schema-validated artifact named extraction-results.json scoped to source plan id."
- Avoid `Redundancy across sections` antipattern:
  "Do not run source-plan-bound extraction in Zarya" (§3), "must not read raw extraction artifacts or serve extracted claims as pages" (§6), "Halt if Zarya must execute extraction for ingestion to proceed" (§15).
  The evidence-for-supported-claims rule and the no-unauthorized-paths rule each appear in Goals, Requirements, Invariants, Behavior Rules, and Acceptance Criteria.
  Because the restatements drift in wording, the reviewer can't tell whether §11 is derived from §4 or adds new constraints, so they must diff five sections against each other. That cross-checking is pure extraneous load.
- Avoid the `non-parallel enumerations` antipattern:
  "ExtractionGap records missing evidence, unsupported hints, ambiguous variants, and out-of-scope material" — four items at four different levels of abstraction (an absence, a hint type, a variant, a material category).
  The reader hunts for the organizing principle and finds none, which is its own small tax repeated throughout the lists.
- All diagrams are plain ASCII.
  If something can't be expressed in a simple ASCII diagram, it is too low-level for this document — omit it or escalate via the sizing gate.
- No pseudocode, no implementation snippets, no function signatures — except public contract types per section 9.
- State technology choices as decisions, not arguments.
  "Uses DynamoDB" — not three paragraphs comparing it to Postgres.
  If a choice needs justification, write a one-line ADR pointer.
- Soft cap: ~300 lines.
- Soft line cap: ~100 character per line
- Hard rule: One sentence per line. Use this as a forcing function for writing clear signal-rich statements and using Domain Objects instead of lengthy descriptions.
- Write for an engineer who already knows the stack.
  Don't explain what GitHub Actions or DynamoDB is.
- Prefer prose for design rationale; bullets for enumerable lists.
- Editing pass before finishing: delete any sentence describing HOW to build something rather than WHAT must be true.
  The test for inclusion: "if the implementer decided this differently, would the PR be rejected?"
  If no, cut it.

