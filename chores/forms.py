from django import forms

from .models import ChoreDefinition, HouseholdMember


class HouseholdSetupForm(forms.Form):
    member_one = forms.CharField(
        label="Member 1",
        max_length=100,
        error_messages={"required": "This name is required."},
    )
    member_two = forms.CharField(
        label="Member 2",
        max_length=100,
        error_messages={"required": "This name is required."},
    )

    def clean_member_one(self):
        return self._clean_name("member_one")

    def clean_member_two(self):
        return self._clean_name("member_two")

    def clean(self):
        cleaned_data = super().clean()
        member_one = cleaned_data.get("member_one")
        member_two = cleaned_data.get("member_two")
        if member_one and member_two and member_one.casefold() == member_two.casefold():
            raise forms.ValidationError("Choose two different member names.")
        return cleaned_data

    def _clean_name(self, field_name):
        value = self.cleaned_data[field_name].strip()
        if not value:
            raise forms.ValidationError("This name is required.")
        return value


class MemberRenameForm(forms.Form):
    name = forms.CharField(
        label="Name",
        max_length=100,
        error_messages={"required": "This name is required."},
    )

    def clean_name(self):
        value = self.cleaned_data["name"].strip()
        if not value:
            raise forms.ValidationError("This name is required.")
        return value


class ChoreDefinitionForm(forms.ModelForm):
    class Meta:
        model = ChoreDefinition
        fields = (
            "name",
            "description",
            "category",
            "effort_score",
            "priority",
            "recurrence",
            "assignment_type",
            "fixed_member",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "effort_score": forms.NumberInput(attrs={"min": 1, "max": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fixed_member"].queryset = HouseholdMember.objects.order_by("id")
        self.fields["fixed_member"].required = False

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("A chore name is required.")
        return name

    def clean_effort_score(self):
        effort_score = self.cleaned_data["effort_score"]
        if not 1 <= effort_score <= 5:
            raise forms.ValidationError("Effort score must be between 1 and 5.")
        return effort_score

    def clean(self):
        cleaned_data = super().clean()
        assignment_type = cleaned_data.get("assignment_type")
        fixed_member = cleaned_data.get("fixed_member")
        if assignment_type == ChoreDefinition.AssignmentType.FIXED and fixed_member is None:
            self.add_error("fixed_member", "Select a member for a fixed chore.")
        if assignment_type != ChoreDefinition.AssignmentType.FIXED:
            cleaned_data["fixed_member"] = None
        return cleaned_data


class OccurrenceAssignmentForm(forms.Form):
    member = forms.ModelChoiceField(
        label="Member",
        queryset=HouseholdMember.objects.none(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["member"].queryset = HouseholdMember.objects.order_by("id")
