# Inbox Janitor Design System & UI/UX Best Practices

**Last Updated:** 2025-11-04
**Status:** Active Reference Document
**Purpose:** Guide all frontend development decisions with proven UI/UX patterns

---

## 📌 When to Reference This Document

**ALWAYS reference during:**
- Building any new page or component
- Making color/typography decisions
- Implementing interactions (hover, focus, transitions)
- Creating forms or settings pages
- Designing mobile layouts
- Adding animations or micro-interactions

**This document provides:**
- Specific Tailwind classes to use
- Code examples for common patterns
- Color palette and typography scale
- HTMX and Alpine.js interaction patterns
- Accessibility requirements

---

## 🎨 Core Design Principles

### 1. The 60-30-10 Color Rule

**60% - Dominant (Neutral Background)**
- Use for: Main backgrounds, content areas
- Classes: `bg-gray-50`, `bg-white`, `bg-gray-100`
- Coverage: Majority of the interface

**30% - Secondary (Structure & Contrast)**
- Use for: Text, borders, dividers, navigation
- Classes: `bg-gray-800`, `text-gray-700`, `border-gray-200`
- Coverage: Structural elements

**10% - Accent (Actions & Highlights)**
- Use for: CTAs, success states, links, important badges
- Classes: `bg-blue-600`, `bg-green-500`, `bg-red-500`
- Coverage: Focal points only

### 2. Trust & Reliability Through Blue

**Why Blue:**
- Conveys trust, security, and professionalism
- Used by banks, healthcare, enterprise SaaS
- Reduces anxiety about granting email access

**Primary Blue Palette:**
```css
colors: {
  primary: {
    50: '#eff6ff',   /* Very light - backgrounds */
    100: '#dbeafe',  /* Light - hover backgrounds */
    500: '#3b82f6',  /* Medium - links, icons */
    600: '#2563eb',  /* Main - Primary CTAs */
    700: '#1d4ed8',  /* Dark - Hover states */
  }
}
```

**Usage:**
- Primary CTA buttons: `bg-blue-600 hover:bg-blue-700`
- Login/OAuth screens: Blue dominant
- Confirmation messages: Blue text/icons
- Dashboard primary elements: Blue accents

### 3. Minimize Cognitive Load

**Strategies:**
- Limit to 2 font families (we use Inter only)
- Maintain clear visual hierarchy (size, weight, color)
- Use whitespace generously (8px spacing system)
- One primary action per screen
- Progressive disclosure (hide complexity until needed)

---

## 🎨 Color System

### Complete Palette

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        // Primary (Trust & Actions)
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb', // Main CTA color
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        // Grays (Structure)
        gray: {
          50: '#f9fafb',
          100: '#f3f4f6',
          200: '#e5e7eb',
          300: '#d1d5db',
          400: '#9ca3af',
          500: '#6b7280',
          600: '#4b5563',
          700: '#374151',
          800: '#1f2937',
          900: '#111827',
        },
      },
    },
  },
}
```

### Action Colors

```html
<!-- Success (positive actions, completed states) -->
<button class="bg-green-500 hover:bg-green-600 text-white">
  ✓ Saved
</button>

<!-- Warning (review items, pending states) -->
<div class="bg-amber-50 border-amber-200 text-amber-800">
  ⚠️ Sandbox mode active
</div>

<!-- Danger (delete actions, errors) -->
<button class="bg-red-600 hover:bg-red-700 text-white">
  Delete Account
</button>

<!-- Neutral (disabled, secondary) -->
<button class="bg-gray-200 text-gray-500 cursor-not-allowed" disabled>
  Unavailable
</button>
```

### Status Badges

```html
<!-- Trash action -->
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
  Trash
</span>

<!-- Archive action -->
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
  Archive
</span>

<!-- Keep action -->
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
  Keep
</span>

<!-- Review action -->
<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
  Review
</span>
```

---

## ✍️ Typography System

### Font Family

**Primary: Inter** (Google Fonts)
- Clean, highly readable at small sizes
- Wide range of weights (300-700)
- Excellent for dashboards and data-heavy UIs

```html
<!-- In base.html -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

```css
/* In Tailwind config */
fontFamily: {
  sans: ['Inter', 'system-ui', 'sans-serif'],
}
```

### Typography Scale

