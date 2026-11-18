# Lumigen Frontend – Design & Component Rules

Binding rules for every change under `frontend/`. They apply to humans and coding agents alike.
The root `AGENTS.md` / `CLAUDE.md` still apply; where they describe Jinja2/HTMX templates or
`app/web/static/*`, this file wins for the Vue frontend.

Stack: Vue 3 (`<script setup lang="ts">`), Vite, TypeScript, Pinia, vue-router, Tailwind CSS v4
(class-based dark mode via `@custom-variant dark` in `src/style.css`), `lucide-vue-next` for icons.

---

## 1. Component hierarchy (where things go)

| Layer | Path | Contains | May import from |
|---|---|---|---|
| Primitives | `src/components/ui/` | Generic, domain-free building blocks (Button, Input, Modal, …) | nothing app-specific (no stores, no api) |
| Layout | `src/components/layout/` | App shell, header, navigation, `PageShell`, `PageHeader` | `ui/`, stores |
| Shared domain | `src/components/<domain>/` | Components used by more than one feature (e.g. `queue/`) | `ui/`, `layout/`, stores |
| Feature | `src/features/<feature>/components/` | Components used by one feature only | everything above |
| View | `src/features/<feature>/<Name>View.vue` | Route entry: composes components, no raw styling beyond grid/flex layout | everything above |

Rules:
- A primitive never knows about Lumigen domain concepts (assets, sessions, providers).
- When a feature component is needed by a second feature, move it to `components/<domain>/` – do not copy it.
- When the same markup pattern (≥ 3 lines of template, or the same class string) appears in **two or more**
  files, extract a component before adding the third occurrence.
- Keep single-file components below ~300 lines of template+script. Larger files must be split into
  sub-components or composables (`src/composables/`).

## 2. Mandatory primitives – never re-implement inline

Use these instead of raw HTML elements. If a primitive lacks a variant you need, **extend the primitive**
(add a prop), do not style a raw element in a feature file.

| Need | Use | Instead of |
|---|---|---|
| Any clickable action with text | `ui/Button` (`variant`, `size`, `loading`, `#icon`) | raw `<button class="…">` |
| Icon-only action | `ui/IconButton` (requires `label` → `aria-label` + tooltip) | raw `<button>` + `<svg>`/emoji |
| Text / number / search input | `ui/Input` (`size="sm" \| "md"`) | raw `<input>` |
| Dropdown selection | `ui/Select` (`size="sm" \| "md"`) | raw `<select>` |
| Multi-line text | `ui/Textarea` | raw `<textarea>` |
| Boolean | `ui/Switch` (settings) or `ui/Checkbox` (lists/selection) | raw checkbox |
| Range | `ui/Slider` | raw `<input type="range">` |
| Label + hint + error around a control | `ui/FormField` | hand-written `<label class="text-[10px] uppercase …">` |
| Tabs / segmented control | `ui/Tabs` | hand-rolled button groups |
| Status / tag | `ui/Badge` | hand-rolled `rounded-full px-1.5 …` spans |
| Surface / container | `ui/Card` (`glass`, `padding`) | copying `rounded-2xl border … backdrop-blur-xl` |
| Dialog | `ui/Modal` | own `fixed inset-0` overlays |
| Side panel | `ui/Drawer` | own `fixed inset-0` overlays |
| Destructive confirmation | `useConfirm()` / `ui/ConfirmDialog` | `window.confirm()`, `alert()` |
| Loading | `ui/Spinner`, `ui/LoadingState`, `ui/Skeleton` | ad-hoc centered spinners |
| Nothing to show | `ui/EmptyState` (`icon`, `title`, `description`, `#actions`) | ad-hoc emoji + h3 + p blocks |
| Popup menu | `ui/DropdownMenu` | hand-rolled `absolute right-0 mt-2 …` menus |
| User initials | `ui/Avatar` | duplicated gradient circles |
| Tabular data | `ui/DataTable` (or `Table`/`Th`/`Td` primitives) | copying `<table>` class sets |
| Settings line (label, description, control) | `ui/SettingsRow` | ad-hoc `flex justify-between p-4` rows |
| Page title, description, actions | `layout/PageHeader` | ad-hoc `h2 text-base font-bold` + `p text-xs` |
| Scrollable page container | `layout/PageShell` | repeating `h-full overflow-y-auto pb-20 pr-1` |

