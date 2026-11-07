---
type: llm
focus: trace
---
Judge only the JavaScript and XML files the assistant WROTE (Write/Edit tool inputs), not documentation it read.
Pass only if all hold:
1. the component declares props with `props = useProps({...})` (spreading `standardFieldProps` is fine) and does
   NOT use `static props` / `static defaultProps`;
2. it does not import or call `useState`, `reactive`, `useRef` or `useExternalListener`;
3. the OWL template refers to component members with `this.` (e.g. `this.props.readonly`) and uses `t-out`, not `t-esc`;
4. icons, if any, use `<i class="oi" data-icon="..."/>`, not Font Awesome `fa fa-*`;
5. the widget is registered with `registry.category("fields").add("rating_stars", ...)` and supports integer fields.