```css
/* Tailwind classes and their use cases */
.text-xs     /* 12px - Helper text, input labels, badges */
.text-sm     /* 14px - Secondary text, table data, timestamps */
.text-base   /* 16px - Body text, form inputs, buttons */
.text-lg     /* 18px - Emphasized text, large buttons */
.text-xl     /* 20px - Section headings, card titles */
.text-2xl    /* 24px - Page titles */
.text-3xl    /* 30px - Hero headlines (landing page only) */
.text-4xl    /* 36px - Landing page hero */
```

### Font Weights

```css
.font-normal    /* 400 - Body text */
.font-medium    /* 500 - Emphasized text, labels */
.font-semibold  /* 600 - Headings, buttons */
.font-bold      /* 700 - Hero text, very important */
```

### Visual Hierarchy Pattern

```html
<div class="space-y-6">
  <!-- Page header -->
  <div class="border-b border-gray-200 pb-5">
    <h1 class="text-2xl font-semibold text-gray-900">Settings</h1>
    <p class="mt-2 text-sm text-gray-600">Manage your email cleanup preferences</p>
  </div>

  <!-- Section -->
  <div class="space-y-4">
    <h2 class="text-xl font-medium text-gray-900">Classification</h2>

    <!-- Subsection -->
    <div class="space-y-2">
      <h3 class="text-base font-medium text-gray-700">Confidence Threshold</h3>
      <p class="text-sm text-gray-600">
        Emails with confidence above this level will be automatically processed
      </p>
    </div>
  </div>
</div>
```

### Reading-Friendly Text

```html
<!-- Max width for readability -->
<div class="max-w-2xl">
  <p class="text-base leading-relaxed text-gray-700">
    Long paragraph text here. The max-w-2xl keeps line length at ~65-75 characters,
    which is optimal for reading. The leading-relaxed gives 1.625 line height.
  </p>
</div>

<!-- Paragraph spacing -->
<div class="space-y-4">
  <p>First paragraph...</p>
  <p>Second paragraph...</p>
</div>
```

---

## 📏 Spacing System

### Base Unit: 8px

```css
/* Tailwind spacing scale (4px base, but use 8px increments) */
.space-y-2   /* 8px */
.space-y-4   /* 16px - Between related content */
.space-y-6   /* 24px - Between sections */
.space-y-8   /* 32px - Between major sections */

.p-4   /* 16px padding */
.p-6   /* 24px padding - Default card padding */
.p-8   /* 32px padding */

.gap-4  /* 16px gap in flexbox/grid */
.gap-6  /* 24px gap */
```

### Common Spacing Patterns

```html
<!-- Page layout -->
<main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <!-- Content -->
</main>

<!-- Card spacing -->
<div class="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
  <!-- Card content -->
</div>

<!-- Section spacing -->
<div class="space-y-8">
  <section>Section 1</section>
  <section>Section 2</section>
</div>
```

---

## 🧩 Component Patterns

### Button System

```html
<!-- Primary button (main CTA) -->
<button class="
  bg-blue-600 text-white
  px-4 py-2 rounded-md
  font-medium
  transition-all duration-150
  hover:bg-blue-700 hover:shadow-md
  active:scale-95
  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2
">
  Enable Action Mode
</button>

<!-- Secondary button (less important actions) -->
<button class="
  bg-white text-gray-700
  border border-gray-300
  px-4 py-2 rounded-md
  font-medium
  transition-all duration-150
  hover:bg-gray-50
  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-500 focus-visible:ring-offset-2
">
  Cancel
</button>

<!-- Danger button (destructive actions) -->
<button class="
  bg-red-600 text-white
  px-4 py-2 rounded-md
  font-medium
  transition-all duration-150
  hover:bg-red-700
  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2
">
  Delete Account
</button>

<!-- Large button (landing page CTA) -->
<button class="
  bg-blue-600 text-white
  px-8 py-4 rounded-lg
  text-lg font-semibold
  min-h-[60px]
  transition-all duration-150
  hover:bg-blue-700 hover:shadow-lg
">
  Connect Your Gmail
</button>
```

### Card Component

