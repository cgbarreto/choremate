from datetime import date, datetime, timezone

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
