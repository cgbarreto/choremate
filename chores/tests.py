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