```html
<div class="
  bg-white rounded-lg
  border border-gray-200
  shadow-sm
  transition-all duration-200
  hover:shadow-md hover:border-gray-300
  hover:-translate-y-0.5
">
  <!-- Card header (optional) -->
  <div class="border-b border-gray-200 px-6 py-4">
    <h3 class="text-lg font-medium text-gray-900">Card Title</h3>
  </div>

  <!-- Card body -->
  <div class="px-6 py-4 space-y-4">
    Card content goes here
  </div>

  <!-- Card footer (optional) -->
  <div class="border-t border-gray-200 px-6 py-4 bg-gray-50">
    <button class="btn btn-primary">Action</button>
  </div>
</div>
```

### Stats Card

```html
<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition">
  <div class="flex items-center justify-between">
    <div>
      <p class="text-sm font-medium text-gray-600">Emails Cleaned</p>
      <p class="mt-2 text-3xl font-semibold text-gray-900">6,247</p>
    </div>
    <div class="p-3 bg-blue-100 rounded-full">
      <svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
      </svg>
    </div>
  </div>
  <div class="mt-4">
    <span class="text-sm text-green-600">↑ 23% this week</span>
  </div>
</div>
```

### Form Input

```html
<!-- Text input with label -->
<div class="space-y-1">
  <label for="email-input" class="block text-sm font-medium text-gray-700">
    Email Address
  </label>
  <input
    id="email-input"
    type="email"
    class="
      block w-full rounded-md
      border-gray-300
      focus:border-blue-500 focus:ring-blue-500
      text-base
    "
    placeholder="your@email.com"
  />
  <p class="text-xs text-gray-500">
    We'll never share your email with anyone else.
  </p>
</div>

<!-- Range slider with value display -->
<div class="space-y-2" x-data="{ value: 0.85 }">
  <label class="block text-sm font-medium text-gray-700">
    Confidence Threshold
  </label>
  <input
    type="range"
    min="0.5"
    max="1.0"
    step="0.05"
    x-model="value"
    class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
  />
  <div class="flex justify-between text-xs text-gray-500">
    <span>Less strict (0.5)</span>
    <span class="font-medium text-gray-900" x-text="value"></span>
    <span>Very strict (1.0)</span>
  </div>
</div>

<!-- Toggle switch (Alpine.js) -->
<div class="flex items-center justify-between" x-data="{ enabled: true }">
  <div>
    <label class="text-sm font-medium text-gray-900">
      Auto-trash promotions
    </label>
    <p class="text-sm text-gray-500">
      Automatically move promotional emails to trash
    </p>
  </div>

  <button
    @click="enabled = !enabled"
    :class="enabled ? 'bg-blue-600' : 'bg-gray-200'"
    class="relative inline-flex h-6 w-11 items-center rounded-full transition"
  >
    <span :class="enabled ? 'translate-x-6' : 'translate-x-1'"
          class="inline-block h-4 w-4 rounded-full bg-white transition">
    </span>
  </button>
</div>
```

---

## 🎭 HTMX Interaction Patterns

### Global Loading Indicator

```html
<!-- In base.html layout -->
<div id="global-spinner" class="htmx-indicator fixed top-4 right-4 z-50">
  <div class="bg-white rounded-full shadow-lg p-3">
    <svg class="animate-spin h-5 w-5 text-blue-600" viewBox="0 0 24 24">
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
    </svg>
  </div>
</div>

<!-- Set as global indicator -->
<body hx-indicator="#global-spinner">
  <!-- All HTMX requests will show this spinner -->
</body>
```

### Auto-Save Toggle

```html
<button
  hx-post="/api/settings/toggle"
  hx-vals='{"field": "action_mode_enabled", "value": true}'
  hx-swap="none"
  hx-indicator="#save-indicator"
  class="bg-blue-600 text-white px-4 py-2 rounded-md"
>
  Enable
</button>

<span id="save-indicator" class="htmx-indicator text-sm text-green-600">
  ✓ Saved
</span>
```

### Form with Inline Validation

```html
<form
  hx-post="/api/settings/update"
  hx-target="#success-message"
  hx-swap="innerHTML"
  class="space-y-4"
>
  <input
    name="threshold"
    type="range"
    class="w-full"
  />

  <button
    type="submit"
    class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition"
  >
    Save Changes
  </button>

  <div id="success-message"></div>
</form>

<!-- Server returns: -->
<!-- <p class='text-green-600 text-sm'>✓ Settings saved</p> -->
```

### Loading Content on Demand

