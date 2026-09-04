from django.db import models


class HouseholdMember(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("id",)

    def __str__(self):
        return self.name


class ChoreDefinition(models.Model):
    class Category(models.TextChoices):
        CLEANING = "cleaning", "Cleaning"
        LAUNDRY = "laundry", "Laundry"
        KITCHEN = "kitchen", "Kitchen"
        SHOPPING = "shopping", "Shopping"
        MAINTENANCE = "maintenance", "Maintenance"
        PETS = "pets", "Pets"
        OTHER = "other", "Other"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class Recurrence(models.TextChoices):
        ONE_TIME = "one-time", "One-time"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    class AssignmentType(models.TextChoices):
        FIXED = "fixed", "Fixed"
        ALTERNATING = "alternating", "Alternating"
        UNASSIGNED = "unassigned", "Unassigned"

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    effort_score = models.PositiveSmallIntegerField()
    priority = models.CharField(max_length=10, choices=Priority.choices)
    recurrence = models.CharField(max_length=10, choices=Recurrence.choices)
    assignment_type = models.CharField(max_length=12, choices=AssignmentType.choices)
    fixed_member = models.ForeignKey(
        HouseholdMember,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="fixed_chore_definitions",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        constraints = (
            models.CheckConstraint(
                condition=models.Q(effort_score__gte=1, effort_score__lte=5),
                name="chore_definition_effort_score_1_to_5",
            ),
        )

    def __str__(self):
        return self.name


class ChoreOccurrence(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        OVERDUE = "overdue", "Overdue"
        CANCELLED = "cancelled", "Cancelled"

    definition = models.ForeignKey(ChoreDefinition, on_delete=models.PROTECT, related_name="occurrences")
    due_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    chore_name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=ChoreDefinition.Category.choices)
    effort_score = models.PositiveSmallIntegerField()
    priority = models.CharField(max_length=10, choices=ChoreDefinition.Priority.choices)
    recurrence = models.CharField(
        max_length=10,
        choices=ChoreDefinition.Recurrence.choices,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("due_date", "id")
        constraints = (
            models.UniqueConstraint(fields=("definition", "due_date"), name="one_occurrence_per_definition_and_due_date"),
            models.CheckConstraint(condition=models.Q(effort_score__gte=1, effort_score__lte=5), name="chore_occurrence_effort_score_1_to_5"),
        )

    def __str__(self):
        return f"{self.chore_name} on {self.due_date}"


class ChoreAssignment(models.Model):
    occurrence = models.OneToOneField(ChoreOccurrence, on_delete=models.CASCADE, related_name="assignment")
    member = models.ForeignKey(HouseholdMember, on_delete=models.PROTECT, related_name="chore_assignments")
    assigned_at = models.DateTimeField(auto_now_add=True)


class ChoreCompletion(models.Model):
    occurrence = models.OneToOneField(ChoreOccurrence, on_delete=models.CASCADE, related_name="completion")
    completed_by = models.ForeignKey(HouseholdMember, on_delete=models.PROTECT, related_name="chore_completions")
    completed_at = models.DateTimeField()


class WeeklySummary(models.Model):
    week_start = models.DateField()
    member = models.ForeignKey(HouseholdMember, on_delete=models.PROTECT, related_name="weekly_summaries")
    planned_effort_points = models.PositiveIntegerField(default=0)
    actual_effort_points = models.PositiveIntegerField(default=0)
    completed_chore_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-week_start", "member_id")
        constraints = (
            models.UniqueConstraint(fields=("week_start", "member"), name="one_weekly_summary_per_member"),
        )

    def __str__(self):
        return f"{self.member} summary for {self.week_start}"
