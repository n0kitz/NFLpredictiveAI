# Tool Routing Reference

12 tool categories with routing rules. Read this file to identify which category the target tool belongs to and how to
format the prompt accordingly.

---

## 1. Reasoning LLM (Claude, GPT-5.4, Gemini)

Full structure. XML tags for Claude. Explicit format locks. Numeric constraints over vague adjectives. Role assignment
required for complex tasks.

**Best templates:** A (RTF), B (CO-STAR), C (RISEN), E (CoT), F (Few-Shot)

**Key rules:**

- Use XML tags for reliable parsing (especially Claude)
- State numeric constraints: "3 bullet points, each under 20 words" not "a short summary"
- Assign a domain-specific role for complex tasks
- Add grounding anchors for factual tasks

---

## 2. Thinking LLM (o1, o3, DeepSeek-R1)

Short, clean instructions ONLY. NEVER add reasoning scaffolding. State what you want, not how to think. These models
reason internally; constraining the reasoning path degrades output.

**Best templates:** A (RTF) — keep it simple

**Key rules:**

- NEVER add "think step by step" or CoT instructions
- NEVER add reasoning structure or thinking tags
- State the task and constraints clearly, then stop
- Shorter is better; these models handle ambiguity well

---

## 3. Open-Weight LLM (Llama, Mistral, Qwen)

Shorter prompts. Simpler structure. No deep nesting. These models lose coherence in complex hierarchies.

**Best templates:** A (RTF), F (Few-Shot)

**Key rules:**

- Keep prompt under 500 tokens if possible
- Avoid deeply nested XML or complex formatting instructions
- Few-shot examples are more reliable than written instructions
- One task per prompt; do not chain

---

## 4. Agentic AI (Claude Code, Devin, SWE-agent)

Starting state + target state + allowed actions + forbidden actions + stop conditions + checkpoint output. Stop
conditions are NOT optional; runaway loops are the single biggest credit killer.

**Best templates:** H (ReAct + Stop Conditions)

**Key rules:**

- Always define starting state and target state
- Always include explicit stop conditions
- Always add checkpoint output ("After each step output: [what was completed]")
- Always add human review triggers for destructive actions
- Scope filesystem access to specific directories
- Do NOT leave agents unrestricted

---

## 5. IDE AI (Cursor, Windsurf, Copilot)

File path + function name + current behavior + desired change + do-not-touch list + language and version. Never give an
IDE AI a global instruction without a file anchor.

**Best templates:** G (File-Scope)

**Key rules:**

- Always specify the exact file path
- Always specify the exact function or component name
- Describe current behavior AND desired behavior
- Add an explicit "do not touch" list
- Specify language version and framework version
- Add a "done when" condition

---

## 6. Full-Stack Generator (Bolt, v0, Lovable)

Stack spec + version + what NOT to scaffold + clear component boundaries. Bloated boilerplate is the default; scope it
down explicitly.

**Best templates:** C (RISEN)

**Key rules:**

- Specify exact stack and versions (React 18, Next.js 14, TypeScript 5.3)
- List what NOT to generate (no auth, no database, no admin panel)
- Define component boundaries clearly
- Specify what the project structure should look like
- Add "do not include" constraints for common bloat

---

## 7. Search AI (Perplexity, SearchGPT)

Mode specification required: search vs analyze vs compare. Citation requirements explicit. Reframe "what do experts say"
style questions as grounded queries.

**Best templates:** A (RTF) with explicit mode

**Key rules:**

- Specify the search mode: find sources / analyze a topic / compare options
- State citation requirements explicitly
- Reframe vague queries into specific, verifiable questions
- Add "if uncertain, say so" grounding anchor
- Specify recency requirements if applicable ("sources from 2024 or later only")

---

## 8. Image AI (Gemini/Nano Banana, Midjourney, DALL-E 3, Stable Diffusion)

**Best templates:** I (Visual Descriptor)

**Tool-specific syntax:**

**Gemini API / Nano Banana (primary tool):**

- Prose prompts work well; be specific about style, mood, colors, composition
- Supports style presets: `hearthstone`, `chalk`, `digital-noir`, `watercolor`, `cyberpunk`, `digital-fantasy`, `dnd`,
  `arkham-horror`, `ghibli-landscape`, `ghibli-character`, `shonen`, `dark-fairy-tale`
- When a style preset is used, read its reference file before writing the prompt; the reference contains mandatory
  phrases, checklists, and forbidden terms
