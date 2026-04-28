# Mode Selector

Choose exactly one operating mode before producing deliverables.

## `greenfield_spec`
Use when the user is designing a new product, feature, or major flow from scratch.

Required inputs:
- product statement or user problem
- primary user or audience
- core jobs to be done
- main constraints or risks

Primary outputs:
- `DesignBriefV1`
- `ExperienceMapV1`
- `FlowSpecV1`
- `InteractionSpecV1`
- `VisualSystemV1`
- `MotionAccessibilityV1`
- `HandoffQAPackV1`

## `ux_audit`
Use when the user already has a surface, layout, or implementation and wants critique plus fixes.

Required inputs:
- current UI description, screenshots, or code context
- target users or task context
- known pain points if available

Primary outputs:
- `DesignCritiqueV1`
- `ExperienceMapV1`
- `InteractionSpecV1`
- `HandoffQAPackV1`

## `design_system_uplift`
Use when the user needs tokens, components, states, or governance for a UI system.

Required inputs:
- existing product or component context
- current inconsistencies or goals
- target platforms

Primary outputs:
- `VisualSystemV1`
- `MotionAccessibilityV1`
- `HandoffQAPackV1`
- supporting `DesignBriefV1` when context is weak

## `handoff_translation`
Use when the user wants design-to-dev handoff or web-to-iOS and visionOS translation.

Required inputs:
- existing spec, wireframe, or implemented UI
- target implementation surface
- constraints or parity requirements

Primary outputs:
- `InteractionSpecV1`
- `VisualSystemV1`
- `MotionAccessibilityV1`
- `HandoffQAPackV1`

## Tie Breakers
- New feature plus no existing UI: `greenfield_spec`
- Existing UI plus critique request: `ux_audit`
- Component or tokens first: `design_system_uplift`
- Platform adaptation or dev-ready translation: `handoff_translation`
