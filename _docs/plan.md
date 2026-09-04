# Shared Household Chores Manager — Project Plan

## 1. Project Overview

Build a local web application for managing shared household chores between a couple.

The application should help two people:

- Organize household chores.
- Plan responsibilities throughout the week.
- Track who was expected to perform each chore.
- Track who actually performed each chore.
- Measure how household workload is divided.
- Identify differences between planned and actual workload.
- Review historical workload distribution over time.

The product should remain intentionally focused on a single household composed of exactly two members.

---

## 2. Project Constraints

### Language

The entire project must be written in English.

This includes:

- Source code
- Variable and function names
- Class names
- Comments
- Documentation
- UI text
- Database-related naming
- Tests
- Configuration files

Portuguese must not appear in the project.

### Python Environment

The project must use:

- Python virtual environment (`venv`)
- `uv` for Python package and dependency management

Both are mandatory project requirements.

### Architecture

The application architecture and detailed technology choices are intentionally not defined in this document.

They should be decided separately during the implementation planning phase.

The functional requirements described here should guide those architectural decisions rather than being adapted to a predefined architecture.

---

# 3. Users and Household Model

The application supports exactly:

- One household
- Two household members

There is no authentication system.

During first-run setup, the application asks for the names of the two household members.

Example:

- Alex
- Sam

The members can later be renamed through the application settings.

A member selector should allow the application to know which member is currently interacting with it.

The system does not support:

- User accounts
- Passwords
- Email-based authentication
- Multiple households
- More than two members

---

# 4. Core Product Concepts

The application revolves around two related concepts:

## Chore Definition

A reusable definition describing a household responsibility.

Examples:

- Clean bathroom
- Do laundry
- Take out trash
- Vacuum apartment

A chore definition contains the configuration used to generate actual chore occurrences.

## Chore Occurrence

A concrete instance of a chore that needs to be performed.

Example:

Chore definition:

> Clean bathroom — weekly

Occurrence:

> Clean bathroom — Saturday, September 12

Historical reporting and completion tracking operate on occurrences rather than directly on chore definitions.

---

# 5. Chore Library

The application must provide a **Chore Library**.

The library contains the household's active and inactive chore definitions.

Users must be able to:

- View chores
- Create chores
- Edit chores
- Activate chores
- Deactivate chores

Chores should not need to be permanently deleted.

Deactivation preserves historical information while preventing future occurrences from being generated.

Changes made to a chore definition only affect future occurrences.

Existing and historical occurrences must preserve the values that applied when they were created.

---

# 6. Chore Catalog

The application should include a predefined catalog of common household chores.

Example templates may include:

### Cleaning

- Clean bathroom
- Vacuum floors
- Mop floors
- Dust furniture
- Clean kitchen

### Laundry

- Wash clothes
- Fold clothes
- Change bed sheets

### Kitchen

- Wash dishes
- Empty dishwasher
- Clean refrigerator

### Shopping

- Grocery shopping
- Buy household supplies

### Maintenance

- Take out trash
- Water plants

The exact initial catalog may be refined during implementation.

Catalog entries are **templates**, not permanent system objects.

When a template is added to the Chore Library, it becomes a normal chore definition and can be fully edited.

Users may also create chores manually without using the catalog.

---

# 7. Chore Categories

Every chore belongs to one fixed category.

Initial categories:

- Cleaning
- Laundry
- Kitchen
- Shopping
- Maintenance
- Pets
- Other

Categories are predefined by the application.

Custom category management is outside the MVP scope.

---

# 8. Chore Properties

A chore definition should contain at least:

- Name
- Optional description
- Category
- Effort score
- Priority
- Recurrence type
- Assignment type
- Assigned member when applicable
- Active/inactive status

---

# 9. Effort Score

Every chore has an **effort score from 1 to 5**.

The score represents the relative amount of household workload associated with the chore.

Example interpretation:

- `1` — very small effort
- `2` — small effort
- `3` — moderate effort
- `4` — significant effort
- `5` — high effort

The effort score belongs to the chore definition and applies to all occurrences generated from that definition.

Effort points are used for workload analysis.

They are not a gamification mechanism.

---

# 10. Priority

Every chore has one of three priority levels:

- `low`
- `medium`
- `high`

Priority represents importance.

Priority and effort are independent concepts.

For example:

> Take out trash

could be:

- Priority: high
- Effort: 1

while:

> Deep clean bathroom

could be:

- Priority: medium
- Effort: 5

---

# 11. Recurrence

The MVP supports four recurrence types:

- `one-time`
- `daily`
- `weekly`
- `monthly`

