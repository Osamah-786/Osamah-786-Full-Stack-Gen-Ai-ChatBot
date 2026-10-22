# Premium Frontend Redesign — Understanding and Implementation Scope

## Product goal

Turn Document Copilot into a polished research workspace for SEC filing analysis. The redesign should improve the whole experience—layout, hierarchy, typography, evidence presentation, responsive behavior, and interaction—while preserving the working application rather than replacing it with a static mockup.

## Existing product and constraints

- The frontend is a Vite, React, and TypeScript SPA with Supabase sign-in/sign-up, protected chat and thread routes, conversation history, a custom SSE client, citations, and a source excerpt panel.
- Styling uses the existing global CSS files. Tailwind-related packages are present but are not wired into the frontend; shadcn/ui and an AI SDK are not installed.
- The existing backend response provides answer text, citations, and an insufficient-evidence flag. It does not currently provide a validated structured table result.
- Preserve authentication, routes, API contracts, streaming, persistence/history, citation validation, source links, and error handling. Keep backend and database behavior unchanged unless a concrete existing contract requires it.
- Do not add fake controls, mock production data, invented citations, or financial values inferred from prose.

## Proposed visual direction

Use a restrained editorial research aesthetic: warm ivory application background, paper-white reading surface, graphite navigation, charcoal text, muted stone secondary text, deep teal for actions and focus, and small brass details for metadata. Treat the supplied colors as initial tokens and adjust them to meet contrast requirements.

Use clear, consistent type and spacing. Keep answer text at a comfortable reading width, use tabular numerals for financial values, and reserve serif typography for answer passages only if it improves readability. Prefer thin dividers and purposeful grouping over stacked cards, gradients, glass effects, or generic AI dashboard styling.

## Workspace structure

At wide viewports, organize the authenticated workspace into three functional regions:

1. **Conversation navigation:** product identity, new conversation, existing thread list and active state, plus account/sign-out controls. Add collapse behavior only if it improves the current navigation.
2. **Research conversation:** thread topic, distinct question and answer sections, readable streaming answer, inline citations, and a consistently placed multiline composer.
3. **Source inspection:** reuse the current citation action and display the selected filing metadata and exact persisted excerpt, with a safe source link and clear close behavior.

At tablet and mobile widths, avoid squeezing all three regions together. Make navigation and source inspection accessible drawers or overlays while keeping the conversation and composer usable.

## Answer, evidence, and table behavior

- Present answers as readable research notes: conclusion first, then structured paragraphs, headings, or bullets already present in the response; preserve safe text rendering and existing citation behavior.
- Keep citation controls keyboard-accessible and visually identifiable. Never manufacture citation IDs, filing details, excerpts, or page numbers.
- Show insufficient evidence as an honest, distinct state and do not imply an unsupported conclusion.
- A comparison table is a desired presentation only when the backend supplies validated structured values and supporting evidence. The current response contract does not. Until such a contract exists, redesign the answer and citation presentation without fabricating or parsing arbitrary prose into factual cells. Treat structured table data and cell-level citation validation as a separate backend dependency.

## Authentication, history, and interaction states

Apply the same visual identity to sign-in and sign-up, retaining existing Supabase behavior and form validation. Refine empty, loading, error, insufficient-evidence, and missing-source states so each gives clear context and a useful next action. Conversation titles and grouping must come from actual supported data.

Use CSS transitions for ordinary interactions, generally 140–220 ms, and honor `prefers-reduced-motion`. Streaming should distinguish waiting, receiving, and completed states without flashing or shifting the reading layout. Every interactive control needs a real behavior, keyboard support, visible focus, and an accessible name.

## Responsive and accessibility requirements

- Check desktop, tablet, and mobile widths; prevent accidental page-level horizontal overflow.
- Use semantic elements, labeled inputs, logical heading order, visible focus, sufficient color contrast, and keyboard-operable navigation, citations, panels, and composer.
- Use accessible table headers/caption if structured tables become available.
- Do not rely on color alone for status; respect reduced-motion preferences.

## Dependencies and implementation approach

Start with the existing React components and CSS. No additional package is required for the visual redesign, basic tables, or CSS transitions. Add an icon or animation package only if implementation shows a concrete need; do not add a component or chart library preemptively. First inspect the actual routes, components, styles, and API types, then implement the smallest cohesive redesign across the app shell, chat, source panel, auth, and meaningful states.

## Suggested implementation sequence

1. Confirm current frontend components, route/auth behavior, stream and citation types, and existing styles.
2. Define a small set of color, type, spacing, surface, border, focus, and motion tokens.
3. Refine the authenticated shell and responsive conversation navigation.
4. Refine question/answer reading, streaming, citations, source inspection, and composer.
5. Apply the visual system to sign-in/sign-up and loading, empty, error, and insufficient-evidence states.
6. Verify responsive layout, keyboard access, contrast, and reduced motion.
7. Run the existing frontend lint and production build/type checks; manually verify sign-in, thread navigation, streaming, reload/history, and source panel behavior where the environment permits.

## Completion criteria

- The workspace has a coherent, purpose-built research identity across chat and auth screens.
- Existing routes, authentication, streaming, history, citations, and source inspection still work against the current API contract.
- Responsive layouts and empty/loading/error/insufficient-evidence states are intentional and accessible.
- No unsupported financial data, citations, or nonfunctional controls have been introduced.
- Existing frontend lint and build checks pass; any browser-only checks that could not be performed are reported accurately.

## Decisions to keep explicit

- The supplied palette is a direction to validate, not a claim that every proposed color already passes accessibility.
- Structured comparison tables remain conditional on a real backend response type with validated values and evidence.
- This file records the brief and implementation boundaries; it does not mark the redesign as implemented or update phase completion checkboxes.