- Aspect ratios: `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`
- Resolutions: `512px`, `1K`, `2K`, `4K`
- Add "no text" if no text should appear in the image
- Describe only what is IN the scene; do not describe what is NOT (negative prompts are less effective than positive
  framing)
- Style-specific prompts override default behavior; do not mix style instructions with generic prompt padding

**Midjourney:**

- Comma-separated descriptors, NOT prose
- Parameters at end: `--ar 16:9 --style raw --v 6`
- No negative prompt flag; use `--no [thing to exclude]`

**DALL-E 3:**

- Prose description works well
- Always add "do not include any text in the image" unless text is explicitly needed
- Specify aspect ratio in natural language

**Stable Diffusion:**

- Use `(word:1.3)` weight syntax for emphasis
- CFG scale 7 to 12
- Negative prompt is MANDATORY: `blurry, low quality, watermark, extra fingers, distortion`

---

## 9. Video AI (fal.ai Kling O3 / Veo 3.1, Sora, Runway)

**Best templates:** I (Visual Descriptor) extended with motion parameters

**Tool-specific syntax:**

**fal.ai Kling O3 (primary tool, living paintings / loops):**

- Image-to-video only; requires a source image
- Prompts describe ONLY what should move, not the scene (the image provides visual context)
- Keep prompts short: 2-3 sentences max. Hard limit of 2500 characters
- Default behavior: subtle ambient animation (smoke, fire, particles, light) with all characters/creatures frozen
- Supports seamless looping (start frame = end frame); use for presentation images and living paintings
- Always include "Camera static" in custom prompts
- Always include "Seamless loop" for looped output
- CFG scale 0.0-1.0: higher = more guidance (less motion), lower = more freedom (more motion)
- Durations: 3, 5, 10, 15 seconds. 5s is best for loops.
- Aspects: `16:9`, `9:16`, `1:1`
- Scene-specific prompt patterns: "Lava flows, bubbles pop, embers drift. Camera static. Seamless loop." / "Magic energy
  pulses, runes glow, arcane sparks swirl. Camera static. Seamless loop."

**fal.ai Veo 3.1 (primary tool, realistic motion / high-res):**

- Image-to-video only; requires a source image
- Same prompt principles as Kling but with 20000 character limit
- No loop support; use Kling O3 for seamless loops
- Generates audio by default; add `--no-audio` to suppress
- Resolutions: 720p, 1080p, 4k
- Durations: 4, 6, 8 seconds
- Best for: realistic movement, high resolution output, scenes where audio adds value

**Model selection rule:** Default to Kling O3. Use Veo 3.1 when the user wants realistic motion, high resolution (
1080p/4k), or audio, or explicitly asks for Veo.

**Sora / Runway (general knowledge):**

- Text-to-video or image-to-video depending on model
- Specify camera movement: slow dolly, static shot, crane up, tracking shot
- State duration in seconds
- Define cut style: single take, jump cut, crossfade
- Describe subject continuity across frames
- Specify aspect ratio and frame rate if the tool supports it

---

## 10. Voice AI (ElevenLabs)

Emotion + pacing + emphasis markers + speech rate. Prose descriptions do NOT translate to voice control; specify
parameters directly.

**Best templates:** Custom (no standard template fits)

**Key rules:**

- Specify emotion: calm, excited, serious, warm
- Specify pacing: slow, medium, fast, with pauses at [specific points]
- Use emphasis markers for words that need stress
- Specify speech rate numerically if supported
- Do NOT write "speak naturally" or "sound professional" — these are meaningless to voice models

---

## 11. Workflow AI (Zapier, Make, n8n)

Trigger app + event -> action app + field mapping. Step by step. Auth requirements noted explicitly.

**Best templates:** C (RISEN)

**Key rules:**

- Define trigger: which app, which event
- Define action: which app, what operation, which fields to map
- Specify field mapping explicitly (source field -> destination field)
- Note authentication requirements for each connected service
- Add error handling: what happens if a step fails
- One workflow per prompt; do not combine unrelated automations

---

## 12. Unknown Tool

If the tool is not listed above, ask these 4 questions:

1. What format does this tool accept? (natural language / structured / code)
2. Does it support system instructions separate from user input?
3. What is its most common failure — too much output, wrong scope, or hallucination?
4. Does it have memory or is it stateless?

Then build using the closest matching category above.
