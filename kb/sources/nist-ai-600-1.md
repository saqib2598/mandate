# Briefing of NIST AI 600-1 Generative AI profile

NIST AI 600-1, Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile, is a United States government publication in the public domain.
URL: https://doi.org/10.6028/NIST.AI.600-1
This file is an original briefing, not the full profile. Licence of this briefing: CC0.

## Prompt injection
<!-- tags: D2 D10 | nodes: PP P | factor: data | domain: data_protection -->

The Generative AI profile treats prompt injection as a risk to systems that read untrusted text. An untrusted message can carry an instruction that tries to override the system's task, for example by telling the system to disclose a record or to ignore its policy. A pre-processor screen should flag that pattern before the model acts on it. A canary string planted only in the untrusted message is a test that the instruction was not copied into an action.

## Confabulation and provenance
<!-- tags: D2 | nodes: M | factor: research | domain: gov_services -->

The profile also treats confabulation, sometimes called hallucination, as a risk that a generative system will state a rule or a fee that no instrument contains. Content provenance and a human check are the controls the profile points to before such a statement is shown to the public.