Status: all primitives above exist in `src/components/ui/` except `layout/PageShell` and `layout/PageHeader`
(still to be created). A missing primitive must be **created the first time it is needed** – never inline
the pattern "just this once".

Primitive API notes:
- `Input`, `Select`, `Textarea` take `size="sm" | "md"`, `label`, `hint`, `error`. `class`/`style` go to the
  wrapper, every other attribute (`data-testid`, `aria-*`, `min`, listeners) is forwarded to the native control.
  Without a visible `label`, pass `aria-label`.
- `Select` with `options` emits the option's original value type (numbers stay numbers); with slotted
  `<option>`s it emits strings. React to changes via `@update:model-value`, never via native `@change`
  (it fires before the model updates).
- `Switch` forwards attributes to the switch button – give it `label` or `aria-label`.
- `DataTable` customizes cells via `#cell-<key>` slots; `DropdownMenu` items are `DropdownMenuItem`
  (`to` for links, `@select` for actions).
- Never recolour a variant with utility classes (`class="text-rose-600"` on a Button) – the result depends
  on CSS order. Add or use a variant instead (e.g. `Button variant="danger-ghost"`).

Raw `<button>` is acceptable only inside `src/components/ui/` and for fully custom interactive surfaces
(e.g. an image tile that is itself the click target). Such cases need an `aria-label` and a visible
focus style (`focus-visible:ring-2 focus-visible:ring-sky-500/40`).

## 3. Design tokens

Do not invent new values. Pick from the scales below; if a value is missing, add it to `src/style.css`
(`@theme`) in a dedicated change and document it here.

### Colour roles
| Role | Palette | Usage |
|---|---|---|
| Neutral | `slate` | text, borders, surfaces |
| Accent / primary | `sky` (gradient `from-sky-500 to-blue-600` only in `Button variant="primary"`) | primary actions, active nav, focus rings, selection |
| Danger | `rose` | destructive actions, errors |
| Warning / cost | `amber` | warnings, token/cost display |
| Success | `emerald` | success, "active"/"online" states |
| Secondary highlight | `violet` | Agentic Mode / reasoning features only |

- `indigo`, `blue` (outside the primary gradient), `purple`, `cyan`, `teal`, `pink`, `red`, `green`,
  `orange`, `yellow` are **not** used in new code.
- Every colour utility that renders in light mode needs its `dark:` counterpart – or, preferably, lives
  inside a primitive that already handles both modes.
- Text colours: primary `text-slate-900 dark:text-white`, secondary `text-slate-600 dark:text-slate-300`,
  muted `text-slate-500 dark:text-slate-400`. Do not use `text-slate-500` without a `dark:` pair.

### Typography
| Token | Class | Usage |
|---|---|---|
| Page title | `text-lg font-bold` | `PageHeader` title |
| Section title | `text-sm font-semibold` | Section/tab headings, Card headers |
| Body | `text-sm` | default UI text, form controls (`size="md"`) |
| Small | `text-xs` | dense UI, compact controls (`size="sm"`), descriptions |
| Micro | `text-2xs` (theme token in `src/style.css`, 11px) | metadata, counters, timestamps |
| Overline | `text-2xs font-semibold uppercase tracking-wider` | field labels via `FormField` only |

- Arbitrary font sizes (`text-[10px]`, `text-[11px]`, `text-[9px]`, `text-[8px]`) are forbidden in new code.
  Nothing smaller than 11px (`text-2xs`) except numeric badges inside 16px dots.
- Use heading elements semantically: one `h1`/`h2` per page via `PageHeader`, `h3` for sections.

### Radius
| Element | Radius |
|---|---|
| Page panels, Cards, Modals, Drawers | `rounded-2xl` |
| Buttons (sm/md/lg), form controls `size="md"`, menus, list items | `rounded-xl` |
| Compact controls (`Button size="xs"`, form controls `size="sm"`, IconButton xs/sm), chips | `rounded-lg` |
| Pills, badges, avatars, nav links | `rounded-full` |