```html
<!-- Lazy load below-the-fold content -->
<div
  hx-get="/api/old-emails"
  hx-trigger="intersect once"
  hx-swap="outerHTML"
  class="p-6 text-center text-gray-500"
>
  Loading older emails...
</div>
```

### Optimistic UI Update

```html
<div x-data="{ archived: false }">
  <button
    @click="archived = true"
    hx-post="/api/archive/123"
    hx-swap="none"
    :class="archived ? 'bg-green-500 text-white' : 'bg-blue-600 text-white'"
    class="px-4 py-2 rounded-md transition"
  >
    <span x-show="!archived">Archive Email</span>
    <span x-show="archived">✓ Archived</span>
  </button>
</div>
```

### Smooth Transitions

```html
<!-- Add to CSS -->
<style>
.fade-in {
  opacity: 1;
  transition: opacity 300ms ease-in;
}

.fade-in.htmx-added {
  opacity: 0;
}

.fade-out.htmx-swapping {
  opacity: 0;
  transition: opacity 300ms ease-out;
}
</style>

<!-- Use in HTML -->
<div
  hx-get="/api/dashboard-stats"
  hx-trigger="load"
  hx-swap="innerHTML settle:300ms"
  class="fade-in"
>
  Loading stats...
</div>
```

---

## 🏔️ Alpine.js Component Patterns

### Modal with Transitions

```html
<div x-data="{ open: false }">
  <!-- Trigger -->
  <button
    @click="open = true"
    class="text-blue-600 hover:underline"
  >
    View Details
  </button>

  <!-- Modal overlay -->
  <div
    x-show="open"
    @click="open = false"
    x-transition:enter="ease-out duration-300"
    x-transition:enter-start="opacity-0"
    x-transition:enter-end="opacity-100"
    x-transition:leave="ease-in duration-200"
    x-transition:leave-start="opacity-100"
    x-transition:leave-end="opacity-0"
    class="fixed inset-0 bg-gray-900 bg-opacity-50 z-40"
  ></div>

  <!-- Modal panel -->
  <div
    x-show="open"
    @click.away="open = false"
    @keydown.escape.window="open = false"
    x-transition:enter="ease-out duration-300"
    x-transition:enter-start="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
    x-transition:enter-end="opacity-100 translate-y-0 sm:scale-100"
    x-transition:leave="ease-in duration-200"
    x-transition:leave-start="opacity-100 translate-y-0 sm:scale-100"
    x-transition:leave-end="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
    class="fixed inset-0 z-50 flex items-center justify-center p-4"
  >
    <div class="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
      <div class="p-6">
        <button
          @click="open = false"
          class="float-right text-gray-400 hover:text-gray-600"
        >
          ✕
        </button>
        <div id="modal-content">
          Modal content here
        </div>
      </div>
    </div>
  </div>
</div>
```

### Dropdown Menu

```html
<div x-data="{ open: false }" @click.away="open = false">
  <button
    @click="open = !open"
    class="flex items-center space-x-2 text-gray-700 hover:text-gray-900"
  >
    <span>Account</span>
    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
      <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"/>
    </svg>
  </button>

  <div
    x-show="open"
    x-transition:enter="transition ease-out duration-100"
    x-transition:enter-start="opacity-0 scale-95"
    x-transition:enter-end="opacity-100 scale-100"
    x-transition:leave="transition ease-in duration-75"
    x-transition:leave-start="opacity-100 scale-100"
    x-transition:leave-end="opacity-0 scale-95"
    class="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg py-1 z-50 border border-gray-200"
  >
    <a href="/settings" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">
      Settings
    </a>
    <a href="/account" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">
      Account
    </a>
    <a href="/logout" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">
      Logout
    </a>
  </div>
</div>
```

### Help Tooltip

```html
<div x-data="{ tooltip: false }" class="relative inline-block">
  <button
    @click="tooltip = !tooltip"
    @click.away="tooltip = false"
    class="inline-flex items-center justify-center w-5 h-5 text-gray-400 hover:text-gray-600 rounded-full border border-gray-300"
    aria-label="Help"
  >
    ?
  </button>

  <div
    x-show="tooltip"
    x-transition
    class="absolute z-10 w-64 p-3 mt-2 text-sm bg-white border border-gray-200 rounded-lg shadow-lg"
  >
    <button @click="tooltip = false" class="float-right text-gray-400 hover:text-gray-600">
      ✕
    </button>
    <p class="text-gray-700">
      Sandbox mode logs what we <em>would</em> do without actually moving emails.
      This lets you review our decisions safely.
    </p>
  </div>
</div>
```

