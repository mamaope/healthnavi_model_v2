# HealthNavi AI - Design System Documentation

## 🎨 Design Philosophy

### Core Principles
1. **Medical-Grade Professionalism** - Trust-building through consistent, calm aesthetics
2. **Accessibility First** - WCAG AAA compliance for all users
3. **Performance Optimized** - Minimal re-renders, lazy loading, optimized animations
4. **Responsive by Default** - Mobile-first approach with progressive enhancement

---

## 🎨 Color System

### Primary Colors (Medical Teal)
- **Purpose**: Calm, trustworthy, medical professionalism
- **Usage**: Primary actions, links, active states, brand elements
- **Psychology**: Teal combines the calming properties of blue with the renewal qualities of green

```css
--primary-50: #f0fdfa   /* Lightest - backgrounds */
--primary-500: #14b8a6  /* Brand color - Medical Teal */
--primary-600: #0d9488  /* Primary actions */
--primary-900: #134e4a  /* Darkest - text */
```

### Secondary Colors (Soft Green)
- **Purpose**: Healing, wellness, positive outcomes
- **Usage**: Success messages, completed actions, health indicators
- **Psychology**: Green represents growth, health, and vitality

```css
--secondary-50: #f0fdf4
--secondary-500: #22c55e
--secondary-700: #15803d
```

### Accent Colors (Warm Coral)
- **Purpose**: Attention, important actions, engagement
- **Usage**: Call-to-action buttons, highlights, important notices
- **Psychology**: Warm and inviting, draws attention without alarm

```css
--accent-50: #fff7ed
--accent-500: #f97316
--accent-700: #c2410c
```

### Error Colors (Muted Red)
- **Purpose**: Errors and critical alerts without causing alarm
- **Usage**: Error messages, validation feedback, critical warnings
- **Psychology**: Red for urgency, muted for professionalism

```css
--error-50: #fef2f2
--error-500: #ef4444
--error-700: #b91c1c
```

### Warning Colors (Soft Amber)
- **Purpose**: Caution, review needed
- **Usage**: Warning messages, attention-required items
- **Psychology**: Yellow/amber for caution, soft for approachability

```css
--warning-50: #fefce8
--warning-500: #eab308
--warning-700: #a16207
```

### Neutral Colors (Warm Gray)
- **Purpose**: Base colors for text, backgrounds, borders
- **Usage**: All UI elements, provides warmth and comfort
- **Note**: Warmer than pure gray for a more inviting feel

```css
--neutral-0: #ffffff    /* Pure white */
--neutral-50: #fafaf9   /* Warm off-white */
--neutral-500: #78716c  /* Mid-tone gray */
--neutral-900: #1c1917  /* Deep charcoal */
```

---

## 📐 Spacing System

### Scale (8px base unit)
```css
--space-1: 0.25rem  /* 4px  - Tight spacing */
--space-2: 0.5rem   /* 8px  - Base unit */
--space-3: 0.75rem  /* 12px - Small gaps */
--space-4: 1rem     /* 16px - Standard spacing */
--space-6: 1.5rem   /* 24px - Medium spacing */
--space-8: 2rem     /* 32px - Large spacing */
--space-12: 3rem    /* 48px - Section spacing */
```

### Usage Guidelines
- **Component padding**: Use --space-3 to --space-4
- **Section gaps**: Use --space-6 to --space-8
- **Page margins**: Use --space-8 to --space-12

---

## 🔤 Typography

### Font Family
```css
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto
--font-mono: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono'
```

### Type Scale
```css
--font-size-xs: 0.75rem    /* 12px - Small labels */
--font-size-sm: 0.875rem   /* 14px - Body text small */
--font-size-base: 1rem     /* 16px - Body text */
--font-size-lg: 1.125rem   /* 18px - Large body */
--font-size-xl: 1.25rem    /* 20px - Small headings */
--font-size-2xl: 1.5rem    /* 24px - Section headings */
--font-size-3xl: 1.875rem  /* 30px - Page headings */
--font-size-4xl: 2.25rem   /* 36px - Hero text */
--font-size-5xl: 3rem      /* 48px - Large hero */
```

### Font Weights
```css
--font-weight-normal: 400    /* Body text */
--font-weight-medium: 500    /* Emphasis */
--font-weight-semibold: 600  /* Subheadings */
--font-weight-bold: 700      /* Headings */
```

### Line Heights
```css
--line-height-tight: 1.25    /* Headings */
--line-height-snug: 1.375    /* Subheadings */
--line-height-normal: 1.5    /* Body text */
--line-height-relaxed: 1.625 /* Long-form content */
```

---

## 🎭 Component Library

### Buttons

#### Primary Button
```html
<button class="btn btn-primary">Get Started</button>
```
- **Usage**: Primary actions, CTAs
- **States**: Default, hover, active, disabled, loading

#### Secondary Button
```html
<button class="btn btn-outline">Sign In</button>
```
- **Usage**: Secondary actions, less emphasis
- **States**: Default, hover, active, disabled

#### Icon Button
```html
<button class="btn-icon">
    <i class="fas fa-plus"></i>
</button>
```
- **Usage**: Compact actions, toolbars
- **Min size**: 44px × 44px (touch target)

### Cards

#### Message Card (AI Response)
```html
<div class="ai-message">
    <div class="message-content">
        <!-- Content -->
    </div>
</div>
```
- **Features**: Gradient background, border accent, hover effect
- **Spacing**: Generous padding for readability

