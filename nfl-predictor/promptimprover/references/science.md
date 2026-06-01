# Scientific Constraints

Constraints from current LLM research that inform prompt construction. Read this file when you need to justify a
structural decision or when the user asks why a prompt is structured a certain way.

---

## Working Memory & Context Limits

Transformer models exhibit "working memory" limitations similar to humans, often struggling with N-back tasks as N
increases. This acts as a finite "attention budget"; performance degrades as this budget is depleted by increasing token
counts.

**Implication:** Keep prompts as short as possible while retaining all load-bearing information. Every unnecessary
sentence depletes the attention budget.

---

## Context Rot & Coherence

"Context rot" refers to performance degradation as input length grows. Surprisingly, structured, coherent "filler"
text (like essays) degrades performance more than random sentences because it disrupts the model's logical flow.

**Implication:** Remove all non-essential prose from prompts. Explanatory padding is worse than silence.

---

## Hidden in the Haystack

Contrary to the assumption that concise rules are better, research shows "smaller needles" (shorter gold contexts) are
harder for LLMs to find than longer ones. Extremely short instructions may get lost in the noise of a large context
window.

**Implication:** Critical rules must be substantial enough to be detected. A single-word constraint is more likely to be
overlooked than a clearly stated sentence.

---

## Lost in the Middle

Models display a U-shaped attention curve:

- **Best performance**: information at the very beginning of the context
- **Worst performance**: information buried in the middle
- **Good performance**: information at the very end

Information in the middle is significantly more likely to be overlooked.

**Implication:** Use the 30/55/15 positional doctrine. Identity, hard rules, and output locks go in the first 30% (
primacy zone). Execution logic fills the middle 55%. Verification and success criteria go in the last 15% (recency
zone). Never bury critical constraints in the middle.

---

## SOTA Best Practices

Newer models (e.g., Claude 4.6, Gemini 3.1, GPT-5.4) are highly responsive to system prompts. Aggressive commands (
e.g., "CRITICAL: YOU MUST") now cause "overtriggering" of tools. It is better to use plain, direct imperatives.

**Implication:** Use clear, direct language. "Do X" is better than "YOU MUST ALWAYS DO X." Reserve emphasis for
genuinely critical constraints, not routine instructions.

---

## Reasoning & "State Your Understanding"

To improve accuracy, use "adaptive thinking" or prompt the model to "reflect" and plan before acting. This helps
calibrate the model's effort to the query's complexity.

**Implication:** For complex tasks on standard reasoning models, add "Think through this step by step before answering."
For reasoning-native models (o1, o3, R1), do NOT add this; they reason internally and external CoT degrades their
output.

---

## Just-in-Time Context

Rather than front-loading all data, use "just-in-time" loading where the model retrieves specific files or chunks
dynamically using tools. This preserves the attention budget.

**Implication:** When building prompts for agentic systems, prefer tool-based context retrieval over pasting entire
codebases or documents into the prompt.