### Toast Notification System

```html
<!-- Add to base layout -->
<div
  x-data="{
    toasts: [],
    addToast(message, type = 'success') {
      const id = Date.now();
      this.toasts.push({ id, message, type });
      setTimeout(() => {
        this.toasts = this.toasts.filter(t => t.id !== id);
      }, 5000);
    }
  }"
  @toast.window="addToast($event.detail.message, $event.detail.type)"
>
  <!-- Toast container -->
  <div class="fixed top-4 right-4 z-50 space-y-2">
    <template x-for="toast in toasts" :key="toast.id">
      <div
        x-show="true"
        x-transition:enter="transform ease-out duration-300"
        x-transition:enter-start="translate-x-full opacity-0"
        x-transition:enter-end="translate-x-0 opacity-100"
        x-transition:leave="transform ease-in duration-200"
        x-transition:leave-start="translate-x-0 opacity-100"
        x-transition:leave-end="translate-x-full opacity-0"
        :class="{
          'bg-green-50 border-green-200 text-green-800': toast.type === 'success',
          'bg-red-50 border-red-200 text-red-800': toast.type === 'error',
          'bg-blue-50 border-blue-200 text-blue-800': toast.type === 'info'
        }"
        class="max-w-sm w-full border rounded-lg shadow-lg p-4"
      >
        <div class="flex items-center justify-between">
          <span x-text="toast.message" class="text-sm font-medium"></span>
          <button @click="toasts = toasts.filter(t => t.id !== toast.id)" class="text-gray-400 hover:text-gray-600 ml-4">
            ✕
          </button>
        </div>
      </div>
    </template>
  </div>
</div>

<!-- Trigger toast from HTMX -->
<button
  hx-post="/api/settings/save"
  hx-on::after-request="
    if(event.detail.successful) {
      window.dispatchEvent(new CustomEvent('toast', {
        detail: { message: 'Settings saved successfully', type: 'success' }
      }));
    }
  "
>
  Save
</button>
```

---

## 📱 Mobile-First Responsive Design

### Breakpoints

```css
/* Tailwind default breakpoints */
sm: 640px   /* Tablet portrait */
md: 768px   /* Tablet landscape */
lg: 1024px  /* Desktop */
xl: 1280px  /* Large desktop */
```

### Mobile-First Pattern

```html
<!-- Always write mobile styles first, then scale up -->
<div class="
  px-4 py-6           /* Mobile: smaller padding */
  sm:px-6 sm:py-8     /* Tablet: 640px+ */
  lg:px-8 lg:py-10    /* Desktop: 1024px+ */
">
  <!-- Stats cards: stack on mobile, grid on desktop -->
  <div class="
    grid
    grid-cols-1        /* Mobile: single column */
    sm:grid-cols-2     /* Tablet: 2 columns */
    lg:grid-cols-3     /* Desktop: 3 columns */
    gap-4 lg:gap-6
  ">
    <!-- Cards -->
  </div>
</div>
```

### Mobile Navigation

```html
<nav x-data="{ mobileMenuOpen: false }" class="bg-white border-b border-gray-200">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex justify-between h-16">
      <!-- Logo -->
      <div class="flex items-center">
        <span class="text-xl font-semibold text-gray-900">Inbox Janitor</span>
      </div>

      <!-- Desktop nav (hidden on mobile) -->
      <div class="hidden md:flex items-center space-x-4">
        <a href="/dashboard" class="text-gray-700 hover:text-gray-900">Dashboard</a>
        <a href="/settings" class="text-gray-700 hover:text-gray-900">Settings</a>
        <a href="/account" class="text-gray-700 hover:text-gray-900">Account</a>
      </div>

      <!-- Mobile hamburger (hidden on desktop) -->
      <button
        @click="mobileMenuOpen = !mobileMenuOpen"
        class="md:hidden inline-flex items-center justify-center p-2 rounded-md text-gray-700 hover:text-gray-900"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
        </svg>
      </button>
    </div>
  </div>

  <!-- Mobile menu (shown when hamburger clicked) -->
  <div
    x-show="mobileMenuOpen"
    @click.away="mobileMenuOpen = false"
    x-transition
    class="md:hidden border-t border-gray-200"
  >
    <a href="/dashboard" class="block px-4 py-3 text-gray-700 hover:bg-gray-50">Dashboard</a>
    <a href="/settings" class="block px-4 py-3 text-gray-700 hover:bg-gray-50">Settings</a>
    <a href="/account" class="block px-4 py-3 text-gray-700 hover:bg-gray-50">Account</a>
  </div>
</nav>
```

