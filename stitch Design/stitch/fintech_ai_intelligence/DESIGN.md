---
name: Fintech AI Intelligence
colors:
  surface: '#101419'
  surface-dim: '#101419'
  surface-bright: '#36393f'
  surface-container-lowest: '#0a0e13'
  surface-container-low: '#181c21'
  surface-container: '#1c2025'
  surface-container-high: '#262a30'
  surface-container-highest: '#31353b'
  on-surface: '#e0e2ea'
  on-surface-variant: '#bacac1'
  inverse-surface: '#e0e2ea'
  inverse-on-surface: '#2d3136'
  outline: '#85948c'
  outline-variant: '#3c4a43'
  surface-tint: '#2fe0aa'
  primary: '#44edb7'
  on-primary: '#003828'
  primary-container: '#00d09c'
  on-primary-container: '#00533c'
  inverse-primary: '#006c4f'
  secondary: '#bfc7d6'
  on-secondary: '#29313c'
  secondary-container: '#424a56'
  on-secondary-container: '#b1b9c7'
  tertiary: '#cad4e3'
  on-tertiary: '#27313d'
  tertiary-container: '#aeb8c7'
  on-tertiary-container: '#3f4955'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#59fdc5'
  primary-fixed-dim: '#2fe0aa'
  on-primary-fixed: '#002116'
  on-primary-fixed-variant: '#00513b'
  secondary-fixed: '#dbe3f2'
  secondary-fixed-dim: '#bfc7d6'
  on-secondary-fixed: '#141c27'
  on-secondary-fixed-variant: '#3f4753'
  tertiary-fixed: '#d9e3f3'
  tertiary-fixed-dim: '#bdc7d7'
  on-tertiary-fixed: '#121c27'
  on-tertiary-fixed-variant: '#3e4854'
  background: '#101419'
  on-background: '#e0e2ea'
  surface-variant: '#31353b'
typography:
  headline-xl:
    fontFamily: Geist
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.05em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  container-max-width: 1200px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
---

## Brand & Style
The brand personality of the design system is authoritative yet approachable—combining the precision of a financial institution with the fluidity of a modern AI assistant. It targets sophisticated investors who value clarity and speed. 

The visual style is **Modern Corporate with Glassmorphic accents**. It leverages deep-sea dark tones to reduce eye strain during long research sessions, using vibrant "Accent Green" hits to signify growth and financial health. The interface takes inspiration from high-end analytical tools, utilizing translucent layers and subtle luminescence to create a sense of depth and technical sophistication.

## Colors
The palette is built on a foundation of deep neutrals to provide maximum contrast for financial data.

- **Background (#0B0F14):** The base canvas for all views.
- **Secondary Surface (#141A22):** Used for persistent sidebars, navigation bars, and grouping elements.
- **Card Surface (#1A222D):** The primary container color for content modules and AI responses.
- **Accent Green (#00D09C):** Reserved for primary actions, success states, and indicating positive market trends.
- **Text Primary (#FFFFFF):** Used for headlines and critical data points.
- **Text Secondary (#AAB4C3):** Used for supporting text, labels, and metadata to maintain visual hierarchy.

## Typography
This design system utilizes **Geist** for its technical precision and exceptional legibility in dark environments. 

- **Scale:** High contrast between headlines and body text ensures that financial figures stand out.
- **Weight:** Medium (500) and Semi-bold (600) weights are used for UI labels to ensure they remain crisp against dark backgrounds.
- **Spacing:** Headlines use a slight negative letter spacing to feel more "locked-in" and editorial, while labels use expanded spacing for better scannability at small sizes.

## Layout & Spacing
The system employs a **12-column fluid grid** for desktop and a **4-column grid** for mobile. 

- **Rhythm:** An 8px spacing system is the default, but a 4px "half-step" is permitted for tight data tables and dense information clusters.
- **AI Chat Layout:** The chat interface is centered within a 800px max-width container to optimize readability and mimic a "document" feel, similar to modern AI research platforms.
- **Margins:** Generous outer margins (40px) on desktop give the application a premium, spacious feel, preventing the interface from feeling cluttered despite the density of financial data.

## Elevation & Depth
Depth is created through **Tonal Layering** and **Glassmorphism** rather than traditional heavy shadows.

- **Layer 0 (Background):** #0B0F14.
- **Layer 1 (Secondary):** #141A22, used for navigation or inset areas.
- **Layer 2 (Cards):** #1A222D with a 1px border (#FFFFFF with 10% opacity) to define edges.
- **Layer 3 (Modals/Overlays):** Utilizes backdrop-blur (20px) and a slightly lighter fill.
- **Glows:** Primary buttons and the active AI search bar feature a "soft bloom" effect using the Accent Green (#00D09C) at 20% opacity with a 30px blur radius.

## Shapes
The design system uses a **consistent 20px corner radius** for all primary containers and cards to create a soft, approachable aesthetic that balances the "coldness" of dark mode and finance.

- **Base Components:** 8px radius for buttons and input fields.
- **Cards & Modals:** 20px radius.
- **Badges/Chips:** Fully pill-shaped to contrast against the structured card layouts.

## Components

### Glowing Search Bar
The central entry point for the AI. It features a persistent 1px border of Accent Green and a subtle outer glow. When focused, the glow intensifies, and the background utilizes a glassmorphic blur to lift it above the content.

### Glass Cards
Content containers should use the #1A222D surface color with 80% opacity and a `backdrop-filter: blur(12px)`. This is essential for AI-generated responses to feel integrated into the "intelligence" layer of the app.

### Verified Source Badges
Small, pill-shaped components used in AI citations. They feature a #00D09C background at 15% opacity with a solid #00D09C icon, indicating the data is pulled from a reliable regulatory or fund house source.

### Compliance Warning States
Financial advice requires a distinct visual language. Compliance warnings should use a secondary card style with a #FFB000 (Warning Yellow) left-hand border accent and a Geist Mono font for the disclaimer text to denote a "legal/systemic" voice.

### Primary Buttons
Solid #00D09C fill with #0B0F14 (Background) text. No shadows are used here; instead, an inner highlight on the top edge provides a tactile, "clickable" feel.