Recurring chores automatically generate chore occurrences.

One-time chores can be created manually whenever needed.

More advanced recurrence rules such as:

- Every 3 days
- Every 2 weeks
- Specific combinations of weekdays

are outside the MVP scope.

---

# 12. Assignment Models

Every chore uses one of three assignment strategies:

- `fixed`
- `alternating`
- `unassigned`

## Fixed

The chore is normally assigned to the same household member.

Example:

> Water plants → Alex

## Alternating

Responsibility alternates between members for each generated occurrence.

Example:

Week 1:

> Clean bathroom → Alex

Week 2:

> Clean bathroom → Sam

Week 3:

> Clean bathroom → Alex

Alternation is based on occurrences, not completion.

The next assignment therefore changes even if the previous occurrence was missed or cancelled.

## Unassigned

The occurrence initially has no responsible member.

Either member can use a **Claim** action.

Once claimed, that member becomes the assigned member for that occurrence.

---

# 13. Reassignment

An occurrence may be reassigned during the week.

Either member can transfer responsibility to the other member.

No approval workflow is required.

Reassignment changes the planned responsibility for that occurrence.

---

# 14. Assigned Member vs. Completing Member

The application must distinguish between:

- `assigned_to`
- `completed_by`

These values may be different.

Example:

> Clean bathroom

Planned:

> assigned_to = Alex

Actual:

> completed_by = Sam

This distinction is important for workload analysis.

Planned workload uses assignment information.

Actual workload uses completion information.

---

# 15. Due Dates

Chore occurrences have a due date.

Time-of-day scheduling is not required.

Example:

> Clean bathroom — Saturday

rather than:

> Clean bathroom — Saturday at 10:30 AM

---

# 16. Chore Occurrence Lifecycle

Occurrences may move through states such as:

- Pending
- Completed
- Overdue
- Cancelled

A pending occurrence becomes overdue when its due date passes without completion.

Overdue chores remain visible and require a user decision.

Users may:

- Complete the chore
- Reschedule the chore
- Cancel the chore

Overdue chores should not silently disappear or automatically roll into another date.

---

# 17. Completion

When completing a chore, the application must record:

- Completion status
- Completion date
- Member who actually completed the chore

The member completing the chore may differ from the assigned member.

Historical workload calculations must use the member who actually completed the chore.

---

# 18. Weekly Model

The application uses a weekly planning cycle.

A week runs:

**Monday → Sunday**

Recurring chores automatically generate the appropriate occurrences for the week.

One-time chores may be added manually during the week.

The weekly cycle closes automatically when the week ends.

No manual weekly closing action is required.

Historical information from closed weeks remains available for reporting.

---

# 19. Weekly Planning

The application must provide a **Weekly Planning** view.

It should display the seven days of the current week and the chores scheduled for each day.

Users should be able to understand:

- What needs to be done
- When it needs to be done
- Who is responsible
- Chore priority
- Chore effort

The weekly view should provide a calendar-like representation of:

- Monday
- Tuesday
- Wednesday
- Thursday
- Friday
- Saturday
- Sunday

Users may reassign chores during the week.

One-time chores may also be added.

---

# 20. Today View

The **Today** view is the primary operational screen.

It should show:

- Chores due today
- Overdue chores
- Assigned member
- Priority
- Effort score
- Current status

From this view, users should be able to:

- Complete a chore
- Claim an unassigned chore
- Reassign a chore
- Reschedule a chore
- Cancel a chore
- Add a one-time chore

Visual reminders should highlight:

- Chores due today
- Overdue chores

No external notification system is required.

---

# 21. Workload Measurement

Workload is measured using completed effort points.

Example:

During one week:

Alex completes:

- Clean bathroom: 4 points
- Take out trash: 1 point
- Grocery shopping: 3 points

Total:

> Alex = 8 effort points

Sam completes:

- Laundry: 3 points
- Vacuum apartment: 4 points

Total:

> Sam = 7 effort points

Actual workload distribution:

> Alex = 53%

> Sam = 47%

The purpose of this metric is to make household workload visible, not to create competition.

---

# 22. Planned vs. Actual Workload

The dashboard must distinguish between:

## Planned Workload

Calculated from the effort points assigned to each member.

## Actual Workload

Calculated from the effort points of chores actually completed by each member.

Example:

Planned:

> Alex 50% / Sam 50%

Actual:

> Alex 65% / Sam 35%

This allows the couple to identify differences between intended workload distribution and what actually happened.

---

# 23. Dashboard

The application should provide a dashboard containing information about the current week.

