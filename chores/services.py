import calendar
from datetime import date, timedelta

from django.db import transaction

from .models import ChoreAssignment, ChoreDefinition, ChoreOccurrence, HouseholdMember


def week_start_for(day=None):
    day = day or date.today()
    return day - timedelta(days=day.weekday())


def generate_occurrences_for_week(week_start):
    """Create active recurring occurrences in the Monday-to-Sunday week."""
    if week_start.weekday() != 0:
        raise ValueError("week_start must be a Monday")

    week_end = week_start + timedelta(days=6)
    with transaction.atomic():
        occurrences = []
        for definition in ChoreDefinition.objects.filter(is_active=True).order_by("id"):
            for due_date in _recurring_dates(definition, week_start, week_end):
                occurrence, created = _get_or_create_occurrence(definition, due_date)
                if created:
                    _create_assignment_if_needed(occurrence, definition)
                occurrences.append(occurrence)
        return occurrences


def create_one_time_occurrence(definition, due_date):
    """Create a manually scheduled one-time occurrence from a definition."""
    if definition.recurrence != ChoreDefinition.Recurrence.ONE_TIME:
        raise ValueError("Only one-time definitions can create one-time occurrences")

    with transaction.atomic():
        occurrence, created = _get_or_create_occurrence(definition, due_date)
        if created:
            _create_assignment_if_needed(occurrence, definition)
        return occurrence


def _recurring_dates(definition, week_start, week_end):
    if definition.recurrence == ChoreDefinition.Recurrence.DAILY:
        return [week_start + timedelta(days=offset) for offset in range(7)]

    if definition.recurrence == ChoreDefinition.Recurrence.WEEKLY:
        due_date = week_start + timedelta(days=definition.created_at.weekday())
        return [due_date]

    if definition.recurrence == ChoreDefinition.Recurrence.MONTHLY:
        dates = []
        cursor = date(week_start.year, week_start.month, 1)
        while cursor <= week_end:
            last_day = calendar.monthrange(cursor.year, cursor.month)[1]
            due_date = date(cursor.year, cursor.month, min(definition.created_at.day, last_day))
            if week_start <= due_date <= week_end:
                dates.append(due_date)
            cursor = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
        return dates

    return []


def _get_or_create_occurrence(definition, due_date):
    return ChoreOccurrence.objects.get_or_create(
        definition=definition,
        due_date=due_date,
        defaults={
            "chore_name": definition.name,
            "category": definition.category,
            "effort_score": definition.effort_score,
            "priority": definition.priority,
            "recurrence": definition.recurrence,
        },
    )


def _create_assignment_if_needed(occurrence, definition):
    if definition.assignment_type == ChoreDefinition.AssignmentType.UNASSIGNED:
        return

    members = list(HouseholdMember.objects.order_by("id")[:2])
    if definition.assignment_type == ChoreDefinition.AssignmentType.FIXED:
        if definition.fixed_member is None:
            raise ValueError("A fixed definition requires a member")
        member = definition.fixed_member
    else:
        if len(members) != 2:
            raise ValueError("Exactly two household members are required for alternating chores")
        previous_count = ChoreOccurrence.objects.filter(
            definition=definition,
            due_date__lt=occurrence.due_date,
        ).count()
        member = members[previous_count % 2]

    ChoreAssignment.objects.create(occurrence=occurrence, member=member)
