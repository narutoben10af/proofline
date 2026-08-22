# Theme inventory

Source: `frontend/src/styles.css` and `.superdesign/design-system.md`.

```css
:root {
  font-family: Inter, ui-sans-serif, system-ui, sans-serif;
  color: #191815;
  background: #f7f4ee;
  --paper: #f7f4ee;
  --surface: #fffdf8;
  --wash: #efeae1;
  --ink: #191815;
  --muted: #625f58;
  --rule: #d8d2c8;
  --red: #b52d24;
  --red-wash: #f6e2de;
  --green: #2f704c;
  --green-wash: #e3eee6;
  --amber: #815000;
}
```

Display type is Source Serif 4/Georgia; UI and data type is Inter/system sans. Keep warm paper and ink as the dominant language. Add only restrained lavender/ochre accents for MagicFin focus/progress states when they pass WCAG AA for text. Focus uses a visible 2px outline. Motion is 140–220ms and removed under `prefers-reduced-motion: reduce`.
