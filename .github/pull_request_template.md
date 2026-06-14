## Description
Please include a summary of the change, the problem it solves, and any motivation/context. 

Fixes # (issue number)

## Type of Change
Please delete options that are not relevant.
- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] ⚙️ Chore / Refactoring (code cleanup, component refactoring, modularity improvements)
- [ ] 📝 Documentation update

## Scope of Changes
Which parts of the application does this PR impact?
- [ ] **Frontend / UI:** React, TypeScript, Carbon Design System components
- [ ] **App Shell:** Electron / Main process logic
- [ ] **Backend / CLI:** Python script, SQL/Flyway parsing, Graphify layer
- [ ] **Build / CI:** Dependency updates, GitHub Actions, packaging

## Quality Assurance & Testing
Please describe the tests that you ran to verify your changes. Provide instructions so we can reproduce.

### Automated Tests Run
*Note: We use Vitest for unit testing and Playwright for E2E. Ensure no Jest artifacts are introduced.*
- [ ] **Unit Tests (Vitest):** All tests passing, or new tests added to cover changes.
- [ ] **E2E Tests (Playwright):** UI changes verified with end-to-end flows.

### Manual Verification Steps
1. Go to '...'
2. Click on '...'
3. Scroll down to '...'
4. Verify the graph/export output matches expected behavior.

## Checklist
- [ ] My code follows the code style and SOLID architectural principles of this project.
- [ ] I have performed a self-review of my own code.
- [ ] I have commented my code, particularly in hard-to-understand areas.
- [ ] I have made corresponding changes to the documentation (if applicable).
- [ ] My changes generate no new build errors or console warnings.
- [ ] New and existing unit tests pass locally with my changes.