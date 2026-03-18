---
name: github-issue-user-story
description: 'Create GitHub issue descriptions in markdown as user stories with acceptance criteria. Use for feature requests, UI/backend enhancements, and requirement-to-issue conversion with clear validation rules.'
argument-hint: 'Paste rough requirements, notes, or a feature request to convert into a GitHub issue user story.'
user-invocable: true
---

# GitHub Issue User Story Writer

## What This Skill Produces
This skill turns rough requirements into a ready-to-paste GitHub issue in markdown.

Output format:
1. A clear issue title
2. A user story (`As a ... I want ... so that ...`)
3. Functional requirements
4. Acceptance criteria
5. Notes/assumptions where needed

## When to Use
Use this skill when you have:
- A short idea that needs to become an implementation-ready issue
- Mixed UI + backend requirements that need structure
- Raw notes that need validation rules and edge cases

Trigger phrases:
- "create issue text"
- "write a user story"
- "generate acceptance criteria"
- "turn requirements into a GitHub issue"

## Procedure
1. Parse the request and extract the feature goal, user-facing behavior, and constraints.
2. Normalize terminology and call out likely typos or naming conflicts (for example, "skills" vs "styles") in a short Notes section.
3. Convert the core request into a user story format.
4. Build requirement bullets that separate admin/configuration behavior from runtime behavior.
5. Write acceptance criteria as testable, observable statements.
6. Add fallback behavior criteria (for example, behavior when optional data is missing).
7. Return clean markdown with stable section headers.
8. Ask the user if they want to add the issue to GitHub.

## Output Template
Use this structure unless the user requests a different format.

```markdown
## Title
<concise, action-oriented title>

## User Story
As a <role>, I want <capability>, so that <outcome>.

## Description
<1-2 short paragraphs explaining intent and scope>

## Requirements
1. <requirement>
2. <requirement>
3. <requirement>

## Acceptance Criteria
1. Given <context>, when <action>, then <result>.
2. Given <context>, when <action>, then <result>.
3. <measurable validation statement>

## Notes
- <assumption, naming clarification, or non-goal>
```

## Quality Checklist
Before finalizing output, verify:
1. Markdown is valid and easy to scan.
2. The user story is present and complete (`As/I want/so that`).
3. Acceptance criteria are concrete and testable.
4. Field limits, optionality, and validation constraints from the request are preserved.
5. The issue remains useful when no optional inputs are provided.

## Tone and Style Rules
- Keep wording implementation-ready and specific.
- Prefer explicit limits (length, optional/required) over vague language.
- Avoid nested bullets to keep GitHub rendering clean.
- Use consistent domain terms throughout the issue.
