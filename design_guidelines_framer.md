# Framer.com-Inspired Design System Guidelines (Agency Multi-Tenant & AI Showcase)

## 1. Visual Archetype & Layout Rhythm
- **Core Aesthetic**: Framer-inspired dark obsidian canvas (#090A0F) with refined 1px subtle strokes (`border-white/10` or `#282D3F`), ambient soft glows, and high-precision visual hierarchy.
- **Backgrounds**: Deep void black (`#090A0F`), secondary dark elevated panels (`#11131C`), card containers (`#161924`), and hover states (`#1E2232`).
- **Layout Rhythm**: Asymmetric bento grids (`grid-cols-1 md:grid-cols-8 lg:grid-cols-12`) with expansive section padding (`py-24 lg:py-32`) and breathable block spacing (`gap-6 lg:gap-8`).

## 2. Framer Nav Pill & Sticky Header
- **Floating Pill Nav**: Centered pill container with `rounded-full`, `backdrop-blur-xl bg-[#090A0F]/80 border border-white/10 px-6 py-3 shadow-2xl z-50`.
- **Nav Actions**: Subtle link states with emerald dot hover indicators (`hover:text-emerald-400 transition-colors duration-200`), primary action CTA with shiny emerald glow button (`bg-emerald-500 hover:bg-emerald-400 text-black font-semibold rounded-full px-5 py-2 shadow-[0_0_20px_rgba(16,185,129,0.3)]`).

## 3. Hero & Video Showcase Section
- **Typography Scale**:
  - Main Display Hero H1: `text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.1]` using `Space Grotesk`.
  - Section Titles H2: `text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight` with accent gradients.
  - Subtitles / Lead: `text-lg sm:text-xl text-slate-400 max-w-2xl leading-relaxed`.
  - Badges / Labels: `uppercase tracking-[0.2em] text-xs font-semibold text-emerald-400 bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20`.
- **Video & Live Preview Showcase**:
  - Embedded looping autoplay muted video frames featuring real tenant previews.
  - Interactive overlay controls: Play/Pause, Fullscreen view, Live Subdomain preview links (`tenant.agency.app`).
  - Interactive device frame toggles (Desktop Viewport, Mobile Safari/Chrome Wrapper).

## 4. Feature Bento & Framer Cards
- **Card Anatomy**:
  - Solid surface (#161924) wrapped in 1px crisp border (`border-slate-800 hover:border-emerald-500/40 transition-all duration-300`).
  - Subtle top edge highlight beam or ambient emerald radial gradient bleed (`bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-emerald-500/10 via-transparent to-transparent`).
  - Internal padding: `p-6 sm:p-8`.
- **Interactive Tenant Matrix**:
  - Filterable tabs by industry (SaaS, E-Commerce, Internal Tool, Service Booking, AI Portal).
  - Quick action status indicators: Pulsing Emerald (Active), Amber (Maintenance), Cyan (Handover).

## 5. Master Platform Tabs & Key Features
1. **Master Dashboard**: Real-time tenant management, CPU/RAM/API speed metrics, quick deployment & spin-up modal.
2. **Framer-Style Visual Block Builder**: Drag-and-drop block canvas (Hero, Feature Grid, Pricing, AI Widget), prompt-to-UI AI generator, live iframe preview switcher.
3. **AI Media Studio**:
   - Voice Synthesis (ElevenLabs voice options & audio player waveform).
   - Image Prompt Generator (GPT-Image prompts with style presets).
   - Video Prompt Generator (fal.ai video preview player).
4. **Stripe Billing & Pricing Import**:
   - Tiered plan management (Starter, Pro, Enterprise).
   - Excel / Word file drop zone for pricing table import & automated tiered pricing parser.
5. **Custom Domains & DNS Panel**:
   - Domain binding interface (`app.clientbrand.com`).
   - Interactive DNS Checklist (CNAME, A Record, TXT validation with live status badges).
6. **Public Live Preview Links**:
   - Direct shareable URLs (`preview.agency.app/tenant-id`) with sandbox controls and client feedback panel.

## 6. Motion & Micro-Interactions
- Smooth spring physics or cubic-bezier standard (`transition-all duration-200 ease-out`).
- Hover lift on cards (`hover:-translate-y-1 hover:shadow-[0_12px_30px_rgba(0,0,0,0.5)]`).
- Glowing border beam tracing effect for highlighted/selected tenant apps.

## 7. QA & Accessibility Compliance
- **Testing Attributes**: ALL interactive elements (buttons, inputs, filters, tabs, dropdowns, build cards) MUST include kebab-case `data-testid` attributes (e.g., `data-testid="nav-pill-builder-link"`, `data-testid="ai-media-generate-btn"`).
- **Contrast**: Text contrast strictly follows >4.5:1 ratio over dark background panels.
