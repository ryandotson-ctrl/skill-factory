# Output Contracts

Use these contracts to keep the skill deterministic and implementation-ready.

## Mode Mapping
- `greenfield_spec`: `DesignBriefV1`, `ExperienceMapV1`, `FlowSpecV1`, `InteractionSpecV1`, `VisualSystemV1`, `MotionAccessibilityV1`, `HandoffQAPackV1`
- `ux_audit`: `DesignCritiqueV1`, `ExperienceMapV1`, `InteractionSpecV1`, `HandoffQAPackV1`
- `design_system_uplift`: `DesignBriefV1` when needed, `VisualSystemV1`, `MotionAccessibilityV1`, `HandoffQAPackV1`
- `handoff_translation`: `InteractionSpecV1`, `VisualSystemV1`, `MotionAccessibilityV1`, `HandoffQAPackV1`

## `DesignBriefV1`
- product_statement
- primary_users
- user_contexts
- jobs_to_be_done
- success_metrics
- constraints
- risks
- non_goals
- selected_style_mode

## `ExperienceMapV1`
- information_architecture
- navigation_model
- naming_rules
- reduction_log
- content_priority_notes

## `FlowSpecV1`
- core_tasks
- step_by_step_flows
- state_requirements
- critique_pass
- revised_flow

## `InteractionSpecV1`
- surface_list
- interactions
- latency_handling
- error_prevention
- recovery_paths
- trust_patterns
- permission_or_confirmation_rules

## `VisualSystemV1`
- typography_tokens
- spacing_tokens
- radius_tokens
- elevation_tokens
- color_tokens
- motion_tokens
- css_variable_guidance
- component_inventory
- density_modes

## `MotionAccessibilityV1`
- motion_principles
- allowed_scenarios
- duration_ranges
- easing_guidance
- reduced_motion_rules
- keyboard_and_focus_rules
- contrast_and_readability_checks

## `DesignCritiqueV1`
- audit_target
- scorecard
- top_5_fixes
- severity_ordering
- non_regression_notes

## `HandoffQAPackV1`
- component_api_expectations
- responsive_rules
- breakpoint_guidance
- qa_checklist
- regression_risks
- do_not_regress_list

## Delivery Rules
- Keep the output sectionized and scannable.
- Prefer short paragraphs plus flat lists over long prose.
- Preserve the skill's existing care, accessibility, and edge-case discipline.