At minimum, it should display:

- Effort points assigned to each member
- Effort points completed by each member
- Planned workload distribution
- Actual workload distribution
- Number of chores completed by each member

The dashboard should make workload balance easy to understand visually.

---

# 24. Weekly History

The application must preserve historical weekly summaries.

Users should be able to view recent weeks and compare:

- Completed chores
- Effort points by member
- Planned workload distribution
- Actual workload distribution

The goal is simple historical comparison.

Advanced analytics are outside the MVP scope.

---

# 25. Settings

A simple Settings area should allow:

- Renaming household member 1
- Renaming household member 2

Additional account or household administration is not required.

---

# 26. Persistence

Application data must persist locally using **SQLite**.

The database should preserve at least:

- Household members
- Chore definitions
- Chore occurrences
- Assignments
- Completions
- Weekly historical information

The exact database schema should be defined during architecture and implementation planning.

---

# 27. Responsive Web Interface

The application must be a web application.

The interface should work appropriately on:

- Desktop browsers
- Smartphone browsers

The application does not need to be mobile-first.

A native mobile application is outside the project scope.

---

# 28. Visual Reminders

The application should provide visual indicators for chores requiring attention.

At minimum:

- Due today
- Overdue

These indicators exist only inside the application.

The MVP does not send external notifications.

---

# 29. Data Integrity Rules

The following rules should be preserved:

### Historical occurrences are immutable in meaning

Editing a chore definition must not retroactively change historical occurrences.

For example:

If:

> Clean bathroom = 3 effort points

and later changes to:

> Clean bathroom = 4 effort points

previous completed occurrences remain worth 3 points.

Only future occurrences use the new value.

### Completion reflects actual work

Actual workload must always be calculated using `completed_by`, not `assigned_to`.

### Alternation is occurrence-based

Alternating chores switch responsibility for every generated occurrence regardless of whether previous occurrences were completed.

### Deactivation preserves history

Deactivating a chore prevents future generation but must not remove historical data.

---

# 30. Out of Scope

The following features are explicitly outside the MVP.

## Authentication

No:

- Login
- Passwords
- Email accounts
- OAuth
- SSO

## Multiple Households

The system supports exactly one household.

## Additional Members

The system supports exactly two members.

## External Integrations

No integrations with:

- Email
- WhatsApp
- Telegram
- Slack
- External calendars
- Smart home platforms
- Third-party task managers

## External Notifications

No:

- Push notifications
- SMS
- Email reminders

Only in-app visual reminders are required.

## Advanced Recurrence

No complex recurrence rules beyond:

- One-time
- Daily
- Weekly
- Monthly

## Gamification

No:

- Scores
- Rewards
- Badges
- Leaderboards
- Competitive ranking
- Streak mechanics

Effort points exist only for workload measurement.

## Advanced Analytics

No:

- Custom reporting periods
- Complex filters
- BI-style analytics
- Forecasting
- Predictive workload analysis

## Native Mobile Applications

No dedicated:

- iOS application
- Android application

The responsive web interface is sufficient.

## Custom Categories

Users cannot create or manage chore categories in the MVP.

---

# 31. Main Application Areas

The MVP can be conceptually divided into five user-facing areas:

### Today

Operational view for today's chores and overdue work.

### Week

Seven-day planning view for the current week.

### Chore Library

Management of recurring chore definitions and access to chore templates.

### Dashboard

Current workload distribution and planned-vs-actual comparison.

### History

Simple comparison of previous weeks.

A Settings area provides basic member configuration.

---

# 32. MVP Success Criteria

The MVP is successful when a couple can:

1. Configure their two household members.
2. Add chores from predefined templates.
3. Create custom chores.
4. Assign effort scores and priorities.
5. Configure chores as fixed, alternating, or unassigned.
6. Configure chores as one-time, daily, weekly, or monthly.
7. Automatically receive recurring chore occurrences.
8. View the current week.
9. View chores due today.
10. Claim unassigned chores.
11. Reassign chores.
12. Complete chores while recording who actually performed them.
13. Handle overdue chores.
14. Reschedule or cancel occurrences.
15. Compare planned workload with actual workload.
16. Review workload distribution from previous weeks.
17. Preserve all relevant information between application restarts.
18. Use the application from both desktop and smartphone browsers.

---

# 33. Guiding Product Principle

The application should answer three questions clearly:

> **What needs to be done?**

> **Who is expected to do it?**

> **Who is actually doing the household work?**

Features that do not materially improve one of these three questions should generally be considered outside the MVP unless explicitly added to the scope later.