### Touch Targets

```html
<!-- Minimum 44x44px for mobile -->
<button class="min-h-[44px] min-w-[44px] px-4 py-2">
  Tap Me
</button>

<!-- Icon buttons need extra padding -->
<button class="p-3">
  <svg class="w-5 h-5">...</svg>
</button>
```

---

## ♿ Accessibility Patterns

### Focus States

```html
<!-- Always visible focus rings -->
<button class="
  bg-blue-600 text-white px-4 py-2 rounded-md
  focus-visible:outline-none
  focus-visible:ring-2
  focus-visible:ring-blue-500
  focus-visible:ring-offset-2
  transition
">
  Enable Action Mode
</button>

<!-- Link focus states -->
<a href="/settings" class="
  text-blue-600 hover:underline
  focus-visible:outline-none
  focus-visible:ring-2
  focus-visible:ring-blue-500
  focus-visible:rounded
  focus-visible:px-1
">
  Update settings
</a>
```

### Semantic HTML

```html
<!-- Proper heading hierarchy -->
<main>
  <h1>Dashboard</h1>
  <section>
    <h2>Email Statistics</h2>
    <article>
      <h3>This Week</h3>
      <!-- Content -->
    </article>
  </section>
</main>

<!-- Proper form labels -->
<div>
  <label for="threshold-input" class="block text-sm font-medium text-gray-700">
    Confidence Threshold
  </label>
  <input
    id="threshold-input"
    type="range"
    aria-valuemin="0.5"
    aria-valuemax="1.0"
    aria-valuenow="0.85"
    aria-label="Confidence threshold for email classification"
  />
</div>

<!-- Button vs. link -->
<button type="button">Perform action</button> <!-- Interactive element -->
<a href="/page">Navigate to page</a>         <!-- Navigation -->
```

### ARIA Attributes

```html
<!-- Loading states -->
<button
  hx-post="/api/cleanup"
  aria-busy="false"
  hx-on::before-request="this.setAttribute('aria-busy', 'true')"
  hx-on::after-request="this.setAttribute('aria-busy', 'false')"
>
  Start Cleanup
</button>

<!-- Live region for dynamic updates -->
<div
  hx-get="/api/stats"
  hx-trigger="every 10s"
  aria-live="polite"
  aria-atomic="true"
>
  247 emails cleaned today
</div>

<!-- Icon buttons need labels -->
<button aria-label="Close modal">
  ✕
</button>

<!-- Disclosure widgets -->
<button aria-expanded="false" @click="open = !open" :aria-expanded="open">
  Show more
</button>
```

### Skip to Main Content

```html
<!-- Add to top of base.html -->
<a
  href="#main-content"
  class="sr-only focus:not-sr-only focus:absolute focus:top-0 focus:left-0 bg-blue-600 text-white px-4 py-2 z-50"
>
  Skip to main content
</a>

<main id="main-content">
  <!-- Page content -->
</main>
```

---

## 🎬 Micro-interactions & Animations

### Button Hover Effects

```html
<button class="
  bg-blue-600 text-white px-4 py-2 rounded-md
  transition-all duration-150
  hover:bg-blue-700
  hover:shadow-md
  active:scale-95
">
  Enable Action Mode
</button>
```

### Card Hover Effects

```html
<div class="
  bg-white rounded-lg border border-gray-200 p-6
  transition-all duration-200
  hover:shadow-lg hover:border-gray-300
  hover:-translate-y-0.5
">
  <!-- Card content -->
</div>
```

### Loading Skeletons

```css
/* Add to CSS */
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.skeleton {
  background: linear-gradient(
    90deg,
    #f0f0f0 25%,
    #e0e0e0 50%,
    #f0f0f0 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
```