#### Message Card (User)
```html
<div class="user-message">
    <div class="message-content">
        <!-- Content -->
    </div>
</div>
```
- **Style**: Primary color background, rounded corners
- **Alignment**: Right-aligned

### Forms

#### Input Field
```html
<div class="form-group">
    <label for="email">Email</label>
    <input type="email" id="email" required>
</div>
```
- **Features**: Focus states, validation feedback
- **Accessibility**: Labels, ARIA attributes

#### Textarea
```html
<textarea 
    id="messageInput" 
    placeholder="Type your message..."
    rows="1"
    aria-label="Message input"
></textarea>
```
- **Features**: Auto-resize, character counter
- **Max height**: 120px with scroll

---

## 🎬 Animations & Transitions

### Timing Functions
```css
--transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1)
--transition-normal: 300ms cubic-bezier(0.4, 0, 0.2, 1)
--transition-slow: 500ms cubic-bezier(0.4, 0, 0.2, 1)
```

### Common Animations

#### Fade In
```css
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
```
- **Usage**: Message appearance, content loading
- **Duration**: 300ms

#### Bounce (Loading)
```css
@keyframes bounce {
    0%, 80%, 100% { transform: scale(0); }
    40% { transform: scale(1); }
}
```
- **Usage**: Loading indicators
- **Duration**: 1400ms

#### Pulse (Skeleton)
```css
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
```
- **Usage**: Skeleton screens, loading states
- **Duration**: 1500ms

---

## 🌓 Theme System

### Light Theme (Default)
```css
--bg-primary: #ffffff
--bg-secondary: #f9fafb
--text-primary: #111827
--text-secondary: #4b5563
```

### Dark Theme
```css
[data-theme="dark"] {
    --bg-primary: #111827
    --bg-secondary: #1f2937
    --text-primary: #f9fafb
    --text-secondary: #d1d5db
}
```

### Theme Toggle
- **Location**: Header (all users), Sidebar (authenticated)
- **Persistence**: localStorage
- **System Preference**: Auto-detect on first visit

---

## ♿ Accessibility

### WCAG Compliance
- **Level**: AAA target
- **Contrast Ratios**: 
  - Normal text: 7:1 minimum
  - Large text: 4.5:1 minimum

### Keyboard Navigation
- **Tab Order**: Logical flow through interactive elements
- **Focus Indicators**: 2px outline, primary color
- **Skip Links**: Jump to main content

### Screen Readers
- **ARIA Labels**: All interactive elements
- **Semantic HTML**: Proper heading hierarchy
- **Alt Text**: All images and icons

### Reduced Motion
```css
@media (prefers-reduced-motion: reduce) {
    * {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }
}
```

---

## 📱 Responsive Design

### Breakpoints
```css
/* Mobile First Approach */
@media (min-width: 480px)  { /* Small devices */ }
@media (min-width: 768px)  { /* Tablets */ }
@media (min-width: 1024px) { /* Desktops */ }
@media (min-width: 1280px) { /* Large screens */ }
```

### Touch Targets
- **Minimum Size**: 44px × 44px (Apple/WCAG)
- **Spacing**: 8px minimum between targets
- **Hover States**: Disabled on touch devices

---

## 🚀 Performance

### Optimization Strategies
1. **CSS Variables**: Dynamic theming without JS
2. **GPU Acceleration**: transform and opacity for animations
3. **Lazy Loading**: Images and components
4. **Code Splitting**: Route-based chunks
5. **Minimal Re-renders**: Memoization, pure components

### Loading States
- **Skeleton Screens**: Content placeholders
- **Spinner**: Inline loading indicators
- **Progress Bars**: Long operations
- **Empty States**: No data scenarios

---

## 📦 Component Organization

### File Structure
```
frontend/
├── index.html          # Main HTML structure
├── style.css           # Design system + components
├── script.js           # Application logic
├── auth.html           # Authentication page
├── auth.js             # Auth logic
└── DESIGN_SYSTEM.md    # This file
```

### Naming Conventions
- **BEM-inspired**: `.component-element--modifier`
- **Utility Classes**: `.btn`, `.card`, `.container`
- **State Classes**: `.active`, `.disabled`, `.loading`

---

## 🎯 Best Practices

### Do's ✅
- Use CSS variables for theming
- Follow spacing system consistently
- Maintain accessibility standards
- Test on multiple devices
- Optimize for performance
- Document component usage

### Don'ts ❌
- Hardcode colors or spacing
- Skip accessibility features
- Ignore responsive design
- Use inline styles
- Forget loading states
- Neglect keyboard navigation

---

## 🔄 Future Enhancements

### Planned Improvements
1. **Component Library**: Extract reusable React/Vue components
2. **Storybook Integration**: Component documentation and testing
3. **Design Tokens**: JSON-based token system
4. **Icon System**: Custom medical icon set
5. **Animation Library**: Framer Motion integration
6. **Testing**: Visual regression tests

---

## 📚 Resources

### Design Inspiration
- [Material Design](https://material.io/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Shadcn/UI](https://ui.shadcn.com/)
- [Healthcare Design Patterns](https://www.healthdesignchallenge.com/)

### Accessibility
- [WCAG Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [A11y Project](https://www.a11yproject.com/)
- [WebAIM](https://webaim.org/)

### Performance
- [Web.dev](https://web.dev/)
- [Lighthouse](https://developers.google.com/web/tools/lighthouse)

---

**Version**: 2.0  
**Last Updated**: 2025-01-05  
**Maintained by**: HealthNavi AI Team
