from datetime import date, datetime, timezone
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase

from .models import (
    ChoreAssignment,
    ChoreCompletion,
    ChoreDefinition,
    ChoreOccurrence,
    HouseholdMember,
    WeeklySummary,
)
from .services import (
    cancel_occurrence,
    complete_occurrence,
    create_one_time_occurrence,
    calculate_workload,
    generate_occurrences_for_week,
    refresh_overdue_occurrences,
    reschedule_occurrence,
    persist_closed_week_summaries,
)


class HomeViewTests(TestCase):
    def test_home_page_is_served(self):
        HouseholdMember.objects.create(name="Alex")
        HouseholdMember.objects.create(name="Sam")

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choremate")
        self.assertContains(response, "Alex")

    def test_home_redirects_to_setup_for_a_fresh_installation(self):
        response = self.client.get("/")

        self.assertRedirects(response, "/setup/")


class HouseholdSetupTests(TestCase):
    def test_setup_creates_exactly_two_members_and_selects_the_first(self):
        response = self.client.post(
            "/setup/",
            {"member_one": " Alex ", "member_two": "Sam"},
        )

        self.assertRedirects(response, "/")
        self.assertEqual(list(HouseholdMember.objects.values_list("name", flat=True)), ["Alex", "Sam"])
        self.assertEqual(self.client.session["active_member_id"], HouseholdMember.objects.get(name="Alex").id)

    def test_setup_rejects_missing_or_duplicate_names_without_partial_data(self):
        response = self.client.post("/setup/", {"member_one": " ", "member_two": "Alex"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This name is required.")
        self.assertEqual(HouseholdMember.objects.count(), 0)

        response = self.client.post("/setup/", {"member_one": "Alex", "member_two": "alex"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose two different member names.")
        self.assertEqual(HouseholdMember.objects.count(), 0)


class MemberSettingsTests(TestCase):
    def setUp(self):
        self.alex = HouseholdMember.objects.create(name="Alex")
        self.sam = HouseholdMember.objects.create(name="Sam")

    def test_member_selector_persists_the_active_member(self):
        response = self.client.post("/members/select/", {"member_id": self.sam.id})

        self.assertRedirects(response, "/")
        self.assertEqual(self.client.session["active_member_id"], self.sam.id)
        self.assertContains(self.client.get("/"), "Sam")

    def test_settings_renames_a_member_and_preserves_the_same_record(self):
        response = self.client.post(
            "/settings/",
            {"member_id": self.alex.id, f"member-{self.alex.id}-name": "Taylor"},
        )

        self.assertRedirects(response, "/settings/")
        self.alex.refresh_from_db()
        self.assertEqual(self.alex.name, "Taylor")
        self.assertEqual(HouseholdMember.objects.count(), 2)

    def test_settings_rejects_a_blank_name(self):
        response = self.client.post(
            "/settings/",
            {"member_id": self.alex.id, f"member-{self.alex.id}-name": "  "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This name is required.")
        self.alex.refresh_from_db()
        self.assertEqual(self.alex.name, "Alex")


class ChoreLibraryTests(TestCase):
    def setUp(self):
        self.alex = HouseholdMember.objects.create(name="Alex")
        self.sam = HouseholdMember.objects.create(name="Sam")
        self.chore_data = {
            "name": "Clean bathroom",
            "description": "Weekly bathroom cleaning",
            "category": ChoreDefinition.Category.CLEANING,
            "effort_score": 4,
            "priority": ChoreDefinition.Priority.MEDIUM,
            "recurrence": ChoreDefinition.Recurrence.WEEKLY,
            "assignment_type": ChoreDefinition.AssignmentType.FIXED,
            "fixed_member": self.alex,
        }
        self.chore_form_data = {**self.chore_data, "fixed_member": self.alex.id}

    def test_library_lists_active_and_inactive_chores(self):
        active = ChoreDefinition.objects.create(**self.chore_data)
        inactive = ChoreDefinition.objects.create(
            **{**self.chore_data, "name": "Wash dishes", "is_active": False}
        )

        response = self.client.get("/library/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, active.name)
        self.assertContains(response, inactive.name)
        self.assertContains(response, "Active")
        self.assertContains(response, "Inactive")

    def test_user_can_create_and_edit_a_chore_definition(self):
        response = self.client.post("/library/add/", self.chore_form_data)

        self.assertRedirects(response, "/library/")
        chore = ChoreDefinition.objects.get(name="Clean bathroom")
        self.assertEqual(chore.effort_score, 4)

        response = self.client.post(
            f"/library/{chore.id}/edit/",
            {**self.chore_form_data, "name": "Deep clean bathroom", "effort_score": 5},
        )

        self.assertRedirects(response, "/library/")
        chore.refresh_from_db()
        self.assertEqual(chore.name, "Deep clean bathroom")
        self.assertEqual(chore.effort_score, 5)

    def test_fixed_chore_requires_a_member_and_other_types_clear_member(self):
        invalid = {**self.chore_form_data, "fixed_member": ""}
        response = self.client.post("/library/add/", invalid)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a member for a fixed chore.")
        self.assertEqual(ChoreDefinition.objects.count(), 0)

        response = self.client.post(
            "/library/add/",
            {**self.chore_form_data, "assignment_type": ChoreDefinition.AssignmentType.UNASSIGNED},
        )

        self.assertRedirects(response, "/library/")
        chore = ChoreDefinition.objects.get()
        self.assertIsNone(chore.fixed_member)

    def test_invalid_effort_does_not_save(self):
        response = self.client.post("/library/add/", {**self.chore_form_data, "effort_score": 6})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Effort score must be between 1 and 5.")
        self.assertEqual(ChoreDefinition.objects.count(), 0)

    def test_toggle_deactivates_and_reactivates_without_deleting(self):
        chore = ChoreDefinition.objects.create(**self.chore_data)

        response = self.client.post(f"/library/{chore.id}/toggle/")

        self.assertRedirects(response, "/library/")
        chore.refresh_from_db()
        self.assertFalse(chore.is_active)
        self.assertEqual(ChoreDefinition.objects.count(), 1)

        self.client.post(f"/library/{chore.id}/toggle/")
        chore.refresh_from_db()
        self.assertTrue(chore.is_active)

    def test_editing_definition_does_not_change_an_existing_occurrence_snapshot(self):
        chore = ChoreDefinition.objects.create(**self.chore_data)
        occurrence = ChoreOccurrence.objects.create(
            definition=chore,
            due_date=date(2026, 9, 7),
            chore_name=chore.name,
            category=chore.category,
            effort_score=chore.effort_score,
            priority=chore.priority,
        )

        self.client.post(
            f"/library/{chore.id}/edit/",
            {**self.chore_form_data, "effort_score": 5, "name": "Deep clean bathroom"},
        )

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.chore_name, "Clean bathroom")
        self.assertEqual(occurrence.effort_score, 4)


class ChoreCatalogTests(TestCase):
    def setUp(self):
        HouseholdMember.objects.create(name="Alex")
        HouseholdMember.objects.create(name="Sam")

    def test_catalog_shows_required_categories_and_examples(self):
        response = self.client.get("/library/catalog/")

        self.assertEqual(response.status_code, 200)
        for template_name in (
            "Clean bathroom",
            "Vacuum floors",
            "Wash clothes",
            "Wash dishes",
            "Grocery shopping",
            "Take out trash",
        ):
            self.assertContains(response, template_name)
        for category in ("cleaning", "laundry", "kitchen", "shopping", "maintenance"):
            self.assertContains(response, category)

    def test_adding_template_creates_a_normal_editable_chore(self):
        response = self.client.post("/library/catalog/clean-bathroom/add/")

        self.assertRedirects(response, "/library/")
        chore = ChoreDefinition.objects.get(name="Clean bathroom")
        self.assertEqual(chore.description, "Clean the bathroom surfaces and fixtures.")
        self.assertEqual(chore.assignment_type, ChoreDefinition.AssignmentType.UNASSIGNED)
        self.assertTrue(chore.is_active)

    def test_adding_the_same_template_does_not_create_a_duplicate(self):
        self.client.post("/library/catalog/clean-bathroom/add/")
        self.client.post("/library/catalog/clean-bathroom/add/")

        self.assertEqual(ChoreDefinition.objects.filter(name="Clean bathroom").count(), 1)

    def test_invalid_template_does_not_create_a_chore(self):
        response = self.client.post("/library/catalog/not-a-template/add/", follow=True)

        self.assertContains(response, "could not be found")
        self.assertEqual(ChoreDefinition.objects.count(), 0)


class RecurrenceGenerationTests(TestCase):
    def setUp(self):
        self.alex = HouseholdMember.objects.create(name="Alex")
        self.sam = HouseholdMember.objects.create(name="Sam")

    def create_definition(self, **overrides):
        data = {
            "name": "Recurring chore",
            "category": ChoreDefinition.Category.CLEANING,
            "effort_score": 3,
            "priority": ChoreDefinition.Priority.MEDIUM,
            "recurrence": ChoreDefinition.Recurrence.DAILY,
            "assignment_type": ChoreDefinition.AssignmentType.UNASSIGNED,
        }
        data.update(overrides)
        return ChoreDefinition.objects.create(**data)

    def set_creation_date(self, definition, creation_date):
        ChoreDefinition.objects.filter(pk=definition.pk).update(
            created_at=datetime.combine(creation_date, datetime.min.time(), tzinfo=timezone.utc),
        )
        definition.refresh_from_db()

    def test_daily_generation_creates_seven_snapshot_occurrences(self):
        definition = self.create_definition()

        occurrences = generate_occurrences_for_week(date(2026, 9, 7))

        self.assertEqual(len(occurrences), 7)
        self.assertEqual(
            list(ChoreOccurrence.objects.values_list("due_date", flat=True)),
            [date(2026, 9, day) for day in range(7, 14)],
        )
        self.assertEqual(occurrences[0].recurrence, definition.recurrence)
        self.assertEqual(occurrences[0].effort_score, definition.effort_score)

    def test_weekly_generation_uses_definition_weekday_and_is_idempotent(self):
        definition = self.create_definition(recurrence=ChoreDefinition.Recurrence.WEEKLY)
        self.set_creation_date(definition, date(2026, 9, 9))

        first_run = generate_occurrences_for_week(date(2026, 9, 7))
        second_run = generate_occurrences_for_week(date(2026, 9, 7))

        self.assertEqual([occurrence.due_date for occurrence in first_run], [date(2026, 9, 9)])
        self.assertEqual([occurrence.pk for occurrence in first_run], [occurrence.pk for occurrence in second_run])
        self.assertEqual(ChoreOccurrence.objects.count(), 1)

    def test_monthly_generation_uses_anchor_day_clamped_to_month_end(self):
        definition = self.create_definition(recurrence=ChoreDefinition.Recurrence.MONTHLY)
        self.set_creation_date(definition, date(2026, 1, 31))

        occurrences = generate_occurrences_for_week(date(2026, 9, 28))

        self.assertEqual([occurrence.due_date for occurrence in occurrences], [date(2026, 9, 30)])

    def test_inactive_definitions_are_not_generated(self):
        definition = self.create_definition(is_active=False)

        self.assertEqual(generate_occurrences_for_week(date(2026, 9, 7)), [])
        self.assertFalse(ChoreOccurrence.objects.filter(definition=definition).exists())

    def test_one_time_occurrence_can_be_created_manually(self):
        definition = self.create_definition(recurrence=ChoreDefinition.Recurrence.ONE_TIME)

        occurrence = create_one_time_occurrence(definition, date(2026, 9, 12))

        self.assertEqual(occurrence.due_date, date(2026, 9, 12))
        self.assertEqual(occurrence.recurrence, ChoreDefinition.Recurrence.ONE_TIME)
        self.assertEqual(create_one_time_occurrence(definition, occurrence.due_date).pk, occurrence.pk)

    def test_fixed_and_alternating_assignments_are_generated(self):
        fixed = self.create_definition(
            name="Fixed chore",
            recurrence=ChoreDefinition.Recurrence.WEEKLY,
            assignment_type=ChoreDefinition.AssignmentType.FIXED,
            fixed_member=self.alex,
        )
        alternating = self.create_definition(
            name="Alternating chore",
            recurrence=ChoreDefinition.Recurrence.WEEKLY,
            assignment_type=ChoreDefinition.AssignmentType.ALTERNATING,
        )
        self.set_creation_date(alternating, date(2026, 9, 9))

        generate_occurrences_for_week(date(2026, 9, 7))
        generate_occurrences_for_week(date(2026, 9, 14))

        self.assertEqual(fixed.occurrences.order_by("due_date").first().assignment.member, self.alex)
        alternating_assignments = list(
            alternating.occurrences.order_by("due_date").values_list("assignment__member", flat=True)
        )
        self.assertEqual(alternating_assignments, [self.alex.id, self.sam.id])


class OccurrenceAssignmentTests(TestCase):
    def setUp(self):
        self.alex = HouseholdMember.objects.create(name="Alex")
        self.sam = HouseholdMember.objects.create(name="Sam")
        self.definition = ChoreDefinition.objects.create(
            name="Claimable chore",
            category=ChoreDefinition.Category.CLEANING,
            effort_score=2,
            priority=ChoreDefinition.Priority.LOW,
            recurrence=ChoreDefinition.Recurrence.ONE_TIME,
            assignment_type=ChoreDefinition.AssignmentType.UNASSIGNED,
        )
        self.occurrence = ChoreOccurrence.objects.create(
            definition=self.definition,
            due_date=date(2026, 9, 12),
            chore_name=self.definition.name,
            category=self.definition.category,
            effort_score=self.definition.effort_score,
            priority=self.definition.priority,
            recurrence=self.definition.recurrence,
        )

    def test_unassigned_occurrence_can_be_claimed(self):
        response = self.client.post(
            f"/occurrences/{self.occurrence.id}/assign/",
            {"member": self.alex.id, "action": "claim"},
        )

        self.assertRedirects(response, "/occurrences/")
        self.assertEqual(self.occurrence.assignment.member, self.alex)

    def test_assigned_occurrence_can_be_reassigned_without_changing_definition(self):
        assignment = ChoreAssignment.objects.create(occurrence=self.occurrence, member=self.alex)

        response = self.client.post(
            f"/occurrences/{self.occurrence.id}/assign/",
            {"member": self.sam.id, "action": "reassign"},
        )

        self.assertRedirects(response, "/occurrences/")
        assignment.refresh_from_db()
        self.assertEqual(assignment.member, self.sam)
        self.assertEqual(self.occurrence.definition_id, self.definition.id)

    def test_claiming_an_already_assigned_occurrence_is_rejected(self):
        ChoreAssignment.objects.create(occurrence=self.occurrence, member=self.alex)

        response = self.client.post(
            f"/occurrences/{self.occurrence.id}/assign/",
            {"member": self.sam.id, "action": "claim"},
            follow=True,
        )

        self.assertContains(response, "already assigned")
        self.assertEqual(self.occurrence.assignment.member, self.alex)

    def test_invalid_member_is_rejected(self):
        response = self.client.post(
            f"/occurrences/{self.occurrence.id}/assign/",
            {"member": 999, "action": "claim"},
            follow=True,
        )

        self.assertContains(response, "Choose one of the two household members.")
        self.assertFalse(ChoreAssignment.objects.filter(occurrence=self.occurrence).exists())


class WeeklyPlanningTests(TestCase):
    def setUp(self):
        self.alex = HouseholdMember.objects.create(name="Alex")
        self.sam = HouseholdMember.objects.create(name="Sam")
        self.definition = ChoreDefinition.objects.create(
            name="Weekly clean",
            category=ChoreDefinition.Category.CLEANING,
            effort_score=3,
            priority=ChoreDefinition.Priority.MEDIUM,
            recurrence=ChoreDefinition.Recurrence.DAILY,
            assignment_type=ChoreDefinition.AssignmentType.UNASSIGNED,
        )

    def test_week_view_shows_all_seven_days_and_generates_current_week(self):
        with patch("chores.views.week_start_for", return_value=date(2026, 9, 7)):
            response = self.client.get("/week/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["days"]), 7)
        self.assertEqual(ChoreOccurrence.objects.filter(definition=self.definition).count(), 7)
        self.assertContains(response, "Weekly Planning")

    def test_week_view_adds_one_time_chore_in_current_week(self):
        with patch("chores.views.week_start_for", return_value=date(2026, 9, 7)):
            response = self.client.post(
                "/week/",
                {
                    "name": "Buy detergent",
                    "due_date": "2026-09-11",
                    "category": ChoreDefinition.Category.SHOPPING,
                    "effort_score": 2,
                    "priority": ChoreDefinition.Priority.HIGH,
                },
            )

        self.assertRedirects(response, "/week/")
        self.assertTrue(ChoreOccurrence.objects.filter(chore_name="Buy detergent", due_date=date(2026, 9, 11)).exists())

    def test_one_time_chore_outside_current_week_is_rejected(self):
        with patch("chores.views.week_start_for", return_value=date(2026, 9, 7)):
            response = self.client.post(
                "/week/",
                {
                    "name": "Buy detergent",
                    "due_date": "2026-09-20",
                    "category": ChoreDefinition.Category.SHOPPING,
                    "effort_score": 2,
                    "priority": ChoreDefinition.Priority.HIGH,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "current Monday-to-Sunday week")
        self.assertFalse(ChoreDefinition.objects.filter(name="Buy detergent").exists())


class OccurrenceLifecycleTests(TestCase):
    def setUp(self):
        self.member = HouseholdMember.objects.create(name="Alex")
        self.other_member = HouseholdMember.objects.create(name="Sam")
        definition = ChoreDefinition.objects.create(
            name="Lifecycle chore",
            category=ChoreDefinition.Category.OTHER,
            effort_score=2,
            priority=ChoreDefinition.Priority.MEDIUM,
            recurrence=ChoreDefinition.Recurrence.ONE_TIME,
            assignment_type=ChoreDefinition.AssignmentType.UNASSIGNED,
        )
        self.occurrence = ChoreOccurrence.objects.create(
            definition=definition,
            due_date=date(2026, 9, 1),
            chore_name=definition.name,
            category=definition.category,
            effort_score=definition.effort_score,
            priority=definition.priority,
            recurrence=definition.recurrence,
        )

    def test_pending_occurrence_becomes_overdue_after_due_date(self):
        self.assertEqual(refresh_overdue_occurrences(date(2026, 9, 2)), 1)
        self.occurrence.refresh_from_db()
        self.assertEqual(self.occurrence.status, ChoreOccurrence.Status.OVERDUE)

    def test_overdue_occurrence_can_be_completed_by_any_member(self):
        refresh_overdue_occurrences(date(2026, 9, 2))

        complete_occurrence(self.occurrence, self.other_member, datetime(2026, 9, 2, tzinfo=timezone.utc))

        self.occurrence.refresh_from_db()
        self.assertEqual(self.occurrence.status, ChoreOccurrence.Status.COMPLETED)
        self.assertEqual(self.occurrence.completion.completed_by, self.other_member)

    def test_overdue_occurrence_can_be_rescheduled_or_cancelled(self):
        refresh_overdue_occurrences(date(2026, 9, 2))
        reschedule_occurrence(self.occurrence, date(2026, 9, 5))
        self.occurrence.refresh_from_db()
        self.assertEqual(self.occurrence.status, ChoreOccurrence.Status.PENDING)
        self.assertEqual(self.occurrence.due_date, date(2026, 9, 5))

        cancel_occurrence(self.occurrence)
        self.occurrence.refresh_from_db()
        self.assertEqual(self.occurrence.status, ChoreOccurrence.Status.CANCELLED)

    def test_cancelled_and_completed_occurrences_reject_invalid_transitions(self):
        cancel_occurrence(self.occurrence)
        with self.assertRaises(ValueError):
            complete_occurrence(self.occurrence, self.member)

        other = ChoreOccurrence.objects.create(
            definition=self.occurrence.definition,
            due_date=date(2026, 9, 3),
            chore_name=self.occurrence.chore_name,
            category=self.occurrence.category,
            effort_score=self.occurrence.effort_score,
            priority=self.occurrence.priority,
            recurrence=self.occurrence.recurrence,
        )
        complete_occurrence(other, self.member)
        with self.assertRaises(ValueError):
            cancel_occurrence(other)


class WorkloadCalculationTests(TestCase):
    def setUp(self):
        self.alex = HouseholdMember.objects.create(name="Alex")
        self.sam = HouseholdMember.objects.create(name="Sam")
        self.definition = ChoreDefinition.objects.create(
            name="Workload chore",
            category=ChoreDefinition.Category.OTHER,
            effort_score=4,
            priority=ChoreDefinition.Priority.MEDIUM,
            recurrence=ChoreDefinition.Recurrence.ONE_TIME,
            assignment_type=ChoreDefinition.AssignmentType.UNASSIGNED,
        )

    def make_occurrence(self, due_date, status=ChoreOccurrence.Status.PENDING):
        return ChoreOccurrence.objects.create(
            definition=self.definition,
            due_date=due_date,
            status=status,
            chore_name=self.definition.name,
            category=self.definition.category,
            effort_score=self.definition.effort_score,
            priority=self.definition.priority,
            recurrence=self.definition.recurrence,
        )

    def test_planned_and_actual_totals_use_their_respective_members(self):
        assigned_to_alex = self.make_occurrence(date(2026, 9, 1))
        ChoreAssignment.objects.create(occurrence=assigned_to_alex, member=self.alex)
        complete_occurrence(assigned_to_alex, self.sam, datetime(2026, 9, 1, tzinfo=timezone.utc))

        assigned_to_sam = self.make_occurrence(date(2026, 9, 2))
        ChoreAssignment.objects.create(occurrence=assigned_to_sam, member=self.sam)

        unassigned = self.make_occurrence(date(2026, 9, 3))
        totals = calculate_workload(ChoreOccurrence.objects.all())

        self.assertEqual(totals[self.alex.id]["planned_effort_points"], 4)
        self.assertEqual(totals[self.sam.id]["planned_effort_points"], 4)
        self.assertEqual(totals[self.alex.id]["actual_effort_points"], 0)
        self.assertEqual(totals[self.sam.id]["actual_effort_points"], 4)
        self.assertEqual(totals[self.sam.id]["completed_chore_count"], 1)
        self.assertEqual(totals[self.alex.id]["actual_percentage"], 0)
        self.assertEqual(totals[self.sam.id]["actual_percentage"], 100)
        self.assertEqual(totals[self.alex.id]["planned_percentage"], 50)
        self.assertEqual(totals[self.sam.id]["planned_percentage"], 50)
        self.assertIsNone(getattr(unassigned, "assignment", None))

    def test_zero_workload_has_zero_percentages(self):
        totals = calculate_workload([])

        self.assertEqual(totals[self.alex.id]["planned_percentage"], 0)
        self.assertEqual(totals[self.sam.id]["actual_percentage"], 0)


class TodayViewTests(TestCase):
    def setUp(self):
        self.alex = HouseholdMember.objects.create(name="Alex")
        self.sam = HouseholdMember.objects.create(name="Sam")
        self.definition = ChoreDefinition.objects.create(
            name="Today chore",
            category=ChoreDefinition.Category.OTHER,
            effort_score=2,
            priority=ChoreDefinition.Priority.HIGH,
            recurrence=ChoreDefinition.Recurrence.ONE_TIME,
            assignment_type=ChoreDefinition.AssignmentType.UNASSIGNED,
        )

    def make_occurrence(self, due_date, status=ChoreOccurrence.Status.PENDING):
        return ChoreOccurrence.objects.create(
            definition=self.definition, due_date=due_date, status=status,
            chore_name=self.definition.name, category=self.definition.category,
            effort_score=self.definition.effort_score, priority=self.definition.priority,
            recurrence=self.definition.recurrence,
        )

    def test_today_shows_due_and_overdue_work(self):
        self.make_occurrence(date(2026, 9, 4))
        self.make_occurrence(date(2026, 9, 1))

        with patch("chores.views.date") as mocked_date:
            mocked_date.today.return_value = date(2026, 9, 4)
            response = self.client.get("/today/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Today chore")
        self.assertEqual(ChoreOccurrence.objects.filter(status=ChoreOccurrence.Status.OVERDUE).count(), 1)

    def test_today_can_complete_and_cancel_an_occurrence(self):
        occurrence = self.make_occurrence(date(2026, 9, 4))

        response = self.client.post(
            f"/today/{occurrence.id}/action/",
            {"action": "complete", "member": self.sam.id},
        )
        self.assertRedirects(response, "/today/")
        occurrence.refresh_from_db()
        self.assertEqual(occurrence.status, ChoreOccurrence.Status.COMPLETED)

        other = self.make_occurrence(date(2026, 9, 5))
        self.client.post(f"/today/{other.id}/action/", {"action": "cancel"})
        other.refresh_from_db()
        self.assertEqual(other.status, ChoreOccurrence.Status.CANCELLED)

    def test_today_can_claim_and_reassign_an_occurrence(self):
        occurrence = self.make_occurrence(date(2026, 9, 4))

        response = self.client.post(
            f"/occurrences/{occurrence.id}/assign/",
            {"action": "claim", "member": self.alex.id, "next": "today"},
        )
        self.assertRedirects(response, "/today/")
        occurrence.refresh_from_db()
        self.assertEqual(occurrence.assignment.member, self.alex)

        response = self.client.post(
            f"/occurrences/{occurrence.id}/assign/",
            {"action": "reassign", "member": self.sam.id, "next": "today"},
        )
        self.assertRedirects(response, "/today/")
        occurrence.refresh_from_db()
        self.assertEqual(occurrence.assignment.member, self.sam)

    def test_today_renders_inline_assignment_controls(self):
        assigned = self.make_occurrence(date(2026, 9, 4))
        ChoreAssignment.objects.create(occurrence=assigned, member=self.alex)
        other_definition = ChoreDefinition.objects.create(
            name="Another today chore",
            category=ChoreDefinition.Category.OTHER,
            effort_score=1,
            priority=ChoreDefinition.Priority.LOW,
            recurrence=ChoreDefinition.Recurrence.ONE_TIME,
            assignment_type=ChoreDefinition.AssignmentType.UNASSIGNED,
        )
        ChoreOccurrence.objects.create(
            definition=other_definition,
            due_date=date(2026, 9, 4),
            chore_name=other_definition.name,
            category=other_definition.category,
            effort_score=other_definition.effort_score,
            priority=other_definition.priority,
            recurrence=other_definition.recurrence,
        )

        response = self.client.get("/today/")

        self.assertContains(response, "Reassign")
        self.assertContains(response, "Claim")

    def test_today_adds_a_one_time_chore_for_today(self):
        with patch("chores.views.date") as mocked_date:
            mocked_date.today.return_value = date(2026, 9, 4)
            response = self.client.post(
                "/today/add/",
                {"name": "Buy milk", "category": "shopping", "effort_score": 1, "priority": "high"},
            )

        self.assertRedirects(response, "/today/")
        self.assertTrue(ChoreOccurrence.objects.filter(chore_name="Buy milk", due_date=date(2026, 9, 4)).exists())


class DashboardViewTests(TestCase):
    def setUp(self):
        self.alex = HouseholdMember.objects.create(name="Alex")
        self.sam = HouseholdMember.objects.create(name="Sam")
        self.definition = ChoreDefinition.objects.create(
            name="Dashboard chore",
            category=ChoreDefinition.Category.OTHER,
            effort_score=4,
            priority=ChoreDefinition.Priority.MEDIUM,
            recurrence=ChoreDefinition.Recurrence.ONE_TIME,
            assignment_type=ChoreDefinition.AssignmentType.UNASSIGNED,
        )

    def make_occurrence(self, due_date, status=ChoreOccurrence.Status.PENDING):
        return ChoreOccurrence.objects.create(
            definition=self.definition, due_date=due_date, status=status,
            chore_name=self.definition.name, category=self.definition.category,
            effort_score=self.definition.effort_score, priority=self.definition.priority,
            recurrence=self.definition.recurrence,
        )

    def test_dashboard_shows_current_week_and_planned_actual_values(self):
        planned = self.make_occurrence(date(2026, 9, 1))
        ChoreAssignment.objects.create(occurrence=planned, member=self.alex)
        completed = self.make_occurrence(date(2026, 9, 2), ChoreOccurrence.Status.COMPLETED)
        ChoreCompletion.objects.create(
            occurrence=completed, completed_by=self.sam,
            completed_at=datetime(2026, 9, 2, 12, tzinfo=timezone.utc),
        )

        with patch("chores.views.date") as mocked_date:
            mocked_date.today.return_value = date(2026, 9, 4)
            response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Current week: Aug. 31, 2026 to Sept. 6, 2026")
        self.assertContains(response, "Alex")
        self.assertContains(response, "Sam")
        self.assertContains(response, "Planned effort")
        self.assertContains(response, "Completed effort")
        self.assertContains(response, "100.0%")

    def test_dashboard_keeps_zero_workload_member_visible(self):
        with patch("chores.views.date") as mocked_date:
            mocked_date.today.return_value = date(2026, 9, 4)
            response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alex")
        self.assertContains(response, "Sam")
        self.assertContains(response, "0%")


class HistoryViewTests(TestCase):
    def setUp(self):
        self.alex = HouseholdMember.objects.create(name="Alex")
        self.sam = HouseholdMember.objects.create(name="Sam")
        self.definition = ChoreDefinition.objects.create(
            name="Historical chore",
            category=ChoreDefinition.Category.OTHER,
            effort_score=3,
            priority=ChoreDefinition.Priority.MEDIUM,
            recurrence=ChoreDefinition.Recurrence.ONE_TIME,
            assignment_type=ChoreDefinition.AssignmentType.UNASSIGNED,
        )

    def test_closed_week_is_persisted_and_displayed(self):
        occurrence = ChoreOccurrence.objects.create(
            definition=self.definition,
            due_date=date(2026, 8, 27),
            status=ChoreOccurrence.Status.COMPLETED,
            chore_name=self.definition.name,
            category=self.definition.category,
            effort_score=self.definition.effort_score,
            priority=self.definition.priority,
            recurrence=self.definition.recurrence,
        )
        ChoreAssignment.objects.create(occurrence=occurrence, member=self.alex)
        ChoreCompletion.objects.create(
            occurrence=occurrence,
            completed_by=self.sam,
            completed_at=datetime(2026, 8, 27, 12, tzinfo=timezone.utc),
        )

        with patch("chores.views.date") as mocked_date:
            mocked_date.today.return_value = date(2026, 9, 4)
            response = self.client.get("/history/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aug. 24, 2026")
        self.assertContains(response, "Historical chore")
        self.assertContains(response, "completed by Sam")
        self.assertEqual(WeeklySummary.objects.count(), 2)
        self.assertEqual(WeeklySummary.objects.get(member=self.alex).planned_effort_points, 3)
        self.assertEqual(WeeklySummary.objects.get(member=self.sam).actual_effort_points, 3)

    def test_history_reports_empty_state_without_closed_weeks(self):
        response = self.client.get("/history/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No closed weeks yet.")

    def test_closed_summary_can_be_rebuilt_without_duplicate_rows(self):
        ChoreOccurrence.objects.create(
            definition=self.definition,
            due_date=date(2026, 8, 27),
            chore_name=self.definition.name,
            category=self.definition.category,
            effort_score=self.definition.effort_score,
            priority=self.definition.priority,
            recurrence=self.definition.recurrence,
        )

        persist_closed_week_summaries(date(2026, 9, 4))
        persist_closed_week_summaries(date(2026, 9, 5))

        self.assertEqual(WeeklySummary.objects.count(), 2)


class PersistenceBoundaryTests(TestCase):
    def setUp(self):
        self.member = HouseholdMember.objects.create(name="Alex")
        self.definition = ChoreDefinition.objects.create(
            name="Clean bathroom",
            category=ChoreDefinition.Category.CLEANING,
            effort_score=4,
            priority=ChoreDefinition.Priority.MEDIUM,
            recurrence=ChoreDefinition.Recurrence.WEEKLY,
            assignment_type=ChoreDefinition.AssignmentType.FIXED,
            fixed_member=self.member,
        )
        self.occurrence = ChoreOccurrence.objects.create(
            definition=self.definition,
            due_date=date(2026, 9, 7),
            chore_name=self.definition.name,
            category=self.definition.category,
            effort_score=self.definition.effort_score,
            priority=self.definition.priority,
        )

    def test_mvp_persistence_boundaries_are_related(self):
        assignment = ChoreAssignment.objects.create(
            occurrence=self.occurrence,
            member=self.member,
        )
        completion = ChoreCompletion.objects.create(
            occurrence=self.occurrence,
            completed_by=self.member,
            completed_at=datetime(2026, 9, 7, 12, tzinfo=timezone.utc),
        )
        summary = WeeklySummary.objects.create(
            week_start=date(2026, 9, 7),
            member=self.member,
            planned_effort_points=4,
            actual_effort_points=4,
            completed_chore_count=1,
        )

        self.assertEqual(self.definition.occurrences.get(), self.occurrence)
        self.assertEqual(self.occurrence.assignment, assignment)
        self.assertEqual(self.occurrence.completion, completion)
        self.assertEqual(self.member.weekly_summaries.get(), summary)

    def test_duplicate_occurrence_for_definition_and_date_is_rejected(self):
        with self.assertRaises(IntegrityError):
            ChoreOccurrence.objects.create(
                definition=self.definition,
                due_date=self.occurrence.due_date,
                chore_name=self.definition.name,
                category=self.definition.category,
                effort_score=self.definition.effort_score,
                priority=self.definition.priority,
            )

    def test_effort_score_is_constrained_to_one_through_five(self):
        with self.assertRaises(IntegrityError):
            ChoreDefinition.objects.create(
                name="Invalid chore",
                category=ChoreDefinition.Category.OTHER,
                effort_score=6,
                priority=ChoreDefinition.Priority.LOW,
                recurrence=ChoreDefinition.Recurrence.ONE_TIME,
                assignment_type=ChoreDefinition.AssignmentType.UNASSIGNED,
            )