```html
<!-- Loading skeleton -->
<div class="space-y-3">
  <div class="h-4 bg-gray-200 rounded skeleton w-3/4"></div>
  <div class="h-4 bg-gray-200 rounded skeleton w-1/2"></div>
  <div class="h-4 bg-gray-200 rounded skeleton w-5/6"></div>
</div>
```

---

## 🎯 Empty States

### No Data Pattern

```html
<div class="text-center py-12">
  <svg class="mx-auto h-24 w-24 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
  </svg>

  <h3 class="mt-6 text-xl font-medium text-gray-900">
    Your inbox is being analyzed
  </h3>

  <p class="mt-2 text-sm text-gray-600 max-w-sm mx-auto">
    Inbox Janitor is learning your email patterns. We'll start cleaning up promotional emails within 24 hours.
  </p>

  <div class="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
    <button class="bg-blue-600 text-white px-5 py-2.5 rounded-md hover:bg-blue-700 transition">
      Review Settings
    </button>
    <button class="bg-white text-gray-700 px-5 py-2.5 rounded-md border border-gray-300 hover:bg-gray-50 transition">
      Learn How It Works
    </button>
  </div>
</div>
```

---

## 📊 Dashboard Layout Pattern

```html
<div class="min-h-screen bg-gray-50">
  <!-- Top navigation -->
  <nav class="bg-white border-b border-gray-200">
    <!-- Nav content -->
  </nav>

  <!-- Main content -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Page header -->
    <div class="mb-8">
      <h1 class="text-2xl font-semibold text-gray-900">Dashboard</h1>
      <p class="mt-2 text-sm text-gray-600">Welcome back! Here's what's happening with your inbox.</p>
    </div>

    <!-- Stats cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      <!-- Stat card 1 -->
      <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div class="text-sm font-medium text-gray-500">Emails Cleaned</div>
        <div class="mt-2 text-3xl font-semibold text-gray-900">6,247</div>
        <div class="mt-2 text-sm text-green-600">↑ 23% this week</div>
      </div>
      <!-- More cards -->
    </div>

    <!-- Content area -->
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <!-- Dashboard content -->
    </div>
  </main>
</div>
```

---

## 🔍 Reference Examples

### Exceptional SaaS UI/UX

1. **Linear** - Keyboard shortcuts, smooth animations, command palette
2. **Notion** - Inline editing, progressive disclosure, helpful empty states
3. **Stripe** - Clear visual hierarchy, status badges, smart defaults
4. **Vercel** - Real-time updates, deployment status, dark mode
5. **Superhuman** - Keyboard-first, instant feedback, undo toasts

### Common Patterns

- **Command Palette**: Cmd+K for quick actions (consider for V2)
- **Inline Editing**: Click to edit (for settings in V2)
- **Status Indicators**: Color + icon (green ✓, red ✕, yellow ⚠)
- **Undo Toast**: After every destructive action
- **Empty States**: Educational content + clear CTA

---

## ✅ Pre-Launch Checklist

### Visual Design
- [ ] 60-30-10 color rule applied throughout
- [ ] Inter font loaded and used consistently
- [ ] 8px spacing system maintained
- [ ] All buttons have proper hover states
- [ ] All interactive elements have focus states

### Interactions
- [ ] HTMX loading indicators on all async actions
- [ ] Toast notifications for all important actions
- [ ] Smooth transitions (300ms fade in/out)
- [ ] Optimistic UI updates where appropriate
- [ ] No jarring page reloads

### Mobile
- [ ] All pages tested at 375px width
- [ ] Touch targets minimum 44x44px
- [ ] Hamburger menu works properly
- [ ] No horizontal scrolling
- [ ] Text remains readable when zoomed to 200%

### Accessibility
- [ ] All interactive elements keyboard accessible
- [ ] Focus states visible and clear
- [ ] ARIA labels on icon-only buttons
- [ ] Semantic HTML throughout
- [ ] Color contrast meets WCAG AA (4.5:1)
- [ ] Screen reader tested (NVDA or VoiceOver)

### Performance
- [ ] Tailwind CSS purged (<100KB)
- [ ] Static files cached (1-year headers)
- [ ] Lighthouse performance score >90
- [ ] No render-blocking resources
- [ ] Fast page loads (<2 seconds on 3G)

---

**This design system should be referenced for every frontend decision. When in doubt, look here first!**