`rounded-md` and `rounded-3xl` are not used.

### Spacing
- Stick to the Tailwind 4px scale; no half steps finer than `.5` and no arbitrary values (`p-[13px]`).
- Page sections: `space-y-6`; within a Card/section: `space-y-4`; form fields: `space-y-3`;
  inline controls: `gap-2`.
- Responsive gutters are owned by `AppLayout` / `PageShell` – views do not add their own outer padding.

### Surfaces & effects
- One surface style per level: app background (AppLayout) → panel (`Card glass`) → inset
  (`bg-slate-100 dark:bg-slate-800/60`). Do not nest glass panels inside glass panels.
- `backdrop-blur` only on elements that float over content (header, sticky bars, modals, drawers,
  image overlays). Not on static panels inside scroll containers.
- Images are the hero of this app: avoid coloured backgrounds, glows or gradients behind image grids.

## 4. Icons

- Use `lucide-vue-next` exclusively: `import { Trash2 } from 'lucide-vue-next'`.
- Sizes: `size-4` (16px) inside buttons/inputs, `size-3.5` in dense lists, `size-5` in headers/empty states.
- No emoji as UI icons, no hand-written `<svg>` paths in feature components (brand logos excepted,
  stored as assets in `public/`).
- Decorative icons get `aria-hidden="true"`; icon-only controls go through `IconButton`.

## 5. Page layout

Every authenticated view follows this skeleton:

```vue
<PageShell>                      <!-- owns scroll, gutters, bottom padding -->
  <PageHeader title="…" description="…">
    <template #actions>…</template>
  </PageHeader>
  <!-- loading → LoadingState / Skeleton, empty → EmptyState, else content -->
</PageShell>
```

- Exception: full-height workspaces (Generate studio) may use `PageShell :scroll="false"` and manage
  inner scroll areas themselves.
- Every list/grid view must handle all three states: **loading**, **empty** (with a call to action),
  **error** (toast + inline retry where sensible).
- Navigation must be reachable at every breakpoint. Anything hidden with `hidden md:flex` needs a
  mobile equivalent (menu, bottom bar or drawer).
- There is exactly one account menu (header). Do not add parallel account/navigation entry points.

## 6. Overlays & accessibility

- `Modal` / `Drawer` must provide `role="dialog"`, `aria-modal="true"`, `aria-labelledby` (title),
  focus trap, focus return to the trigger, and stacking-aware Escape + scroll-lock handling
  (only the top-most overlay reacts). Implement this once in a shared composable (`useOverlayStack`),
  never per component.
- Every interactive element is keyboard-reachable and has a visible `focus-visible` ring.
- Icon-only controls need `aria-label`; `title` alone is not sufficient.
- Colour is never the only carrier of state (add text, icon or `aria-*`).
- Respect `motion-safe:` for non-essential animations (scale/translate hover effects, pulses).

## 7. Vue/TypeScript conventions

- `<script setup lang="ts">`, typed `defineProps<…>()` with `withDefaults`, typed `defineEmits`.
- Form primitives support `v-model` via `modelValue` / `update:modelValue`; prefer `defineModel()` for new ones.
- Variant/size classes live in a typed map (`Record<Variant, string>`), not long `switch` chains or
  string concatenation scattered through templates.
- No `<style>` blocks and no `style="…"` except for runtime-computed values (sizes, positions,
  aspect ratios). Global CSS lives only in `src/style.css`.
- Components that have `data-testid` attributes keep them when refactored (Playwright depends on them).
- All UI text in English (see root rules).

## 8. Checklist before finishing a frontend change

1. Did I use an existing primitive for every button, input, select, dialog, badge, icon?
2. Did I introduce a class string that already exists elsewhere? → extract.
3. Only allowed colours, radii, font sizes (no `text-[Npx]`, no new accent colours)?
4. Light **and** dark mode checked?
5. Loading / empty / error states present?
6. Works at 375px width and with keyboard only?
7. `npm run build` (runs `vue-tsc`) passes from `frontend/`.
8. Playwright specs touching the changed area still pass.
