# Technical Definition of Done (DoD)

This document outlines the criteria that must be met for any piece of work (for example: user story, task, bug fix, or feature) to be considered done and ready for release or further integration.

Adhering to this DoD ensures high quality, consistency, and shared understanding across the team.

## 1. Code quality and standards

- [ ] **Code reviewed:** All new or changed code has been formally reviewed by at least two other qualified team members (or more for critical components). All review comments have been addressed or explicitly justified.
- [ ] **Static analysis passed:** Code passes all configured static analysis checks (for example Cursor, SonarQube, Copilot) with no critical or high-priority issues introduced.
- [ ] **Coding standards met:** Code adheres to the team's agreed coding style guides, architectural patterns, and best practices.
- [ ] **No dead code/comments:** Unused code, commented-out code, or unnecessary debugging statements have been removed.

## 2. Testing and validation

- [ ] **Acceptance criteria met:** All defined acceptance criteria for the story/task have been verified and passed, either through automated tests, manual testing, or a combination.
- [ ] **No known critical/high bugs:** There are no known critical or high-priority bugs introduced by this work, and any identified bugs have been addressed or logged for immediate resolution.
- [ ] **Exploratory testing (if applicable):** Initial exploratory testing has been conducted to uncover unforeseen issues.

## 3. Documentation and knowledge transfer

- [ ] **Technical documentation updated:** Internal technical documentation (for example README, Confluence docs if needed) is updated or created. Database schema changes are documented.
- [ ] **User documentation/release notes drafted (if applicable):** Content for user-facing documentation, release notes, or internal support guides has been drafted or updated.
- [ ] **Knowledge shared:** Key technical insights, potential pitfalls, or operational considerations related to this work have been communicated to relevant team members (for example during stand-up, demo, or KT session).

## 4. Deployment and release readiness

- [ ] **Builds successfully:** Terraform plan does not return errors.
- [ ] **Deployed to staging/pre-production (if applicable):** The feature/fix has been successfully deployed to a staging or pre-production environment for final validation and smoke testing.
- [ ] **Performance considerations:** Basic performance checks have been considered, and no obvious performance degradations are introduced (for example N+1 queries, inefficient loops).
- [ ] **Security considerations:** Basic security checks have been considered, and no obvious vulnerabilities are introduced (for example unhandled inputs, exposed secrets).
- [ ] **Monitoring and alerting (if applicable):** Service adheres to the Observability Checklist and passes all relevant requirements.

## 5. Communication and enablement

- [ ] **Communication plan triggered:** For net new tools or features, especially user-facing updates, a communication plan has been established.
- [ ] **Audience identified:** The target audience for the change has been clearly defined (Engineering, PnT, Customer Success, Executives, Managers).
- [ ] **Demo visuals completed:** High-quality Loom recordings or video walkthroughs of new functionality are completed and accessible to the identified audience.
- [ ] **Training requirements assessed:** A determination has been made on whether formal training sessions or workshops are required to ensure successful adoption.
- [ ] **Announcements drafted:** Communication is prepared and scheduled for the following internal channels:
  - Slack messages tailored for relevant channels
  - `#engineering-community` (new tools and services)
  - `#team-incident-management` (new features and feature updates)
  - Opspacer (official updates to Directors and above)
