```markdown
# Design System: Terminal Precision & Editorial Depth

## 1. Overview & Creative North Star: "The Kinetic Monolith"
The Creative North Star for this design system is **The Kinetic Monolith**. We are moving away from the "web app" aesthetic toward a "high-performance instrument" feel. It combines the brutal, data-dense utility of a Bloomberg Terminal with the refined, intentional polish of Linear. 

To achieve this, we avoid the "template" look by using **intentional asymmetry** and **tonal density**. Layouts should feel like a machine-etched interface—stable, unmoving, and authoritative. We break the grid not through chaos, but through "High-Contrast Information Scoping," where data is grouped into distinct visual islands that prioritize scanning speed over decorative whitespace.

---

## 2. Colors & Surface Philosophy
The palette is rooted in the deep void of `#0d0f17`. This is a dark-only system where color is used strictly as a functional signal or a structural anchor.

### The "No-Line" Rule (Refined)
While the original brief calls for borders, we elevate this by prohibiting **redundant** 1px solid borders for sectioning large layout blocks. Instead, boundaries for major regions must be defined by **background color shifts** (e.g., a `surface_container_low` sidebar against a `surface` main stage). Use borders (`outline_variant`) only for tactical containment of high-density data within those blocks.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers of dark obsidian. 
- **Base Level (`surface`):** The absolute floor of the application.
- **Structural Level (`surface_container_low`):** Used for persistent sidebars or navigation gutters.
- **Action Level (`surface_container`):** The primary workspace for cards and data tables.
- **Focus Level (`surface_container_high`):** For active states, hovered items, or tertiary details that need to "pop" from the card.

### The "Glass & Gradient" Rule
To prevent the interface from feeling "flat" or "cheap," use **Glassmorphism** for floating overlays (Command Menus, Tooltips). Apply `surface_container_highest` at 80% opacity with a 12px backdrop blur. 
*   **Signature Textures:** Use a subtle linear gradient on primary CTAs—from `primary` (#b7c4ff) to `primary_container` (#6a89ff)—at a 135-degree angle. This adds a "machined metal" sheen that flat colors cannot replicate.

---

## 3. Typography: The Dual-Engine Engine
We utilize a two-font system to separate "narrative" from "computation."

- **The Narrative (Inter):** Used for labels, descriptions, and UI controls. It provides a human-centric legibility. 
    - *Editorial Note:* Use `label-sm` (11px) in **ALL CAPS** with `0.08em` tracking for all metadata. This creates a "stamped" look common in high-end technical equipment.
- **The Computation (JetBrains Mono):** This is the soul of the system. Used for all numbers, prices, timestamps, and ticker symbols. 
    - *Metric Values:* 24px Semi-Bold JetBrains Mono. These are the anchors of the page.

**Hierarchy Strategy:** 
We use extreme scale contrast. A `display-sm` (Space Grotesk) headline might sit directly above a `label-sm` metadata string to create an editorial, "newspaper-from-the-future" hierarchy.

---

## 4. Elevation & Depth: Tonal Layering
In this design system, "up" is "lighter," not "shadowed."

- **The Layering Principle:** Depth is achieved by stacking the surface-container tiers. A `surface_container_highest` element on a `surface` background creates a 3D effect without a single drop shadow.
- **Ambient Glows (Not Shadows):** Traditional shadows are forbidden. Instead, use a **1px Inner Border** for active states using `outline` at 30% opacity to simulate a "beveled" edge that catches light.
- **The Ghost Border:** For non-active containers, the border should be the `outline_variant` token at 20% opacity. It should be barely felt, only visible when the eye looks directly for the boundary.

---

## 5. Components

### Buttons
- **Primary:** `primary` background, `on_primary` text. No shadow. 6px radius (`md`).
- **Secondary:** Transparent background, `outline_variant` border. 
- **Interaction:** On hover, shift background one tier higher (e.g., from `primary` to `primary_fixed`).

### Data Cards & Lists
- **The "No Divider" Rule:** Forbid the use of horizontal lines between list items. Use 8px of vertical whitespace (`1`) or a subtle background shift on hover (`surface_container_high`) to separate content.
- **Padding:** Maintain a strict 16px (`1.75`) internal padding for all cards.

### Input Fields
- **Terminal Style:** Use `surface_container_lowest` for the field background. The border is only visible on `:focus` using the `accent` (#5b7cf7) color.
- **Typography:** Input text must always be JetBrains Mono to reinforce the "entry of data" feel.

### Trading-Specific Components
- **The "Tape" (Price Action):** Use `tertiary` (green) and `error` (red) for price movements. These colors must have a high-chroma "neon" feel against the dark background.
- **Status Badges:** 20px radius (`full`). Background at 15% opacity of the signal color (e.g., 15% `tertiary` for "Success") with a solid 100% opacity text.

---

## 6. Do’s and Don’ts

### Do
- **Do** align all elements to the 8px grid. If an element is off by 1px, the "precision" feel is lost.
- **Do** use JetBrains Mono for any value that can change (numbers, dates, status).
- **Do** use `text_muted` for units (e.g., "1.24 **ETH**") to keep the focus on the value.
- **Do** leverage "asymmetric balance"—it's okay to have a dense data table on the left balanced by a large, airy metric on the right.

### Don't
- **Don't** use shadows. If you need depth, use a lighter background color.
- **Don't** use standard blue for links. Use the `accent` (#5b7cf7) or `primary` (#b7c4ff) tokens.
- **Don't** use rounded corners larger than 10px (`xl`) for main containers. The interface should feel sharp and architectural.
- **Don't** use dividers. If the layout feels cluttered, increase the `Spacing Scale` between elements instead of adding a line.