---
name: build-workflow
description: Orchestrates the full build pipeline using subagents
---

# Build Workflow

When asked to run the build workflow, follow this pipeline.
Each phase uses a specialized subagent. Wait for each phase to
complete before starting the next, and get user confirmation at
the checkpoints marked with ⏸️.

## Phase 0: Requirements Gathering (product agent) ⏸️
Ask the product subagent to:
1. Interview the user about what they want to build
2. Synthesize the answers and validate with the user
3. Iterate until the user confirms the requirements
4. Write the MRD to `docs/mrd/mrd.md`
**CHECKPOINT: Do NOT proceed until the user confirms the MRD.**

## Phase 1: UI/UX Design (designer agent) ⏸️
Ask the designer subagent to:
1. Read the MRD to understand the product
2. Interview the user about design preferences, visual references, brand
3. Accept and analyze any screenshots, Figma files, or inspiration images
4. Present the design direction and iterate until the user confirms
5. Write the design spec to `docs/design/design-spec.md`
**CHECKPOINT: Do NOT proceed until the user confirms the design spec.**

## Phase 2: Architecture (architect agent) ⏸️
Ask the architect subagent to:
1. Read the MRD from `docs/mrd/mrd.md` as the source of truth
2. Read the design spec from `docs/design/design-spec.md` for UI requirements
3. Design the high-level architecture
4. Write detailed component specs to `docs/specs/`
5. Trace each design decision back to MRD requirements and design spec
6. Update CLAUDE.md with tech stack and project structure
**CHECKPOINT: Show the user the architecture overview. Proceed on confirmation.**

## Phase 3: Write Tests — Red Phase (tester agent)
Ask the tester subagent to run in **Mode 1 (Write Tests)**:
1. Read the MRD for acceptance criteria
2. Read the specs for interface definitions and data models
3. Create test fixtures and shared setup
4. Write tests for every component based on the specs
5. Write a test plan to `docs/tests/test-plan.md`
6. All tests should FAIL at this point — no implementation exists yet

## Phase 4: Implementation — Green Phase (developer agent)
Ask the developer subagent to:
1. Read the specs from `docs/specs/`
2. Read the failing tests in `tests/`
3. Run the tests to see them fail (confirm Red)
4. Implement code to make each test pass, component by component
5. Run tests after each component — track Red → Green progress
6. Refactor for clean code while keeping tests green

## Phase 5: Validation (tester agent)
Ask the tester subagent to run in **Mode 2 (Validate)**:
1. Run the full test suite
2. Add additional edge case tests discovered during review
3. Document any failures as bugs in `docs/bugs/`
4. Report pass/fail summary

## Phase 6: Containerization & CI/CD (devops agent)
Ask the devops subagent to:
1. Create Dockerfile and .dockerignore
2. Create docker-compose.yml (dev and production)
3. Add health check endpoint and graceful shutdown
4. Create CI/CD pipeline
5. Add production logging and request ID middleware
6. Verify the app builds and runs in Docker
7. Write deployment docs to `docs/deployment.md`

## Phase 4: Testing (tester agent)
Ask the tester subagent to:
1. Create test fixtures and shared setup
2. Write and run tests for all components
3. Verify MRD acceptance criteria are covered
4. Report results and document any bugs in `docs/bugs/`

## Phase 5: Bug Fixes (developer + devops agents)
If the tester found bugs:
1. Pass application bugs to the developer subagent
2. Pass infrastructure / Docker bugs to the devops subagent
3. Have the tester re-run tests to confirm fixes

## Phase 6: Review (reviewer agent)
Ask the reviewer subagent to:
1. Review all code against specs and MRD
2. Check for security, performance, and quality issues
3. Verify MRD compliance (every requirement addressed)
4. Write review report to `docs/reviews/`

## Phase 7: Final Fixes (developer + devops agents)
If the reviewer found critical issues:
1. Pass code issues to the developer
2. Pass infrastructure / security issues to the devops agent
3. Have the reviewer verify the fixes

## Phase 8: Wrap-up
1. Update CLAUDE.md with final commands and structure
2. Summarize what was built
3. List how to run, test, and deploy the project
4. Note any open items or future improvements from the MRD's P1/P2 list
