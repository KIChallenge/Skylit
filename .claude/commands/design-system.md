---
description: Set up the design system, app shell and styleguide page before any feature UI
---

Set up the design system for: $ARGUMENTS

Read `docs/PITCH.md` first: the demo flow decides which screens and components matter.

1. Pick a visual direction that fits the domain and its users, in 3 lines. For public-sector, health or insurance users: calm, trustworthy, accessible, modern — not flashy. Wait for a yes.
2. Tokens, in one tokens file (CSS variables mapped into the Tailwind theme):
   - Colours: one brand accent used sparingly (primary action, highlights), a neutral scale, and semantic success, warning, danger and info. Light theme. Check AA contrast for text.
   - Typography: one font family (Inter or Geist), base 16 px, a short type scale, large sizes (28–40 px) for key results and numbers, tabular figures for numbers.
   - Spacing on an 8 px grid, one radius (8–12 px), subtle borders over heavy shadows, a max content width.
3. Components: initialise shadcn/ui and add only what the demo needs (for example button, card, input, textarea, badge, table, tabs, dialog, skeleton, tooltip, sonner). Use the shadcn MCP server to look up components. Use lucide icons. Add `framer-motion` for animations.
4. App shell: header with the product name as a simple wordmark, favicon, page title, main content area, and a footer or side panel only if the demo needs one.
5. A `/styleguide` page that shows every token and component, including loading, empty and error states.
6. Fill `docs/DESIGN.md`: direction, tokens, components, screen list from the demo flow, and a short do/don't list.
7. Start the app, open `/styleguide` and the home page with the playwright MCP server at 1440×900, and fix anything that looks off.
8. Log the choices with the `decision` command.

Build no features. This task only gives every later UI task a shared base.
