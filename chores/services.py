import calendar
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from .models import ChoreAssignment, ChoreCompletion, ChoreDefinition, ChoreOccurrence, HouseholdMember, WeeklySummary


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


def refresh_overdue_occurrences(as_of=None):
    as_of = as_of or timezone.localdate()
    return ChoreOccurrence.objects.filter(
        status=ChoreOccurrence.Status.PENDING,
        due_date__lt=as_of,
    ).update(status=ChoreOccurrence.Status.OVERDUE)


def complete_occurrence(occurrence, member, completed_at=None):
    if occurrence.status == ChoreOccurrence.Status.CANCELLED:
        raise ValueError("A cancelled occurrence cannot be completed")
    completed_at = completed_at or timezone.now()
    with transaction.atomic():
        completion, _ = ChoreCompletion.objects.update_or_create(
            occurrence=occurrence,
            defaults={"completed_by": member, "completed_at": completed_at},
        )
        occurrence.status = ChoreOccurrence.Status.COMPLETED
        occurrence.save(update_fields=["status"])
    return completion


def reschedule_occurrence(occurrence, due_date):
    if occurrence.status in {ChoreOccurrence.Status.COMPLETED, ChoreOccurrence.Status.CANCELLED}:
        raise ValueError("Only pending or overdue occurrences can be rescheduled")
    occurrence.due_date = due_date
    occurrence.status = ChoreOccurrence.Status.PENDING
    occurrence.save(update_fields=["due_date", "status"])
    return occurrence


def cancel_occurrence(occurrence):
    if occurrence.status == ChoreOccurrence.Status.COMPLETED:
        raise ValueError("A completed occurrence cannot be cancelled")
    occurrence.status = ChoreOccurrence.Status.CANCELLED
    occurrence.save(update_fields=["status"])
    return occurrence


def calculate_workload(occurrences):
    """Return planned and actual effort totals for the household members."""
    totals = {
        member.id: {
            "planned_effort_points": 0,
            "actual_effort_points": 0,
            "completed_chore_count": 0,
        }
        for member in HouseholdMember.objects.order_by("id")
    }
    for occurrence in occurrences:
        assignment = getattr(occurrence, "assignment", None)
        if assignment is not None and assignment.member_id in totals:
            totals[assignment.member_id]["planned_effort_points"] += occurrence.effort_score

        completion = getattr(occurrence, "completion", None)
        if occurrence.status == ChoreOccurrence.Status.COMPLETED and completion is not None:
            if completion.completed_by_id in totals:
                totals[completion.completed_by_id]["actual_effort_points"] += occurrence.effort_score
                totals[completion.completed_by_id]["completed_chore_count"] += 1

    planned_total = sum(item["planned_effort_points"] for item in totals.values())
    actual_total = sum(item["actual_effort_points"] for item in totals.values())
    for item in totals.values():
        item["planned_percentage"] = _percentage(item["planned_effort_points"], planned_total)
        item["actual_percentage"] = _percentage(item["actual_effort_points"], actual_total)
    return totals


def persist_weekly_summary(week_start):
    """Persist the planned/actual snapshot for one closed Monday-Sunday week."""
    if week_start.weekday() != 0:
        raise ValueError("week_start must be a Monday")
    week_end = week_start + timedelta(days=6)
    occurrences = ChoreOccurrence.objects.filter(due_date__range=(week_start, week_end)).select_related(
        "assignment", "completion"
    )
    totals = calculate_workload(occurrences)
    with transaction.atomic():
        for member_id, values in totals.items():
            WeeklySummary.objects.update_or_create(
                week_start=week_start,
                member_id=member_id,
                defaults={
                    "planned_effort_points": values["planned_effort_points"],
                    "actual_effort_points": values["actual_effort_points"],
                    "completed_chore_count": values["completed_chore_count"],
                },
            )
    return totals


def persist_closed_week_summaries(as_of=None):
    """Create or refresh summaries for every week before the current week."""
    as_of = as_of or timezone.localdate()
    current_week = week_start_for(as_of)
    week_starts = {
        week_start_for(occurrence.due_date)
        for occurrence in ChoreOccurrence.objects.filter(due_date__lt=current_week).only("due_date")
    }
    week_starts.update(WeeklySummary.objects.filter(week_start__lt=current_week).values_list("week_start", flat=True))
    for week_start in sorted(week_starts):
        persist_weekly_summary(week_start)
    return sorted(week_starts)


def _percentage(value, total):
    return round(value * 100 / total, 2) if total else 0


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
