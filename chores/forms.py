from django import forms


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
